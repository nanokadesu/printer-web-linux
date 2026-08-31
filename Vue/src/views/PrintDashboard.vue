<template>
  <main class="page">
    <header class="header"><div><h1>GreenPrint 打印</h1><p>Linux CUPS 队列</p></div><div class="header-actions"><span>{{ username }}</span><button class="outline" @click="logout">退出</button></div></header>

    <section class="layout">
      <aside class="panel"><div class="panel-title"><h2>打印机</h2><button class="icon-button" title="刷新打印机" @click="loadPrinters">↻</button></div>
        <div v-for="printer in printers" :key="printer.id" class="printer" :class="printer.status"><div><strong>{{ printer.name }}</strong><small>{{ printer.location || '未设置位置' }}</small></div><span>{{ printer.status === 'online' ? '在线' : '离线' }}</span></div>
        <p v-if="!printers.length" class="muted">没有可用打印机</p>
      </aside>

      <div class="content">
        <section class="panel"><h2>上传文件</h2><FileDropzone @files-selected="addFiles" />
          <div v-if="files.length" class="files-grid"><article v-for="file in files" :key="file.uid" class="file-item">
            <div class="file-summary"><img :src="file.previewUrl" alt="" /><span><strong>{{ file.name }}</strong><small>{{ formatFileSize(file.size) }}</small></span><button class="icon-button remove-file" title="移除文件" aria-label="移除文件" @click="removeFile(file)">×</button></div>
            <fieldset><legend>颜色模式</legend><div class="color-mode"><label :class="{ active: file.colorMode === 'color' }"><input v-model="file.colorMode" type="radio" value="color" />彩色</label><label :class="{ active: file.colorMode === 'monochrome' }"><input v-model="file.colorMode" type="radio" value="monochrome" />黑白</label></div></fieldset>
          </article></div>
        </section>

        <section class="panel"><h2>打印设置</h2><div class="controls"><label>打印机<select v-model="printerId"><option value="">请选择打印机</option><option v-for="printer in printers" :key="printer.id" :value="printer.id">{{ printer.name }}{{ printer.status === 'online' ? '' : ' (离线)' }}</option></select></label>
          <label>份数<input v-model.number="copies" type="number" min="1" max="99" /></label>
          <label>方向<select v-model="orientation"><option value="portrait">纵向</option><option value="landscape">横向</option></select></label>
          <label>打印模式<select v-model="mode"><option value="simplex">单面打印</option><option value="duplex">自动/手动双面</option><option value="front_only">仅正面（奇数页）</option><option value="back_only">仅反面（偶数页）</option></select></label>
        </div>
        <div v-if="selectedPrinter" class="capability" :class="{ warn: !selectedPrinter.supports_duplex }">{{ selectedPrinter.supports_duplex ? '驱动支持自动双面' : '驱动不支持自动双面，双面任务需要手动翻面' }}</div>
        <div class="actions"><button :disabled="!canSubmit || submitting || calibrationSubmitting" @click="submit">{{ submitting ? '提交中...' : '提交打印' }}</button><button class="outline" :disabled="!files.length || submitting || calibrationSubmitting" @click="clearFiles">清空选择</button><button class="outline" :disabled="!canCalibrate || submitting || calibrationSubmitting" @click="printCalibration">{{ calibrationSubmitting ? '校准页提交中...' : '打印物理校准页' }}</button></div></section>

        <section class="panel"><div class="panel-title"><h2>打印队列</h2><div><button class="outline compact" @click="clearCompleted">清理已结束</button><button class="icon-button" title="刷新队列" @click="loadJobs">↻</button></div></div>
          <div v-if="jobs.length" class="jobs"><article v-for="job in jobs" :key="job.job_id" class="job"><div class="job-main"><strong>{{ job.filename }}</strong><small>{{ job.printer_name || job.printer_id }} · {{ job.copies }} 份 · {{ job.page_count || '?' }} 页 · {{ colorModeText(job.color_mode) }}</small></div><span class="status" :class="job.status">{{ statusText(job) }}</span><div class="job-progress"><div :style="{ width: `${job.progress || 0}%` }"></div></div><div class="job-actions"><button v-if="job.can_continue" @click="continueJob(job)">打印第二面</button><button class="outline" v-if="job.can_cancel" @click="cancelJob(job)">中断</button></div><p v-if="job.error" class="error">{{ job.error }}</p></article></div>
          <p v-else class="muted">当前没有打印任务</p>
        </section>
      </div>
    </section>
  </main>
</template>

