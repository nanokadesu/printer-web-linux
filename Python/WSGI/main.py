# coding: utf-8
"""Linux CUPS print service.

The service intentionally keeps conversion and queue state on disk so a
restarted process cannot accidentally resume a manual duplex context.
"""
from __future__ import annotations

import html
import io
import json
import logging
import os
import queue
import re
import shutil
import subprocess
import tempfile
import threading
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, Tuple

import yaml
import cv2
import numpy as np
from flask import Flask, jsonify, request
from flask_cors import CORS
from PIL import Image
from pypdf import PdfReader, PdfWriter
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.lib.utils import ImageReader
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer
from werkzeug.security import check_password_hash


ROOT = Path(__file__).resolve().parent
CONFIG_PATH = Path(os.environ.get("PRINTER_CONFIG", ROOT / "config.yaml"))


def load_config(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as stream:
        config = yaml.safe_load(stream) or {}
    required = ("server", "ip_list", "auth", "cups", "storage", "conversion")
    missing = [key for key in required if key not in config]
    if missing:
        raise RuntimeError("config.yaml 缺少字段: " + ", ".join(missing))
    color_options = config.get("cups", {}).get("color_options", {})
    color_values = color_options.get("values", {})
    if not color_options.get("option") or not all(mode in color_values for mode in ("color", "monochrome")):
        raise RuntimeError("config.yaml 缺少完整的 cups.color_options 配置")
    conversion = config.get("conversion", {})
    horizontal_margin_ratio = float(conversion.get("image_horizontal_margin_ratio", 0.04))
    vertical_margin_ratio = float(conversion.get("image_vertical_margin_ratio", 0.08))
    margin_values = {
        "left": float(conversion.get("image_left_margin_ratio", horizontal_margin_ratio)),
        "right": float(conversion.get("image_right_margin_ratio", horizontal_margin_ratio)),
        "top": float(conversion.get("image_top_margin_ratio", vertical_margin_ratio)),
        "bottom": float(conversion.get("image_bottom_margin_ratio", vertical_margin_ratio)),
    }
    if any(not 0 <= value < 0.5 for value in margin_values.values()):
        raise RuntimeError("图片四边边距比例必须分别在 0 到 0.5 之间")
    if margin_values["left"] + margin_values["right"] >= 1 or margin_values["top"] + margin_values["bottom"] >= 1:
        raise RuntimeError("图片左右或上下边距之和必须小于 1")
    if str(conversion.get("image_interpolation", "cubic")).lower() != "cubic":
        raise RuntimeError("conversion.image_interpolation 当前仅支持 cubic")
    calibration_marks = conversion.get("calibration_marks_mm", [0, 5, 10, 15, 20])
    if not isinstance(calibration_marks, (list, tuple)):
        raise RuntimeError("conversion.calibration_marks_mm 必须是数组")
    try:
        calibration_marks = [float(value) for value in calibration_marks]
    except (TypeError, ValueError):
        raise RuntimeError("conversion.calibration_marks_mm 必须是数字")
    if not any(0 <= value < 100 for value in calibration_marks):
        raise RuntimeError("conversion.calibration_marks_mm 至少需要一个有效刻度")
    return config


CONFIG = load_config(CONFIG_PATH)
IP_LIST = [str(item).strip() for item in CONFIG.get("ip_list", []) if str(item).strip()]
STORAGE = CONFIG["storage"]
UPLOAD_DIR = Path(STORAGE["upload_dir"]).expanduser()
QUEUE_DIR = Path(STORAGE["queue_dir"]).expanduser()
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
QUEUE_DIR.mkdir(parents=True, exist_ok=True)

logging.basicConfig(
    level=getattr(logging, str(CONFIG.get("logging", {}).get("level", "INFO")).upper(), logging.INFO),
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)
LOGGER = logging.getLogger("printer")

app = Flask(__name__)
origins = [f"http://{ip}:{CONFIG['server'].get('frontend_port', 5173)}" for ip in IP_LIST]
CORS(app, resources={r"/api/*": {"origins": origins or "*"}})

TOKENS = {}
JOBS = {}
JOB_CANCEL_EVENTS = {}
JOB_CONTINUE_EVENTS = {}
JOB_LOCK = threading.RLock()
PENDING = queue.Queue()
STOP = threading.Event()


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def job_path(job_id: str) -> Path:
    return QUEUE_DIR / job_id / "job.json"


def save_job(job: dict) -> None:
    job["updated_at"] = now()
    path = job_path(job["job_id"])
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temp_name = tempfile.mkstemp(prefix="job-", suffix=".json", dir=str(path.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            json.dump(job, stream, ensure_ascii=False, indent=2)
        os.replace(temp_name, path)
    finally:
        if os.path.exists(temp_name):
            os.unlink(temp_name)
    with JOB_LOCK:
        JOBS[job["job_id"]] = dict(job)


def load_jobs() -> None:
    for path in QUEUE_DIR.glob("*/job.json"):
        try:
            job = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            LOGGER.exception("读取任务失败: %s", path)
            continue
        status = job.get("status")
        if status in {"waiting_second_side", "converting", "printing_front", "printing_back"}:
            job["status"] = "interrupted"
            job["phase"] = "interrupted"
            job["error"] = "服务重启导致打印上下文失效，不能恢复"
            save_job(job)
        elif status == "pending":
            with JOB_LOCK:
                JOBS[job["job_id"]] = job
            PENDING.put(job["job_id"])
        else:
            with JOB_LOCK:
                JOBS[job["job_id"]] = job


def auth_required() -> bool:
    return bool(CONFIG.get("auth", {}).get("enabled", True))


def authorized() -> bool:
    if not auth_required():
        return True
    header = request.headers.get("Authorization", "")
    token = header[7:] if header.lower().startswith("bearer ") else ""
    return bool(token and token in TOKENS)


@app.before_request
def require_authentication():
    if request.path in {"/api/health", "/api/login"} or not request.path.startswith("/api/"):
        return None
    if not authorized():
        return jsonify({"error": "未登录或登录已过期"}), 401
    return None


def run_command(args: list[str], timeout: int = 60) -> subprocess.CompletedProcess:
    LOGGER.debug("执行命令: %s", args)
    return subprocess.run(args, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=timeout)


def printer_config(printer_id) -> Optional[dict]:
    for printer in CONFIG["cups"].get("printers", []):
        if str(printer.get("id")) == str(printer_id):
            return printer
    return None


def cups_capabilities(name: str) -> dict:
    result = run_command(["lpoptions", "-p", name, "-l"])
    text = (result.stdout or "") + "\n" + (result.stderr or "")
    duplex = bool(re.search(r"(?im)^(Duplex|Sides)/", text)) or bool(re.search(r"(?i)two-sided|duplex", text))
    color = bool(re.search(r"(?im)^(ColorModel|PrintColorMode|print-color-mode)/", text))
    return {"duplex": duplex, "color": color, "raw": text if result.returncode == 0 else ""}


def printer_status(name: str) -> str:
    result = run_command(["lpstat", "-p", name])
    if result.returncode != 0:
        return "offline"
    text = result.stdout.lower()
    return "offline" if any(value in text for value in ("disabled", "rejecting", "not found")) else "online"


def register_font() -> str:
    candidates = [
        CONFIG["conversion"].get("font_path", ""),
        "/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc",
        "/usr/share/fonts/truetype/arphic/uming.ttc",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    ]
    for raw in candidates:
        if not raw or not Path(raw).exists():
            continue
        try:
            name = "PrinterCJK"
            if name not in pdfmetrics.getRegisteredFontNames():
                pdfmetrics.registerFont(TTFont(name, raw))
            return name
        except Exception:
            LOGGER.warning("字体注册失败: %s", raw, exc_info=True)
    return "Helvetica"


def text_to_pdf(source: Path, output: Path) -> None:
    font = register_font()
    margins = CONFIG["conversion"].get("text_margins_mm", [25.4, 25.4, 25.4, 25.4])
    left, top, right, bottom = [float(value) * mm for value in margins]
    content = source.read_text(encoding="utf-8", errors="replace")
    styles = getSampleStyleSheet()
    style = ParagraphStyle(
        "text", parent=styles["Normal"], fontName=font, fontSize=10, leading=14,
        wordWrap="CJK", spaceAfter=0,
    )
    story = []
    for line in content.splitlines() or [""]:
        story.append(Paragraph(html.escape(line).replace("  ", "&nbsp; ") or "&nbsp;", style))
        story.append(Spacer(1, 1.5 * mm))
    doc = SimpleDocTemplate(str(output), pagesize=A4, leftMargin=left, rightMargin=right,
                            topMargin=top, bottomMargin=bottom)
    doc.build(story)


def _opencv_frames(source: Path):
    if source.suffix.lower() in {".tif", ".tiff"}:
        ok, frames = cv2.imreadmulti(str(source), flags=cv2.IMREAD_UNCHANGED)
        if ok and frames:
            return frames
    image = cv2.imread(str(source), cv2.IMREAD_UNCHANGED)
    if image is None:
        raise RuntimeError("图片读取失败: " + source.name)
    return [image]


def _opencv_to_rgb(image):
    if image is None:
        raise RuntimeError("图片解码失败")
    if len(image.shape) == 2:
        return cv2.cvtColor(image, cv2.COLOR_GRAY2RGB)
    if image.shape[2] == 4:
        rgba = cv2.cvtColor(image, cv2.COLOR_BGRA2RGBA)
        alpha = rgba[:, :, 3:4].astype("float32") / 255.0
        white = np.full(rgba[:, :, :3].shape, 255, dtype="uint8")
        rgb = (rgba[:, :, :3].astype("float32") * alpha + white * (1 - alpha)).astype("uint8")
        return rgb
    return cv2.cvtColor(image, cv2.COLOR_BGR2RGB)


def image_to_pdf(source: Path, output: Path, orientation: str = "portrait") -> None:
    page_width, page_height = A4
    if orientation == "landscape":
        page_width, page_height = page_height, page_width
    conversion = CONFIG["conversion"]
    horizontal_margin_ratio = float(conversion.get("image_horizontal_margin_ratio", 0.04))
    vertical_margin_ratio = float(conversion.get("image_vertical_margin_ratio", 0.08))
    left_ratio = float(conversion.get("image_left_margin_ratio", horizontal_margin_ratio))
    right_ratio = float(conversion.get("image_right_margin_ratio", horizontal_margin_ratio))
    top_ratio = float(conversion.get("image_top_margin_ratio", vertical_margin_ratio))
    bottom_ratio = float(conversion.get("image_bottom_margin_ratio", vertical_margin_ratio))
    interpolation_name = str(CONFIG["conversion"].get("image_interpolation", "cubic")).lower()
    interpolations = {"cubic": cv2.INTER_CUBIC}
    if interpolation_name not in interpolations:
        raise RuntimeError("不支持的图片缩放算法: " + interpolation_name)
    dpi = float(CONFIG["conversion"].get("pdf_dpi", 300))
    if dpi <= 0:
        raise RuntimeError("图片输出 DPI 必须大于 0")
    left = page_width * left_ratio
    right = page_width * right_ratio
    bottom = page_height * bottom_ratio
    top = page_height * top_ratio
    content_width = page_width - left - right
    content_height = page_height - top - bottom
    target_width_px = max(1, round(content_width / 72 * dpi))
    target_height_px = max(1, round(content_height / 72 * dpi))
    output.parent.mkdir(parents=True, exist_ok=True)
    pdf = canvas.Canvas(str(output), pagesize=(page_width, page_height))
    try:
        for frame in _opencv_frames(source):
            rgb = _opencv_to_rgb(frame)
            height_px, width_px = rgb.shape[:2]
            if width_px <= 0 or height_px <= 0:
                raise RuntimeError("图片尺寸无效: " + source.name)
            # Use the more restrictive axis for one uniform scale so the
            # complete image remains inside the printable safety frame.
            width_scale = target_width_px / width_px
            height_scale = target_height_px / height_px
            scale = min(width_scale, height_scale)
            resized_width = max(1, round(width_px * scale))
            resized_height = max(1, round(height_px * scale))
            resized = cv2.resize(
                rgb, (resized_width, resized_height), interpolation=interpolations[interpolation_name]
            )
            ok, encoded = cv2.imencode(".png", cv2.cvtColor(resized, cv2.COLOR_RGB2BGR))
            if not ok:
                raise RuntimeError("图片编码失败: " + source.name)
            image_reader = ImageReader(io.BytesIO(encoded.tobytes()))
            draw_width = resized_width / dpi * 72
            draw_height = resized_height / dpi * 72
            x = left + (content_width - draw_width) / 2
            y = bottom + (content_height - draw_height) / 2
            pdf.drawImage(image_reader, x, y, width=draw_width, height=draw_height,
                          preserveAspectRatio=True, mask="auto")
            pdf.showPage()
    finally:
        pdf.save()


def calibration_to_pdf(output: Path, orientation: str = "portrait") -> list[float]:
    page_width, page_height = A4
    if orientation == "landscape":
        page_width, page_height = page_height, page_width
    configured_marks = CONFIG["conversion"].get("calibration_marks_mm", [0, 5, 10, 15, 20])
    marks = sorted({float(value) for value in configured_marks if 0 <= float(value) < min(page_width, page_height) / mm / 2})
    if not marks:
        raise RuntimeError("校准刻度配置无效")
    output.parent.mkdir(parents=True, exist_ok=True)
    pdf = canvas.Canvas(str(output), pagesize=(page_width, page_height))
    font = register_font()
    pdf.setTitle("GreenPrint physical calibration")
    pdf.setFont(font if font != "Helvetica" else "Helvetica", 8)
    pdf.setStrokeColorRGB(0.1, 0.1, 0.1)
    pdf.setFillColorRGB(0.1, 0.1, 0.1)
    tick_length = 5 * mm
    label_gap = 2 * mm
    for value in marks:
        distance = value * mm
        label = f"{value:g} mm"
        # Each edge has a tick at the exact requested distance from paper edge.
        pdf.line(distance, page_height, distance, page_height - tick_length)
        pdf.drawString(distance + label_gap, page_height - tick_length - 8, label)
        pdf.line(distance, 0, distance, tick_length)
        pdf.drawString(distance + label_gap, tick_length + 2, label)
        pdf.line(0, distance, tick_length, distance)
        pdf.drawString(tick_length + 2, distance + 1, label)
        pdf.line(page_width, distance, page_width - tick_length, distance)
        pdf.drawRightString(page_width - tick_length - 2, distance + 1, label)
    pdf.setLineWidth(0.7)
    pdf.rect(0, 0, page_width, page_height)
    pdf.setLineWidth(0.5)
    pdf.line(page_width / 2 - 20 * mm, page_height / 2, page_width / 2 + 20 * mm, page_height / 2)
    pdf.line(page_width / 2, page_height / 2 - 20 * mm, page_width / 2, page_height / 2 + 20 * mm)
    pdf.setFont("Helvetica", 10)
    pdf.drawCentredString(page_width / 2, page_height / 2 + 24 * mm, "PHYSICAL CALIBRATION")
    pdf.drawCentredString(page_width / 2, page_height / 2 + 17 * mm, "Measure from the actual paper edge")
    pdf.drawCentredString(page_width / 2, page_height / 2 + 10 * mm, "Adjust image margins in config.yaml")
    pdf.showPage()
    pdf.save()
    return marks


def rasterize_pdf(source: Path, output: Path) -> None:
    """Rasterize a PDF when a CUPS filter cannot consume the source PDF."""
    dpi = str(CONFIG["conversion"].get("pdf_dpi", 300))
    with tempfile.TemporaryDirectory(prefix="printer-raster-") as temp:
        prefix = str(Path(temp) / "page")
        result = run_command(["pdftoppm", "-png", "-r", dpi, str(source), prefix], timeout=240)
        if result.returncode != 0:
            raise RuntimeError((result.stderr or result.stdout or "PDF 栅格化失败").strip())
        pages = sorted(Path(temp).glob("page-*.png"))
        if not pages:
            raise RuntimeError("PDF 栅格化未生成页面")
        images = [Image.open(page).convert("RGB") for page in pages]
        try:
            images[0].save(str(output), "PDF", resolution=float(dpi), save_all=True,
                           append_images=images[1:])
        finally:
            for image in images:
                image.close()


def command_to_pdf(source: Path, output: Path, extension: str) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    if extension in {".md", ".markdown"}:
        command = ["pandoc", str(source), "-o", str(output), "--from=markdown+tex_math_dollars+raw_tex",
                   "--pdf-engine=xelatex", "-V", "geometry:margin=25.4mm",
                   "-V", "CJKmainfont=AR PL UMing CN"]
        result = run_command(command, timeout=180)
        if result.returncode != 0:
            raise RuntimeError((result.stderr or result.stdout or "Pandoc 导出失败").strip())
    elif extension in {".tex", ".latex"}:
        with tempfile.TemporaryDirectory(prefix="printer-tex-") as temp:
            temp_dir = Path(temp)
            copied = temp_dir / source.name
            shutil.copy2(source, copied)
            result = run_command(["xelatex", "-interaction=nonstopmode", "-halt-on-error", "-output-directory", temp,
                                  str(copied)], timeout=180)
            generated = temp_dir / (source.stem + ".pdf")
            if result.returncode != 0 or not generated.exists():
                raise RuntimeError((result.stderr or result.stdout or "LaTeX 编译失败").strip()[-4000:])
            shutil.copy2(generated, output)
    elif extension in {".doc", ".docx"}:
        with tempfile.TemporaryDirectory(prefix="printer-office-") as temp:
            result = run_command(["libreoffice", "--headless", "--convert-to", "pdf", "--outdir", temp, str(source)], timeout=240)
            generated = Path(temp) / (source.stem + ".pdf")
            if result.returncode != 0 or not generated.exists():
                raise RuntimeError((result.stderr or result.stdout or "Office 文档导出失败").strip()[-4000:])
            shutil.copy2(generated, output)
    else:
        raise RuntimeError("不支持的文件类型: " + extension)


def convert_to_pdf(source: Path, output: Path, orientation: str = "portrait") -> None:
    extension = source.suffix.lower()
    if extension == ".pdf":
        shutil.copy2(source, output)
    elif extension in {".png", ".webp", ".jpg", ".jpeg", ".gif", ".bmp", ".tif", ".tiff"}:
        image_to_pdf(source, output, orientation=orientation)
    elif extension == ".txt":
        text_to_pdf(source, output)
    elif extension in {".md", ".markdown", ".tex", ".latex", ".doc", ".docx"}:
        command_to_pdf(source, output, extension)
    else:
        raise RuntimeError("不支持的文件类型: " + extension)


def submit_document(job: dict, path: Path, page_set: Optional[str] = None, duplex: bool = False) -> str:
    try:
        return submit_cups(job, path, page_set=page_set, duplex=duplex)
    except Exception:
        if str(CONFIG["conversion"].get("pdf_mode", "direct")).lower() == "direct":
            raise
        fallback = path.with_name(path.stem + "-raster.pdf")
        rasterize_pdf(path, fallback)
        return submit_cups(job, fallback, page_set=page_set, duplex=duplex)


def split_pdf(source: Path, front: Path, back: Path) -> Tuple[int, int]:
    reader = PdfReader(str(source))
    front_writer, back_writer = PdfWriter(), PdfWriter()
    for index, page in enumerate(reader.pages):
        (front_writer if index % 2 == 0 else back_writer).add_page(page)
    with front.open("wb") as stream:
        front_writer.write(stream)
    with back.open("wb") as stream:
        back_writer.write(stream)
    return len(front_writer.pages), len(back_writer.pages)


def parse_job_id(stdout: str) -> str:
    match = re.search(r"request id is ([^\s]+)", stdout, re.IGNORECASE)
    return match.group(1) if match else stdout.strip().splitlines()[-1].strip()


def submit_cups(job: dict, path: Path, page_set: Optional[str] = None, duplex: bool = False) -> str:
    printer = printer_config(job["printer_id"])
    if not printer:
        raise RuntimeError("打印机不存在")
    options = CONFIG["cups"].get("default_options", {})
    command = ["lp", "-d", printer["cups_name"], "-n", str(job["copies"])]
    command.extend(["-o", "media=" + str(options.get("media", "A4"))])
    orientation = job.get("orientation", "portrait")
    command.extend(["-o", "orientation-requested=" + ("4" if orientation == "landscape" else "3")])
    if options.get("media_type"):
        command.extend(["-o", "media-type=" + str(options["media_type"])])
    if options.get("quality"):
        command.extend(["-o", "print-quality=" + str(options["quality"])])
    color_options = CONFIG["cups"].get("color_options", {})
    color_mode = job.get("color_mode", "color")
    color_value = color_options.get("values", {}).get(color_mode)
    if color_options.get("option") and color_value:
        command.extend(["-o", f"{color_options['option']}={color_value}"])
    if page_set:
        command.extend(["-o", "page-set=" + page_set])
    if duplex:
        command.extend(["-o", "sides=two-sided-long-edge"])
    command.append(str(path))
    result = run_command(command, timeout=60)
    if result.returncode != 0:
        raise RuntimeError((result.stderr or result.stdout or "CUPS 提交失败").strip())
    return parse_job_id(result.stdout)


def wait_cups(job_id: str, cancel_event: threading.Event) -> bool:
    poll = float(CONFIG["cups"].get("poll_seconds", 1))
    timeout = float(CONFIG["cups"].get("job_timeout_seconds", 3600))
    started = time.monotonic()
    while time.monotonic() - started < timeout:
        if cancel_event.is_set():
            return False
        result = run_command(["lpstat", "-W", "not-completed", "-o"])
        if job_id not in (result.stdout or ""):
            return True
        time.sleep(poll)
    raise RuntimeError("CUPS 任务等待超时: " + job_id)


def cleanup_job_files(job: dict) -> None:
    if not CONFIG["storage"].get("retain_completed", False):
        shutil.rmtree(QUEUE_DIR / job["job_id"], ignore_errors=True)


def set_status(job: dict, status: str, **fields) -> None:
    job["status"] = status
    job["phase"] = status
    job.update(fields)
    save_job(job)


def process_job(job: dict) -> None:
    job_id = job["job_id"]
    cancel_event = JOB_CANCEL_EVENTS.setdefault(job_id, threading.Event())
    continue_event = JOB_CONTINUE_EVENTS.setdefault(job_id, threading.Event())
    job_dir = QUEUE_DIR / job["job_id"]
    document = job_dir / "document.pdf"

    def was_cancelled() -> bool:
        with JOB_LOCK:
            current = JOBS.get(job_id, {})
            return bool(current.get("cancel_requested")) or current.get("status") == "cancelled"

    def wait_or_cancel(cups_job_id: str) -> bool:
        return wait_cups(cups_job_id, cancel_event)

    def finish_cancelled() -> None:
        if not was_cancelled():
            set_status(job, "cancelled", error="任务已中断", can_continue=False)

    try:
        set_status(job, "converting", progress=5)
        convert_to_pdf(job_dir / "source" / job["filename"], document, job.get("orientation", "portrait"))
        reader = PdfReader(str(document))
        job["page_count"] = len(reader.pages)
        mode = job["mode"]
        printer = printer_config(job["printer_id"])
        capabilities = cups_capabilities(printer["cups_name"])
        job["supports_duplex"] = capabilities["duplex"]
        front_pdf, back_pdf = job_dir / "front.pdf", job_dir / "back.pdf"

        if mode == "simplex":
            set_status(job, "printing_front", progress=20)
            job["front_job_id"] = submit_document(job, document)
            if not wait_or_cancel(job["front_job_id"]):
                finish_cancelled()
                return
        elif mode == "duplex" and capabilities["duplex"]:
            set_status(job, "printing_front", progress=20)
            job["front_job_id"] = submit_document(job, document, duplex=True)
            if not wait_or_cancel(job["front_job_id"]):
                finish_cancelled()
                return
        else:
            front_count, back_count = split_pdf(document, front_pdf, back_pdf)
            if mode == "front_only":
                if front_count:
                    set_status(job, "printing_front", progress=20)
                    job["front_job_id"] = submit_document(job, front_pdf)
                    if not wait_or_cancel(job["front_job_id"]):
                        finish_cancelled()
                        return
            elif mode == "back_only":
                if back_count:
                    set_status(job, "printing_back", progress=60)
                    job["back_job_id"] = submit_document(job, back_pdf)
                    if not wait_or_cancel(job["back_job_id"]):
                        finish_cancelled()
                        return
            else:
                if front_count:
                    set_status(job, "printing_front", progress=20)
                    job["front_job_id"] = submit_document(job, front_pdf)
                    if not wait_or_cancel(job["front_job_id"]):
                        finish_cancelled()
                        return
                if back_count:
                    continue_event.clear()
                    set_status(job, "waiting_second_side", progress=50, can_continue=True,
                               message="正面打印完成，请翻面放回纸张后确认")
                    continue_event.wait()
                    if was_cancelled():
                        return
                    with JOB_LOCK:
                        if was_cancelled():
                            return
                        set_status(job, "printing_back", progress=60, can_continue=False)
                        job["back_job_id"] = submit_document(job, back_pdf)
                        save_job(job)
                    if not wait_or_cancel(job["back_job_id"]):
                        finish_cancelled()
                        return
        if was_cancelled():
            return
        set_status(job, "completed", progress=100, completed_at=now(), can_continue=False)
        cleanup_job_files(job)
    except Exception as exc:
        LOGGER.exception("任务失败 %s", job["job_id"])
        if not was_cancelled():
            set_status(job, "failed", error=str(exc), can_continue=False)


def worker() -> None:
    while not STOP.is_set():
        try:
            job_id = PENDING.get(timeout=1)
        except queue.Empty:
            continue
        with JOB_LOCK:
            job = dict(JOBS.get(job_id, {}))
        if job and job.get("status") == "pending":
            process_job(job)
        PENDING.task_done()


def public_job(job: dict) -> dict:
    result = dict(job)
    result.pop("cancel_requested", None)
    result["id"] = result["job_id"]
    result["can_continue"] = result.get("status") == "waiting_second_side"
    result["can_cancel"] = result.get("status") in {"pending", "converting", "printing_front", "waiting_second_side", "printing_back"}
    return result


@app.get("/api/health")
def health():
    return jsonify({"ok": True, "service": "printer", "ip_list": IP_LIST})


@app.post("/api/login")
def login():
    payload = request.get_json(silent=True) or {}
    username, password = str(payload.get("username", "")), str(payload.get("password", ""))
    for user in CONFIG["auth"].get("users", []):
        if user.get("username") != username:
            continue
        configured = str(user.get("password", ""))
        valid = check_password_hash(configured, password) if configured.startswith(("pbkdf2:", "scrypt:")) else configured == password
        if valid:
            token = uuid.uuid4().hex
            TOKENS[token] = username
            return jsonify({"username": username, "token": token})
    return jsonify({"error": "用户名或密码错误"}), 401


@app.get("/api/printers")
def printers():
    result = []
    for printer in CONFIG["cups"].get("printers", []):
        caps = cups_capabilities(printer["cups_name"])
        result.append({"id": str(printer["id"]), "name": printer["cups_name"],
                       "printer_name": printer["cups_name"], "location": printer.get("location", ""),
                       "type": printer.get("type", "CUPS"), "status": printer_status(printer["cups_name"]),
                       "supports_duplex": caps["duplex"], "supports_color": caps["color"],
                       "color_modes": ["color", "monochrome"],
                       "capabilities": {"duplex": caps["duplex"], "color": caps["color"]}})
    return jsonify({"printers": result})


@app.post("/api/print/calibration")
def print_calibration():
    """Queue a physical calibration sheet through the normal FIFO worker."""
    payload = request.get_json(silent=True) or {}
    printer_id = str(payload.get("printer_id", ""))
    if not printer_config(printer_id):
        return jsonify({"error": "请选择有效打印机"}), 400
    orientation = str(payload.get("orientation", "portrait")).lower()
    if orientation not in {"portrait", "landscape"}:
        return jsonify({"error": "无效的打印方向"}), 400
    color_mode = str(payload.get("color_mode", "monochrome")).lower()
    if color_mode not in {"color", "monochrome"}:
        return jsonify({"error": "无效的颜色模式"}), 400

    job_id = uuid.uuid4().hex
    job_dir = QUEUE_DIR / job_id
    source_dir = job_dir / "source"
    source_path = source_dir / "physical-calibration.pdf"
    try:
        source_dir.mkdir(parents=True, exist_ok=True)
        marks = calibration_to_pdf(source_path, orientation)
        job = {
            "job_id": job_id,
            "filename": source_path.name,
            "printer_id": printer_id,
            "copies": 1,
            "mode": "simplex",
            "color_mode": color_mode,
            "orientation": orientation,
            "is_calibration": True,
            "calibration_marks_mm": marks,
            "status": "pending",
            "phase": "pending",
            "progress": 0,
            "page_count": 1,
            "submitted_at": now(),
            "username": TOKENS.get(request.headers.get("Authorization", "")[7:], "unknown"),
        }
        save_job(job)
        JOB_CANCEL_EVENTS[job_id] = threading.Event()
        JOB_CONTINUE_EVENTS[job_id] = threading.Event()
        PENDING.put(job_id)
        return jsonify({
            "success": True,
            "job_id": job_id,
            "job": public_job(job),
            "message": "物理校准页已加入打印队列",
        })
    except Exception as exc:
        LOGGER.exception("创建物理校准任务失败")
        shutil.rmtree(job_dir, ignore_errors=True)
        return jsonify({"error": str(exc)}), 400


@app.post("/api/print/upload")
def upload():
    files = request.files.getlist("files")
    if not files or all(not item.filename for item in files):
        return jsonify({"error": "未找到文件"}), 400
    files = [item for item in files if item.filename]
    mode = str(request.form.get("mode", request.form.get("print_mode", "simplex"))).lower()
    mode = {"1": "simplex", "2": "duplex"}.get(mode, mode)
    if mode not in {"simplex", "duplex", "front_only", "back_only"}:
        return jsonify({"error": "无效的打印模式"}), 400
    printer_id = str(request.form.get("printer_id", ""))
    if not printer_config(printer_id):
        return jsonify({"error": "请选择有效打印机"}), 400
    try:
        copies = max(1, min(99, int(request.form.get("copies", 1))))
    except ValueError:
        return jsonify({"error": "打印份数无效"}), 400
    try:
        raw_options = json.loads(request.form.get("file_options", "[]"))
        if not isinstance(raw_options, list):
            raise ValueError("文件属性必须是数组")
        options_by_index = {}
        for option in raw_options:
            if not isinstance(option, dict) or not isinstance(option.get("index"), int):
                raise ValueError("文件属性格式无效")
            index = option["index"]
            if index < 0 or index >= len(files) or index in options_by_index:
                raise ValueError("文件属性索引无效或重复")
            color_mode = str(option.get("color_mode", "color")).lower()
            if color_mode not in {"color", "monochrome"}:
                raise ValueError("无效的颜色模式: " + color_mode)
            options_by_index[index] = color_mode
        if raw_options and len(options_by_index) != len(files):
            raise ValueError("每个文件都必须提供颜色属性")
    except (TypeError, ValueError, json.JSONDecodeError) as exc:
        return jsonify({"error": str(exc)}), 400

    allowed_extensions = {".pdf", ".png", ".webp", ".jpg", ".jpeg", ".gif", ".bmp", ".tif", ".tiff",
                          ".txt", ".md", ".markdown", ".tex", ".latex", ".doc", ".docx"}
    for item in files:
        extension = Path(item.filename).suffix.lower()
        if extension not in allowed_extensions:
            return jsonify({"error": "不支持的文件类型: " + extension}), 400

    created = []
    created_ids = []
    batch_id = uuid.uuid4().hex
    try:
        for index, item in enumerate(files):
            job_id = uuid.uuid4().hex
            created_ids.append(job_id)
            source_dir = QUEUE_DIR / job_id / "source"
            source_dir.mkdir(parents=True, exist_ok=True)
            safe_name = Path(item.filename).name
            item.save(source_dir / safe_name)
            job = {"job_id": job_id, "filename": safe_name, "printer_id": printer_id,
                   "copies": copies, "mode": mode, "color_mode": options_by_index.get(index, "color"),
                   "batch_id": batch_id, "batch_index": index,
                   "orientation": "landscape" if str(request.form.get("orientation", request.form.get("flat_mode", "portrait"))).lower() in {"landscape", "v"} else "portrait",
                   "status": "pending", "phase": "pending", "progress": 0, "page_count": 0,
                   "submitted_at": now(), "username": TOKENS.get(request.headers.get("Authorization", "")[7:], "unknown")}
            save_job(job)
            JOB_CANCEL_EVENTS[job_id] = threading.Event()
            JOB_CONTINUE_EVENTS[job_id] = threading.Event()
            created.append(public_job(job))
        for job in created:
            PENDING.put(job["job_id"])
        return jsonify({"success": True, "job_ids": [item["job_id"] for item in created], "jobs": created,
                        "message": f"成功上传 {len(created)} 个文件并加入打印队列"})
    except Exception as exc:
        with JOB_LOCK:
            for job_id in created_ids:
                shutil.rmtree(QUEUE_DIR / job_id, ignore_errors=True)
                JOBS.pop(job_id, None)
                JOB_CANCEL_EVENTS.pop(job_id, None)
                JOB_CONTINUE_EVENTS.pop(job_id, None)
        return jsonify({"error": str(exc)}), 400


@app.get("/api/print/jobs")
def get_jobs():
    with JOB_LOCK:
        jobs = [public_job(item) for item in JOBS.values()]
    jobs.sort(key=lambda item: item.get("submitted_at", ""), reverse=True)
    return jsonify({"jobs": jobs})


@app.post("/api/print/jobs/<job_id>/continue")
def continue_job(job_id: str):
    with JOB_LOCK:
        job = JOBS.get(job_id)
        if not job:
            return jsonify({"error": "任务不存在"}), 404
        if job.get("status") != "waiting_second_side":
            return jsonify({"error": "任务不在等待第二面的状态"}), 409
        if job.get("continue_requested"):
            return jsonify({"error": "第二面已经确认，不能重复确认"}), 409
        job["continue_requested"] = True
        save_job(job)
    JOB_CONTINUE_EVENTS.setdefault(job_id, threading.Event()).set()
    return jsonify({"success": True, "message": "已允许打印第二面"})


@app.post("/api/print/jobs/<job_id>/cancel")
def cancel_job(job_id: str):
    with JOB_LOCK:
        job = JOBS.get(job_id)
        if not job:
            return jsonify({"error": "任务不存在"}), 404
        if job.get("status") in {"completed", "cancelled", "failed", "interrupted"}:
            return jsonify({"error": "任务已经结束，不能恢复"}), 409
        job["cancel_requested"] = True
        cups_jobs = [value for value in (job.get("front_job_id"), job.get("back_job_id")) if value]
        set_status(job, "cancelled", error="任务已中断", can_continue=False)
    for cups_job in cups_jobs:
        run_command(["cancel", cups_job])
    JOB_CANCEL_EVENTS.setdefault(job_id, threading.Event()).set()
    JOB_CONTINUE_EVENTS.setdefault(job_id, threading.Event()).set()
    return jsonify({"success": True, "message": "任务已中断且不可恢复"})


@app.get("/api/print/jobs/clear_completed")
def clear_completed():
    removed = 0
    with JOB_LOCK:
        for job_id, job in list(JOBS.items()):
            if job.get("status") in {"completed", "cancelled", "failed", "interrupted"}:
                shutil.rmtree(QUEUE_DIR / job_id, ignore_errors=True)
                JOBS.pop(job_id, None)
                JOB_CANCEL_EVENTS.pop(job_id, None)
                JOB_CONTINUE_EVENTS.pop(job_id, None)
                removed += 1
    return jsonify({"success": True, "deleted": removed})


@app.route("/api/print/read_context", methods=["GET", "POST"])
@app.route("/api/print/write_context", methods=["GET", "POST"])
def removed_windows_api():
    return jsonify({"error": "Windows 批处理接口已移除，请使用 CUPS 打印配置"}), 410


if __name__ == "__main__":
    from waitress import serve
    load_jobs()
    threading.Thread(target=worker, name="print-worker", daemon=True).start()
    serve(app, host=CONFIG["server"].get("host", "0.0.0.0"), port=int(CONFIG["server"].get("port", 5181)), threads=4)
