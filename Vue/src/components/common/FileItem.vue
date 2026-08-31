<template>
  <div class="file-item">
    <div class="file-preview">
      <img :src="file.previewUrl" :alt="file.name" class="preview-image">
      <div v-if="file.type === 'application/pdf'" class="pdf-icon">
        <svg 
          viewBox="0 0 24 24" 
          fill="none" 
          xmlns="http://www.w3.org/2000/svg"
        >
          <path 
            d="M21 15C21 15.5304 20.7893 16.0391 20.4142 16.4142C20.0391 16.7893 19.5304 17 19 17H7L3 21V5C3 4.46957 3.21071 3.96086 3.58579 3.58579C3.96086 3.21071 4.46957 3 5 3H19C19.5304 3 20.0391 3.21071 20.4142 3.58579C20.7893 3.96086 21 4.46957 21 5V15Z" 
            stroke="currentColor" 
            stroke-width="2" 
            stroke-linecap="round" 
            stroke-linejoin="round"
          />
          <path 
            d="M17 21V19C17 18.4696 16.7893 17.9609 16.4142 17.5858C16.0391 17.2107 15.5304 17 15 17H9" 
            stroke="currentColor" 
            stroke-width="2" 
            stroke-linecap="round" 
            stroke-linejoin="round"
          />
          <path 
            d="M7 3V8H15" 
            stroke="currentColor" 
            stroke-width="2" 
            stroke-linecap="round" 
            stroke-linejoin="round"
          />
        </svg>
      </div>
    </div>
    
    <div class="file-info">
      <div class="file-name">{{ file.name }}</div>
      <div class="file-meta">
        <span class="file-size">{{ formatFileSize(file.size) }}</span>
        <span class="file-type">{{ file.type || '文件' }}</span>
      </div>
    </div>
    
    <div class="file-actions">
      <button 
        class="action-btn remove-btn" 
        @click="onRemove"
        aria-label="移除文件"
      >
        <svg 
          class="action-icon" 
          viewBox="0 0 24 24" 
          fill="none" 
          xmlns="http://www.w3.org/2000/svg"
        >
          <path 
            d="M6 19C6 20.1046 6.89543 21 8 21H16C17.1046 21 18 20.1046 18 19V7H6V19Z" 
            stroke="currentColor" 
            stroke-width="2" 
            stroke-linecap="round" 
            stroke-linejoin="round"
          />
          <path 
            d="M19 4H15.5L14.5 3H9.5L8.5 4H5V6H19V4Z" 
            stroke="currentColor" 
            stroke-width="2" 
            stroke-linecap="round" 
            stroke-linejoin="round"
          />
        </svg>
      </button>
    </div>
  </div>
</template>

<script setup>
import { formatFileSize } from '../../utils/helpers.js'

const props = defineProps({
  file: {
    type: Object,
    required: true
  }
})

const emit = defineEmits(['remove'])

const onRemove = () => {
  emit('remove', props.file)
}
</script>

<style scoped>
.file-item {
  display: flex;
  align-items: center;
  padding: 12px 16px;
  border-radius: 8px;
  background-color: white;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.05);
  transition: var(--transition-default);
  margin-bottom: 12px;
}

.file-item:hover {
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.08);
}

.file-preview {
  width: 40px;
  height: 40px;
  margin-right: 16px;
  flex-shrink: 0;
  position: relative;
}

.preview-image {
  width: 100%;
  height: 100%;
  object-fit: cover;
  border-radius: 4px;
}

.pdf-icon {
  width: 100%;
  height: 100%;
  display: flex;
  align-items: center;
  justify-content: center;
  background-color: var(--primary-light);
  border-radius: 4px;
}

.pdf-icon svg {
  width: 24px;
  height: 24px;
  color: var(--primary-color);
}

.file-info {
  flex-grow: 1;
  min-width: 0;
}

.file-name {
  font-weight: 500;
  color: var(--text-color);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  margin-bottom: 4px;
}

.file-meta {
  display: flex;
  font-size: 12px;
  color: var(--text-light);
  gap: 12px;
}

.file-actions {
  display: flex;
  align-items: center;
}

.action-btn {
  background: none;
  border: none;
  cursor: pointer;
  padding: 4px;
  border-radius: 4px;
  transition: var(--transition-default);
  display: flex;
  align-items: center;
  justify-content: center;
}

.action-btn:hover {
  background-color: var(--primary-light);
}

.remove-btn:hover {
  background-color: rgba(255, 77, 79, 0.1);
}

.remove-btn:hover .action-icon {
  color: var(--error-color);
}

.action-icon {
  width: 18px;
  height: 18px;
  color: var(--text-light);
  transition: var(--transition-default);
}
</style>