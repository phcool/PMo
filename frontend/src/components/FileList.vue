<template>
  <div class="files-sidebar" :class="{ 
    'hidden': !showFilesList, 
    'active': showFilesList,
    'pdf-active': showPdf && currentPdfUrl
  }">
    <div v-if="currentPdfUrl && showPdf" class="pdf-view">
      <div class="pdf-header">
        <h3 class="pdf-title" :title="currentFileName">{{ currentFileName }}</h3>
        <div class="pdf-controls">
          <a :href="currentPdfUrl" target="_blank" class="pdf-control-btn" title="Open in new window">
            <svg class="icon-svg" viewBox="0 0 24 24">
              <path d="M14,3V5H17.59L7.76,14.83L9.17,16.24L19,6.41V10H21V3M19,19H5V5H12V3H5C3.89,3 3,3.9 3,5V19A2,2 0 0,0 5,21H19A2,2 0 0,0 21,19V12H19V19Z" />
            </svg>
          </a>
          <button class="close-pdf-btn" @click="closePdf">
            <svg class="icon-svg" viewBox="0 0 24 24">
              <path d="M19,6.41L17.59,5L12,10.59L6.41,5L5,6.41L10.59,12L5,17.59L6.41,19L12,13.41L17.59,19L19,17.59L13.41,12L19,6.41Z" />
            </svg>
          </button>
        </div>
      </div>
      <div class="pdf-loading" v-if="isPdfLoading">
        <div class="loader"></div>
        <div>Loading PDF...</div>
      </div>
      <embed 
        :src="currentPdfUrl" 
        type="application/pdf"
        class="pdf-iframe" 
        @load="isPdfLoading = false"
        :style="{ opacity: isPdfLoading ? 0 : 1 }"
      >
    </div>
    
    <div v-if="!showPdf || !currentPdfUrl" class="pdf-files-panel">
      <div class="panel-header">
        <h3>File List</h3>
        <button class="close-btn" @click="toggleFilesList">×</button>
      </div>
      
      <div class="pdf-files-list">
        <div 
          v-for="file in pdfFiles" 
          :key="file.id"
          :class="['pdf-file-item', { active: file.id === selectedFileId }]"
          @click.stop="handleSelectFile(file)"
        >
          <div class="pdf-file-icon">
            <svg class="icon-svg" viewBox="0 0 24 24">
              <path d="M14,2H6C4.9,2 4,2.9 4,4V20C4,21.1 4.9,22 6,22H18C19.1,22 20,21.1 20,20V8L14,2M18,20H6V4H13V9H18V20M10,19L10.9,19C11.2,19 11.3,18.9 11.4,18.7L12.2,17.1L14.3,18.9L15,18.4L12.8,16.6L13.9,15C14.1,14.8 14.2,14.5 14,14.2C13.8,14 13.4,13.9 13,14.1L11.4,15L10.5,12.2L10,12.3L10.6,15.4L9.7,16L9.2,16.5L10,19M13.3,14.7C13.5,14.6 13.6,14.8 13.4,14.9L12,15.8L13.3,14.7M10.8,15.9L11.5,17.2L11.1,16.2L10.8,15.9M11.7,16.3L12.3,15.6L12.3,15.7L11.7,16.3Z" />
            </svg>
          </div>
          <div class="pdf-file-info">
            <div class="pdf-file-name">{{ file.name }}</div>
            <div class="pdf-file-size">{{ formatFileSize(file.size) }}</div>
          </div>
          <button 
            class="pdf-file-delete" 
            @click.stop="deleteFile(file)" 
            title="Delete file"
          >
            <svg class="icon-svg" viewBox="0 0 24 24">
              <path d="M19,4H15.5L14.5,3H9.5L8.5,4H5V6H19M6,19A2,2 0 0,0 8,21H16A2,2 0 0,0 18,19V7H6V19Z" />
            </svg>
          </button>
        </div>
        <div v-if="pdfFiles.length === 0" class="text-center p-4 text-gray-500">
          No files available in this session.
        </div>
      </div>
    </div>
  </div>
</template>

<script lang="ts">
import { defineComponent, ref, watch } from 'vue'
import { useToast } from 'vue-toastification'
import axios from 'axios'

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || ''

// 定义文件对象的接口
interface ChatFile {
  id: string;
  name: string;
  size: number;
  paper_id?: string;
  created_at?: string;
}