<script setup>
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { useRouter } from 'vue-router'
import FileDropzone from '../components/common/FileDropzone.vue'
import { removeToken, getUsername } from '../utils/auth'
import { createFilePreview, formatFileSize, isValidFileType } from '../utils/helpers'
import { cancelPrintJob, clearCompletedJobs, continuePrintJob, getActiveJobs, getPrinters, printCalibrationPage, uploadPrintFile } from '../services/printerService'

const router = useRouter(); const username = ref(getUsername() || '用户'); const files = ref([]); const printers = ref([]); const jobs = ref([]); const printerId = ref(''); const copies = ref(1); const orientation = ref('portrait'); const mode = ref('simplex'); const submitting = ref(false); const calibrationSubmitting = ref(false); let timer
const selectedPrinter = computed(() => printers.value.find((printer) => printer.id === printerId.value))
const canSubmit = computed(() => files.value.length > 0 && printerId.value && selectedPrinter.value?.status === 'online')
const canCalibrate = computed(() => printerId.value && selectedPrinter.value?.status === 'online')
const loadPrinters = async () => { try { const result = await getPrinters(); printers.value = (result.printers || []).map((item) => ({ ...item, id: String(item.id) })); if (!printerId.value) printerId.value = printers.value.find((item) => item.status === 'online')?.id || '' } catch (error) { ElMessage.error(error.error || '获取打印机失败') } }
const loadJobs = async () => { try { jobs.value = (await getActiveJobs()).jobs || [] } catch (error) { ElMessage.error(error.error || '获取队列失败') } }
const addFiles = async (selected) => { for (const file of selected) { if (!isValidFileType(file)) { ElMessage.warning(`不支持的文件类型: ${file.name}`); continue } if (files.value.some((item) => item.name === file.name && item.size === file.size)) continue; file.uid = `${Date.now()}-${Math.random()}`; file.previewUrl = await createFilePreview(file); file.colorMode = 'color'; files.value.push(file) } }
const removeFile = (file) => { if (file.previewUrl?.startsWith('blob:')) URL.revokeObjectURL(file.previewUrl); files.value = files.value.filter((item) => item.uid !== file.uid) }
const clearFiles = () => { files.value.forEach(removeFile); files.value = [] }
const submit = async () => { if (!canSubmit.value) return; const form = new FormData(); files.value.forEach((file) => form.append('files', file)); form.append('file_options', JSON.stringify(files.value.map((file, index) => ({ index, color_mode: file.colorMode })))); form.append('printer_id', printerId.value); form.append('copies', String(copies.value)); form.append('orientation', orientation.value); form.append('mode', mode.value); submitting.value = true; try { const result = await uploadPrintFile(form); ElMessage.success(result.message || '任务已加入队列'); clearFiles(); await loadJobs() } catch (error) { ElMessage.error(error.error || '提交打印失败') } finally { submitting.value = false } }
const printCalibration = async () => { if (!canCalibrate.value) return; calibrationSubmitting.value = true; try { const result = await printCalibrationPage({ printer_id: printerId.value, orientation: orientation.value, color_mode: 'monochrome' }); ElMessage.success(result.message || '物理校准页已加入队列'); await loadJobs() } catch (error) { ElMessage.error(error.error || '校准页提交失败') } finally { calibrationSubmitting.value = false } }
const continueJob = async (job) => { try { await continuePrintJob(job.job_id); ElMessage.success('已提交第二面'); await loadJobs() } catch (error) { ElMessage.error(error.error || '无法继续任务') } }
const cancelJob = async (job) => { try { await cancelPrintJob(job.job_id); ElMessage.success('任务已中断且不可恢复'); await loadJobs() } catch (error) { ElMessage.error(error.error || '无法中断任务') } }
const clearCompleted = async () => { try { await clearCompletedJobs(); await loadJobs() } catch (error) { ElMessage.error(error.error || '清理失败') } }
const statusText = (job) => ({ pending: '等待中', converting: '转换中', printing_front: '打印正面', waiting_second_side: '等待翻面', printing_back: '打印反面', completed: '已完成', cancelled: '已中断', failed: '失败', interrupted: '上下文失效' }[job.status] || job.status)
const colorModeText = (modeValue) => modeValue === 'monochrome' ? '黑白' : '彩色'
const logout = () => { removeToken(); router.push('/login') }
onMounted(async () => { await loadPrinters(); await loadJobs(); timer = setInterval(loadJobs, 3000) })
onBeforeUnmount(() => { clearInterval(timer); clearFiles() })
</script>

