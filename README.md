# GreenPrint Linux 打印系统

这是基于 Linux CUPS 的文件打印服务。前端使用 Vue/Vite，后端使用 Python/Flask，文件在后端转换为 A4 PDF 后交给打印机驱动处理。

## 访问地址

前端统一使用 `5173` 端口：

- `http://192.168.15.221:5173/`
- `http://10.144.144.75:5173/`

前端优先探测当前网页使用的 IP，再按 `VITE_IP_LIST` 故障切换。每个候选后端连续探测两次，全部失败时返回 HTTP 400。

## 目录结构

```text
Python/WSGI/main.py       Python/CUPS 后端
Python/WSGI/config.yaml   后端配置、用户和打印机
Vue/                      Vue 前端
Vue/.env                  前端端口、API 和 IP 配置
Queue/                    上传文件、转换文件和任务元数据
deploy/                   systemd 服务文件
```

后端监听 `5181`，前端监听 `5173`。浏览器只访问 `5173`，`/api` 由 Vite 代理到后端。

## 支持的文件

- PDF：优先直接交给 CUPS；失败时可按配置进行高 DPI 栅格化。
- PNG、WebP、JPG、JPEG、GIF、BMP、TIFF：使用 OpenCV 三次立方等比适配并转换为 A4 PDF。图片左右各保留 2%、上下各保留 4% 硬件修正区，按宽高两个方向中更严格的缩放比例统一缩放，整张图片在安全框内居中且不裁剪；多页 TIFF 每帧生成一页。
- TXT：使用 A4 页面和四周 `25.4mm` 页边距，支持中文和长行换行。
- Markdown：使用 Pandoc + XeLaTeX 导出，支持中文、表格、代码块和 LaTeX 公式。
- LaTeX：使用 XeLaTeX 编译后打印。
- DOC、DOCX：使用 LibreOffice headless 转换后打印。

## 打印模式

- **单面打印**：打印完整文档。
- **自动/手动双面**：驱动支持双面时直接使用 CUPS 双面选项；不支持时先打印奇数页，等待网页确认翻面后再打印偶数页。
- **仅正面**：只打印奇数页。
- **仅反面**：只打印偶数页。

当前打印机 `HP_DeskJet_1200_series` 不支持自动双面，因此双面任务会进入 `等待翻面` 状态。等待期间队列工作线程暂停；可以中断任务，但中断后的上下文不能恢复。

每个上传文件可以独立选择彩色或黑白。批量上传会按文件顺序生成独立任务，单工作线程只在上一份任务结束后处理下一份，不会同时向 CUPS 提交多份内容。

## 配置

后端配置文件：`Python/WSGI/config.yaml`

主要配置：

```yaml
server:
  host: 0.0.0.0
  port: 5181
ip_list: [192.168.15.221, 10.144.144.75]
auth:
  enabled: true
  users:
    - username: admin
      password: change-me
cups:
  printers:
    - id: 1
      cups_name: HP_DeskJet_1200_series
```

修改配置后重启后端：

```bash
sudo systemctl restart printer-backend.service
```

前端配置文件：`Vue/.env`

```dotenv
VITE_FRONTEND_PORT=5173
VITE_API_PORT=5181
VITE_API_PREFIX=/api
VITE_IP_LIST=192.168.15.221,10.144.144.75
VITE_IP_PROBE_TIMEOUT_MS=1500
```

修改前端配置后重启前端：

```bash
sudo systemctl restart printer-frontend.service
```

## 部署

目标环境为 Python 3.9.2，虚拟环境位于 `/home/orangepi/Code/.env`。

### 1. 安装系统依赖

```bash
sudo apt update
sudo apt install -y cups hplip printer-driver-hpcups avahi-daemon \
  pandoc texlive-xetex texlive-latex-extra texlive-lang-chinese \
  texlive-fonts-recommended lmodern libreoffice
```

确认打印机已被 CUPS 识别：

```bash
lpstat -p -d
lpoptions -p HP_DeskJet_1200_series -l
```

### 2. 安装 Python 依赖

```bash
/home/orangepi/Code/.env/bin/pip install -r Python/requirements.txt
```

### 3. 安装并启动服务

```bash
sudo cp deploy/printer-backend.service /etc/systemd/system/
sudo cp deploy/printer-frontend.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now printer-backend.service printer-frontend.service
```

前端依赖首次部署时安装：

```bash
cd Vue
npm install
```

### 4. 检查服务

```bash
systemctl status printer-backend.service printer-frontend.service
curl http://127.0.0.1:5181/api/health
curl http://192.168.15.221:5173/api/health
ss -ltnp | grep -E ':5173|:5181'
```

日志查看：

```bash
journalctl -u printer-backend.service -f
journalctl -u printer-frontend.service -f
```

## 队列和故障处理

每个任务保存在 `Queue/<job_id>/`，包含源文件、转换后的 PDF、正反面 PDF 和 `job.json`。服务重启时，未完成的转换、打印和等待翻面任务会被标记为 `interrupted`，不会自动恢复。

取消任务：

```bash
curl -X POST http://127.0.0.1:5181/api/print/jobs/<job_id>/cancel \
  -H 'Authorization: Bearer <token>'
```

清理已结束任务：

```bash
curl http://127.0.0.1:5181/api/print/jobs/clear_completed \
  -H 'Authorization: Bearer <token>'
```

如果打印机离线，先检查：

```bash
lpstat -p HP_DeskJet_1200_series
lpstat -o
sudo systemctl restart cups
```

Windows 的 C# 程序、PowerShell、批处理自定义打印接口已经移除，打印行为统一由 `config.yaml` 和 CUPS 控制。

## 物理校准

在打印设置中点击“打印物理校准页”。校准页会从纸张四边绘制 `0/5/10/15/20 mm` 刻度和中心十字线，并按正常 FIFO 队列提交到 CUPS。打印完成后直接用尺子测量纸张实际边缘到最外侧可见刻线的距离；该距离就是打印机对应方向的硬件不可打印偏移。

将测量值换算为比例后写入 `Python/WSGI/config.yaml`：

```yaml
conversion:
  image_left_margin_ratio: 0.02
  image_right_margin_ratio: 0.02
  image_top_margin_ratio: 0.04
  image_bottom_margin_ratio: 0.04
```

左、右比例使用对应测量毫米数除以 A4 宽度（210 mm），上、下比例使用对应测量毫米数除以 A4 高度（297 mm）。旧的 `image_horizontal_margin_ratio` / `image_vertical_margin_ratio` 仍可作为四边配置缺省值。修改配置后重启 `printer-backend.service`；校准页本身不会自动修改配置，也不会绕过队列中的其他任务。