export default defineComponent({
  name: 'FileList',
  
  props: {
    chatId: {
      type: String,
      required: true
    },
    showFilesList: {
      type: Boolean,
      required: true
    }
  },
  
  emits: [
    'update:showFilesList',
    'file-selected',
    'pdf-closed',
    'files-updated'
  ],
  
  setup(props, { emit }) {
    const toast = useToast()
    const pdfFiles = ref<ChatFile[]>([])
    const showPdf = ref(false)
    const currentPdfUrl = ref<string | null>(null)
    const selectedFileId = ref<string | null>(null)
    const isPdfLoading = ref(false)
    const currentFileName = ref('Document')
    
    // Load session files
    const loadSessionFiles = async () => {
      try {
        const response = await axios.get<ChatFile[]>(`${API_BASE_URL}/api/chat/sessions/${props.chatId}/files`)
        pdfFiles.value = response.data
        emit('files-updated', pdfFiles.value)
        console.log('Loaded files:', pdfFiles.value.length)
      } catch (error) {
        console.error('Failed to load files:', error)
        toast.error('Failed to load file list')
      }
    }
    
    // Select PDF file
    const handleSelectFile = (file: ChatFile) => {
      selectedFileId.value = file.id
      isPdfLoading.value = true
      currentFileName.value = file.name
      
      const timestamp = Date.now()
      currentPdfUrl.value = `${API_BASE_URL}/api/chat/files/${file.id}/view?no_download=true&t=${timestamp}`
      showPdf.value = true
      
      emit('file-selected', file)
      
      if (window.innerWidth <= 768) {
        emit('update:showFilesList', false)
      }
    }
    
    // Delete file
    const deleteFile = async (file: ChatFile) => {
      if (!confirm(`Are you sure you want to delete the file ${file.name}?`)) return
      
      try {
        await axios.delete(`${API_BASE_URL}/api/chat/files/${file.id}`)
        
        pdfFiles.value = pdfFiles.value.filter(f => f.id !== file.id)
        emit('files-updated', pdfFiles.value)
        
        if (selectedFileId.value === file.id) {
          closePdf()
        }
        
        toast.success(`File ${file.name} deleted successfully`)
      } catch (error) {
        console.error('Failed to delete file:', error)
        toast.error('Failed to delete file. Please try again.')
      }
    }
    
    // Toggle file list display
    const toggleFilesList = () => {
      emit('update:showFilesList', !props.showFilesList)
      
      if (!props.showFilesList) {
        closePdf()
      }
    }
    
    // Close PDF viewer
    const closePdf = () => {
      currentPdfUrl.value = null
      selectedFileId.value = null
      showPdf.value = false
      isPdfLoading.value = false
      currentFileName.value = 'Document'
      emit('pdf-closed')
    }
    
    // Format file size
    const formatFileSize = (bytes: number): string => {
      if (bytes === 0) return '0 Bytes'
      
      const k = 1024
      const sizes = ['Bytes', 'KB', 'MB', 'GB']
      const i = Math.floor(Math.log(bytes) / Math.log(k))
      
      return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i]
    }
    
    // Watch PDF status, update body class when PDF is active
    watch(() => showPdf.value && currentPdfUrl.value, (isPdfActive) => {
      if (isPdfActive) {
        document.body.classList.add('pdf-active-page')
      } else {
        document.body.classList.remove('pdf-active-page')
      }
    })
    
    // Initial load
    loadSessionFiles()
    
    return {
      pdfFiles,
      showPdf,
      currentPdfUrl,
      selectedFileId,
      isPdfLoading,
      currentFileName,
      handleSelectFile,
      deleteFile,
      toggleFilesList,
      closePdf,
      formatFileSize
    }
  }
})
</script>

<style scoped>
.files-sidebar {
  width: 320px;
  height: 100%;
  background-color: white;
  border-radius: 12px;
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.05);
  overflow: hidden;
  display: flex;
  flex-direction: column;
  transition: all 0.3s ease;
  flex-shrink: 0;
}

.files-sidebar.active {
  width: 320px;
}

.files-sidebar.pdf-active {
  width: 50%;
  max-width: 800px;
  min-width: 600px;
}

.files-sidebar.hidden {
  width: 0;
  margin: 0;
  padding: 0;
  opacity: 0;
}

.pdf-files-panel {
  width: 100%;
  height: 100%;
  display: flex;
  flex-direction: column;
  background-color: white;
  overflow: hidden;
}

.panel-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 1rem;
  border-bottom: 1px solid #eee;
  background-color: #f9f9f9;
}