<style scoped>
.page { min-height: 100vh; background: #f4f8f5; color: #1e3327; padding: 24px; } .header,.panel-title,.header-actions,.actions,.job-actions { display: flex; align-items: center; justify-content: space-between; gap: 12px; } .header { max-width: 1280px; margin: 0 auto 24px; } h1,h2,p { margin: 0; } h1 { color: #1f7049; font-size: 28px; } h2 { font-size: 18px; } .header p,.muted,small { color: #668071; } .header-actions { font-size: 14px; } .layout { max-width: 1280px; margin: auto; display: grid; grid-template-columns: 280px 1fr; gap: 20px; align-items: start; } .content { display: grid; gap: 20px; } .panel { background: white; border: 1px solid #d7e6dc; border-radius: 8px; padding: 20px; box-shadow: 0 4px 14px #2148320d; } .panel h2 { margin-bottom: 16px; } .printer { display: flex; justify-content: space-between; gap: 10px; padding: 12px 0; border-bottom: 1px solid #edf2ee; } .printer strong,.printer small,.job-main strong,.job-main small { display: block; } .printer span { color: #b42318; font-size: 13px; } .printer.online span { color: #18794e; } .controls { display: grid; grid-template-columns: repeat(4, 1fr); gap: 14px; } label { display: grid; gap: 6px; color: #345340; font-size: 14px; } input,select { min-height: 40px; padding: 8px 10px; border: 1px solid #c6d9cc; border-radius: 6px; background: #fff; font-size: 15px; } button { min-height: 38px; padding: 8px 16px; border: 0; border-radius: 6px; background: #2f8f62; color: #fff; font-weight: 600; cursor: pointer; } button:disabled { opacity: .5; cursor: not-allowed; } button.outline { color: #2f8f62; background: white; border: 1px solid #9bc6ad; } .compact { min-height: 32px; padding: 5px 10px; font-size: 12px; } .icon-button { min-height: 30px; padding: 2px 8px; font-size: 18px; }
.files-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); gap: 12px; margin-top: 16px; } .file-item { min-width: 0; padding: 12px; border: 1px solid #dce9e0; border-radius: 6px; background: #fbfdfb; } .file-summary { display: grid; grid-template-columns: 48px minmax(0, 1fr) 32px; align-items: center; gap: 10px; min-height: 48px; } .file-summary img { width: 48px; height: 48px; border-radius: 4px; object-fit: cover; background: #edf2ee; } .file-summary span,.file-summary strong { min-width: 0; } .file-summary strong { display: block; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; font-size: 14px; } .file-summary small { display: block; margin-top: 3px; } .remove-file { align-self: start; width: 32px; padding: 1px; } fieldset { min-width: 0; margin: 12px 0 0; padding: 0; border: 0; } legend { margin-bottom: 6px; color: #60756a; font-size: 12px; } .color-mode { display: grid; grid-template-columns: 1fr 1fr; height: 36px; border: 1px solid #b9d1c1; border-radius: 6px; overflow: hidden; } .color-mode label { display: flex; align-items: center; justify-content: center; cursor: pointer; background: #fff; color: #345340; font-size: 13px; } .color-mode label + label { border-left: 1px solid #b9d1c1; } .color-mode label.active { background: #2f8f62; color: #fff; font-weight: 600; } .color-mode input { position: absolute; width: 1px; height: 1px; min-height: 0; padding: 0; opacity: 0; }
.capability { margin-top: 16px; padding: 10px; color: #18794e; background: #edf8f1; border-radius: 6px; font-size: 13px; } .capability.warn { color: #8a5a00; background: #fff8e6; } .actions { margin-top: 18px; justify-content: flex-start; } .jobs { display: grid; gap: 10px; } .job { display: grid; grid-template-columns: 1fr auto; gap: 8px 12px; padding: 14px; border: 1px solid #e2ece5; border-radius: 6px; } .job-main small { margin-top: 4px; } .status { align-self: start; padding: 4px 8px; border-radius: 4px; font-size: 12px; background: #edf2ee; } .status.waiting_second_side { color: #8a5a00; background: #fff8e6; } .status.completed { color: #18794e; background: #edf8f1; } .status.failed,.status.cancelled,.status.interrupted { color: #b42318; background: #fff1f0; } .job-progress { grid-column: 1 / -1; height: 6px; background: #e8efe9; border-radius: 3px; overflow: hidden; } .job-progress div { height: 100%; background: #2f8f62; transition: width .2s; } .job-actions { grid-column: 1 / -1; justify-content: flex-end; } .error { grid-column: 1 / -1; color: #b42318; font-size: 13px; } @media (max-width: 900px) { .layout { grid-template-columns: 1fr; } .controls { grid-template-columns: repeat(2, 1fr); } } @media (max-width: 520px) { .page { padding: 12px; } .controls,.files-grid { grid-template-columns: 1fr; } .header { align-items: flex-start; flex-direction: column; } }
</style>
