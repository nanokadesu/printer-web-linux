<template>
  <div class="printer-select">
    <label class="label" for="printer">选择打印机</label>
    
    <div class="select-wrapper">
      <select 
        id="printer" 
        class="input printer-input" 
        v-model="selectedPrinterId"
        @change="onPrinterChange"
      >
        <option value="">请选择打印机</option>
        <option 
          v-for="printer in printers" 
          :key="printer.id" 
          :value="printer.id"
        >
          {{ printer.name }} ({{ printer.status === 'online' ? '在线' : '离线' }})
        </option>
      </select>
      
      <div class="select-icon">
        <svg 
          viewBox="0 0 24 24" 
          fill="none" 
          xmlns="http://www.w3.org/2000/svg"
        >
          <path 
            d="M6 9L12 15L18 9" 
            stroke="currentColor" 
            stroke-width="2" 
            stroke-linecap="round" 
            stroke-linejoin="round"
          />
        </svg>
      </div>
    </div>
    
    <div v-if="selectedPrinter" class="printer-info card">
      <div class="printer-info-header">
        <h4 class="printer-info-title">{{ selectedPrinter.name }}</h4>
        <span 
          class="printer-status" 
          :class="{'status-online': selectedPrinter.status === 'online', 'status-offline': selectedPrinter.status === 'offline'}"
        >
          {{ selectedPrinter.status === 'online' ? '在线' : '离线' }}
        </span>
      </div>
      
      <div class="printer-info-body">
        <div class="info-row">
          <span class="info-label">位置:</span>
          <span class="info-value">{{ selectedPrinter.location || '未设置' }}</span>
        </div>
        
        <div class="info-row">
          <span class="info-label">类型:</span>
          <span class="info-value">{{ getPrinterTypeLabel(selectedPrinter.type) }}</span>
        </div>
        
        <div class="info-row">
          <span class="info-label">状态:</span>
          <span class="info-value">{{ selectedPrinter.status_message || '正常' }}</span>
        </div>
        
        <div class="info-row">
          <span class="info-label">队列任务:</span>
          <span class="info-value">{{ selectedPrinter.queue_count || 0 }} 个</span>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, watch, defineProps, defineEmits } from 'vue'

const props = defineProps({
  printers: {
    type: Array,
    required: true
  },
  modelValue: {
    type: String,
    required: false,
    default: ''
  }
})

const emit = defineEmits(['update:modelValue', 'change'])

const selectedPrinterId = ref(props.modelValue)
const selectedPrinter = ref(null)

// 监听打印机ID变化
watch(
  () => selectedPrinterId.value,
  (newId) => {
    if (newId) {
      selectedPrinter.value = props.printers.find(printer => printer.id === newId) || null
    } else {
      selectedPrinter.value = null
    }
    emit('update:modelValue', newId)
    emit('change', newId)
  },
  { immediate: true }
)

// 监听prop变化
watch(
  () => props.modelValue,
  (newValue) => {
    if (newValue !== selectedPrinterId.value) {
      selectedPrinterId.value = newValue
    }
  }
)

// 打印机类型标签
const getPrinterTypeLabel = (type) => {
  return type;
}

// 打印机变化事件
const onPrinterChange = () => {
  // 由watch处理
}
</script>

<style scoped>
.printer-select {
  margin-bottom: 24px;
}

.select-wrapper {
  position: relative;
  margin-bottom: 12px;
}

.printer-input {
  appearance: none;
  padding-right: 40px;
  background-color: white;
}

.select-icon {
  position: absolute;
  right: 12px;
  top: 50%;
  transform: translateY(-50%);
  pointer-events: none;
}

.select-icon svg {
  width: 18px;
  height: 18px;
  color: var(--text-light);
}

.printer-info {
  padding: 16px;
  margin-top: 12px;
  border: 1px solid var(--border-color);
}

.printer-info-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 12px;
}

.printer-info-title {
  font-size: 16px;
  font-weight: 600;
  color: var(--text-color);
}

.printer-status {
  padding: 4px 8px;
  border-radius: 4px;
  font-size: 12px;
  font-weight: 500;
}

.status-online {
  background-color: rgba(82, 196, 26, 0.1);
  color: var(--success-color);
}

.status-offline {
  background-color: rgba(250, 173, 20, 0.1);
  color: var(--warning-color);
}

.printer-info-body {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(200px, 1fr));
  gap: 12px;
}

.info-row {
  display: flex;
  flex-direction: column;
}

.info-label {
  font-size: 12px;
  color: var(--text-light);
  margin-bottom: 4px;
}

.info-value {
  font-size: 14px;
  color: var(--text-color);
  font-weight: 500;
}
</style>