.panel-header h3 {
  margin: 0;
  font-size: 1.2rem;
  color: #333;
  font-weight: 600;
}

.close-btn {
  background: none;
  border: none;
  font-size: 1.5rem;
  line-height: 1;
  cursor: pointer;
  color: #666;
}

.close-btn:hover {
  color: #000;
}

.pdf-files-list {
  padding: 1rem;
  display: flex;
  flex-direction: column;
  gap: 0.75rem;
  flex: 1;
  overflow-y: auto;
}

.pdf-file-item {
  display: flex;
  align-items: center;
  padding: 0.75rem;
  border-radius: 8px;
  cursor: pointer;
  transition: all 0.2s;
  border: 1px solid #eee;
  width: 100%;
  box-sizing: border-box;
}

.pdf-file-item:hover {
  background-color: #f5f5f5;
  transform: translateY(-2px);
  box-shadow: 0 3px 6px rgba(0, 0, 0, 0.08);
}

.pdf-file-item.active {
  background-color: #e3f2fd;
  border-color: #bbdefb;
}

.pdf-file-icon {
  margin-right: 0.75rem;
  color: #1976d2;
  flex-shrink: 0;
}

.pdf-file-info {
  flex: 1;
  overflow: hidden;
  cursor: pointer;
  min-width: 0;
}

.pdf-file-delete {
  background: none;
  border: none;
  color: #757575;
  cursor: pointer;
  padding: 5px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: all 0.2s;
  opacity: 0.7;
  flex-shrink: 0;
}

.pdf-file-delete:hover {
  background-color: #ffebee;
  color: #e53935;
  opacity: 1;
}

.pdf-file-name {
  font-size: 0.95rem;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  margin-bottom: 0.25rem;
  font-weight: 500;
}

.pdf-file-size {
  font-size: 0.8rem;
  color: #777;
}

/* PDF viewer styles */
.pdf-view {
  width: 100%;
  height: 100%;
  position: relative;
  overflow: hidden;
  background-color: #f5f5f5;
  display: flex;
  flex-direction: column;
  border-radius: 6px;
}

.pdf-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 8px 16px;
  background-color: #f0f0f0;
  border-bottom: 1px solid #e0e0e0;
  z-index: 2;
}

.pdf-controls {
  display: flex;
  align-items: center;
  gap: 8px;
}

.pdf-title {
  margin: 0;
  font-size: 0.95rem;
  font-weight: 500;
  color: #333;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  max-width: calc(100% - 80px);
}

.pdf-control-btn, .close-pdf-btn {
  background-color: transparent;
  border: none;
  border-radius: 50%;
  width: 28px;
  height: 28px;
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  transition: all 0.2s;
}

.pdf-control-btn:hover, .close-pdf-btn:hover {
  background-color: rgba(0, 0, 0, 0.1);
}

.pdf-control-btn .icon-svg, .close-pdf-btn .icon-svg {
  width: 18px;
  height: 18px;
  color: #555;
}

.pdf-loading {
  position: absolute;
  top: 40px;
  left: 0;
  right: 0;
  bottom: 0;
  background-color: rgba(255, 255, 255, 0.9);
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  z-index: 5;
  gap: 1rem;
}

.pdf-loading .loader {
  width: 40px;
  height: 40px;
  border: 4px solid #f3f3f3;
  border-top: 4px solid #3f51b5;
  border-radius: 50%;
  animation: spin 1s linear infinite;
}

.pdf-iframe {
  width: 100%;
  height: calc(100% - 40px);
  border: none;
  flex: 1;
  transition: opacity 0.3s ease;
  background-color: white;
}

.icon-svg {
  width: 20px;
  height: 20px;
}

@keyframes spin {
  from { transform: rotate(0deg); }
  to { transform: rotate(360deg); }
}

/* Responsive styles */
@media (min-width: 1400px) {
  .files-sidebar.pdf-active {
    width: 45%;
    max-width: 850px;
  }
}

@media (max-width: 1200px) {
  .files-sidebar.pdf-active {
    width: 50%;
    min-width: 500px;
  }
}

@media (max-width: 1024px) {
  .files-sidebar {
    width: 100%;
    height: 400px;
    min-width: 0;
  }
  
  .files-sidebar.pdf-active {
    height: 550px;
    width: 100%;
    min-width: 0;
  }
  
  .files-sidebar.hidden {
    height: 0;
  }
}

@media (max-width: 768px) {
  .files-sidebar {
    height: 350px;
  }
}
</style> 