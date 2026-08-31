<template>
  <div class="dropzone" :class="{ dragging: isDragging }" @click="input?.click()" @dragover.prevent="isDragging = true" @dragleave.prevent="isDragging = false" @drop.prevent="drop">
    <input ref="input" type="file" multiple :accept="accept" @change="select" />
    <strong>拖放文件到此处，或点击选择</strong>
    <span>PDF、PNG、WebP、JPG、JPEG、TIFF、TXT、Markdown、LaTeX、DOC、DOCX</span>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import { allowedExtensions } from '../../utils/helpers'

const emit = defineEmits(['files-selected'])
const input = ref(null)
const isDragging = ref(false)
const accept = allowedExtensions.join(',')
const emitFiles = (files) => { if (files?.length) emit('files-selected', Array.from(files)) }
const select = (event) => { emitFiles(event.target.files); event.target.value = '' }
const drop = (event) => { isDragging.value = false; emitFiles(event.dataTransfer.files) }
</script>

<style scoped>
.dropzone { border: 2px dashed #b7d8c6; border-radius: 8px; padding: 34px 20px; display: grid; gap: 8px; text-align: center; cursor: pointer; background: #f5fbf7; }
.dropzone.dragging, .dropzone:hover { border-color: #2f8f62; background: #e8f5ef; }
.dropzone input { display: none; }
.dropzone strong { color: #183b2a; font-size: 16px; }
.dropzone span { color: #60756a; font-size: 13px; }
</style>
