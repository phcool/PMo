<template>
  <div class="chat-page">
    <div v-if="initialLoading" class="loading">Loading...</div>
    <div v-else-if="error" class="error">{{ error }}</div>
    <div v-else :class="['full-layout', {'pdf-layout': showPdf && currentPdfUrl}]">
      <!-- Chat Area -->
      <div class="chat-view">
        <div class="chat-section">
          <div class="chat-header">
            <div class="header-main">
              <h2>AI Chat</h2>
              <div class="header-actions">
                <button 
                  v-if="pdfFiles.length > 0" 
                  @click="toggleFilesList" 
                  class="file-list-toggle"
                  :class="{ 'active': showFilesList }"
                  :title="showFilesList ? 'Hide files' : 'Show files'"
                >
                  <svg class="icon-svg" viewBox="0 0 24 24">
                    <path d="M14,2H6C4.9,2 4,2.9 4,4V20C4,21.1 4.9,22 6,22H18C19.1,22 20,21.1 20,20V8L14,2M18,20H6V4H13V9H18V20Z" />
                  </svg>
                  <span v-if="pdfFiles.length > 0" class="file-count">{{ pdfFiles.length }}</span>
                </button>
              </div>
            </div>
            <div class="pdf-actions">
              <label class="pdf-action-button upload">
                <svg class="icon-svg" viewBox="0 0 24 24">
                  <path d="M14,13V17H10V13H7L12,8L17,13H14M19.35,10.03C18.67,6.59 15.64,4 12,4C9.11,4 6.6,5.64 5.35,8.03C2.34,8.36 0,10.9 0,14A6,6 0 0,0 6,20H19A5,5 0 0,0 24,15C24,12.36 21.95,10.22 19.35,10.03Z" />
                </svg>
                <span>Upload PDF</span>
                <input 
                  type="file" 
                  accept=".pdf" 
                  @change="handleFileUpload" 
                  style="display: none;" 
                >
              </label>
            </div>
          </div>
          <div class="chat-container">
            <div class="chat-messages" ref="messagesContainer">
              <div v-for="message in messages" :key="message.id" 
                   :class="[
                     'chat-message', 
                     message.role === 'user' ? 'user-message' : 'assistant-message',
                     message.role === 'assistant' && isTyping && message.id === currentTypingMessageId ? 'typing' : ''
                   ]"
                   :data-message-id="message.id">
                <div class="message-content" v-html="formatMessage(message.content)" :class="{ 'live-typing': message.role === 'assistant' && isTyping && message.id === currentTypingMessageId }"></div>
              </div>
              <div v-if="isLoading && messages.length === 0" class="chat-loading">
                <div class="chat-loader"></div>
                <div>AI is thinking...</div>
              </div>
            </div>
            <div class="chat-input-container">
              <textarea 
                ref="inputField" 
                v-model="userInput"
                @keydown.enter.exact.prevent="sendMessage"
                :placeholder="isProcessingFile 
                  ? pendingFiles.length > 1 
                    ? `Please wait while I process ${processingFileName}... (${currentProcessingIndex + 1}/${pendingFiles.length})` 
                    : `Please wait while I process ${processingFileName}...` 
                  : 'Type your question...'
                "
                :disabled="isLoading || isProcessingFile"
                class="chat-input"
              ></textarea>
              <button 
                @click="sendMessage" 
                :disabled="isLoading || !userInput.trim() || isProcessingFile"
                class="chat-send-button"
              >
                <span v-if="isLoading">⏳</span>
                <span v-else-if="isProcessingFile">⌛</span>
                <span v-else>Send</span>
              </button>
            </div>
          </div>
        </div>
      </div>
      
      <!-- Files Sidebar -->
      <div class="files-sidebar" :class="{ 
        'hidden': !showFilesList, 
        'active': showFilesList,
        'pdf-active': showPdf && currentPdfUrl
      }">
        <div v-if="currentPdfUrl && showPdf" class="pdf-view">
          <div class="pdf-header">
            <h3 class="pdf-title" :title="currentFileName">{{ currentFileName }}</h3>
            <div class="pdf-controls">
              <a :href="currentPdfUrl" target="_blank" class="pdf-control-btn" title="在新窗口打开">
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
          <object 
            :data="currentPdfUrl" 
            type="application/pdf"
            class="pdf-iframe" 
            @load="isPdfLoading = false"
            :style="{ opacity: isPdfLoading ? 0 : 1 }"
          >
            <div class="pdf-fallback">
              无法直接显示PDF，<a :href="currentPdfUrl" target="_blank">点击此处</a>在新窗口打开
            </div>
          </object>
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
              No files. Please upload a PDF file for analysis.
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted, onBeforeUnmount, watch, computed, nextTick } from 'vue';
import { useRoute, useRouter } from 'vue-router';
import axios from 'axios';
import { useToast } from 'vue-toastification';
import { marked } from 'marked';
import DOMPurify from 'dompurify';
import hljs from 'highlight.js';
import 'highlight.js/styles/github.css';

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || '';

const route = useRoute();
const router = useRouter();
const toast = useToast();

// 聊天会话数据
const chatId = ref(null);
const messages = ref([]);
const userInput = ref('');
const isLoading = ref(false);  // 消息加载状态
const initialLoading = ref(true);  // 初始加载状态
const isTyping = ref(false);
const currentTypingMessageId = ref(null); // 当前正在输入的消息ID
const messagesContainer = ref(null);
const inputField = ref(null);
const error = ref(null);

// PDF文件管理
const pdfFiles = ref([]);
const showFilesList = ref(false);
const showPdf = ref(false);
const currentPdfUrl = ref(null);
const selectedFileId = ref(null);
const isProcessingFile = ref(false);
const processingFileName = ref('');
const isPdfLoading = ref(false); // 新增PDF加载状态
const currentFileName = ref('Document'); // 当前显示的PDF文件名

// PDF文件上传进度
const isUploading = ref(false);
const uploadProgress = ref(0);
const pendingFiles = ref([]);
const currentProcessingIndex = ref(0);

// 初始化
onMounted(async () => {
  try {
    initialLoading.value = true;
    error.value = null;
    // 如果URL中有chatId参数，加载已有会话
    if (route.params.id) {
      chatId.value = route.params.id;
      await loadChatSession();
      await loadSessionFiles();
    } else {
      // 否则创建新会话
      await createChatSession();
    }
    initialLoading.value = false;
  } catch (err) {
    console.error('Initialization error:', err);
    if (err.response) {
      console.error('API response:', err.response.status, err.response.data);
      error.value = `API error: ${err.response.status} - ${err.response.data.detail || 'Unknown error'}`;
    } else if (err.request) {
      console.error('No response received:', err.request);
      error.value = 'No response received from server. Please check your network connection.';
    } else {
      console.error('Error message:', err.message);
      error.value = `Error: ${err.message}`;
    }
    toast.error('Failed to initialize chat session. Please refresh the page and try again.');
    initialLoading.value = false;
  }
  
  // 设置高亮
  marked.setOptions({
    highlight: function(code, lang) {
      if (lang && hljs.getLanguage(lang)) {
        return hljs.highlight(code, { language: lang }).value;
      }
      return hljs.highlightAuto(code).value;
    }
  });
});

// 创建新的聊天会话
async function createChatSession() {
  try {
    isLoading.value = true;
    const response = await axios.post(`${API_BASE_URL}/api/chat/sessions`);
    
    // 根据API响应结构获取chat_id
    chatId.value = response.data.chat_id;
    
    // 更新URL以包含会话ID
    router.push({ name: 'chat', params: { id: chatId.value } });
    console.log('Created new session:', chatId.value);
  } catch (error) {
    console.error('Session creation failed:', error);
    toast.error('Failed to create chat session. Please try again.');
    // 不设置全局error，只显示toast消息
  } finally {
    isLoading.value = false;
  }
}

// 加载已有聊天会话
async function loadChatSession() {
  try {
    isLoading.value = true;
    const response = await axios.get(`${API_BASE_URL}/api/chat/sessions/${chatId.value}/messages`);
    
    // 根据API响应的结构获取消息列表
    if (response.data.messages) {
      messages.value = response.data.messages;
    } else {
      messages.value = [];
    }
    
    console.log('Loaded chat history:', messages.value.length);
    
    // 滚动到底部
    await nextTick();
    scrollToBottom();
  } catch (error) {
    console.error('Failed to load session:', error);
    toast.error('Failed to load chat history. Please try again.');
    // 不设置全局error，只显示toast消息
  } finally {
    isLoading.value = false;
  }
}

// 加载会话关联的文件
async function loadSessionFiles() {
  try {
    const response = await axios.get(`${API_BASE_URL}/api/chat/sessions/${chatId.value}/files`);
    pdfFiles.value = response.data;
    console.log('Loaded files:', pdfFiles.value.length);
  } catch (error) {
    console.error('Failed to load files:', error);
    toast.error('Failed to load file list');
    // 不设置全局error，只显示toast消息
  }
}

// 发送消息
async function sendMessage() {
  if (!userInput.value.trim() || isLoading.value) return;
  
  const messageContent = userInput.value.trim();
  userInput.value = '';
  
  // 添加用户消息到界面
  const userMessage = {
    id: Date.now().toString(),
    role: 'user',
    content: messageContent,
    created_at: new Date().toISOString()
  };
  
  messages.value.push(userMessage);
  
  // 滚动到底部
  await nextTick();
  scrollToBottom();
  
  // 开始处理回复
  try {
    isLoading.value = true;
    isTyping.value = true;
    
    // 添加一个空的助手消息作为占位符
    const assistantMessage = {
      id: (Date.now() + 1).toString(),
      role: 'assistant',
      content: '',
      created_at: new Date().toISOString()
    };
    
    currentTypingMessageId.value = assistantMessage.id;
    messages.value.push(assistantMessage);
    
    // 使用流式响应获取回复
    await streamChatResponse(messageContent, assistantMessage);
  } catch (err) {
    console.error('Failed to send message:', err);
    toast.error('Failed to send message. Please try again.');
    
    // 移除最后一条空的助手消息
    if (messages.value.length > 0 && 
        messages.value[messages.value.length - 1].role === 'assistant' && 
        messages.value[messages.value.length - 1].content === '') {
      messages.value.pop();
    }
  } finally {
    isLoading.value = false;
    isTyping.value = false;
    currentTypingMessageId.value = null;
  }
}

// 流式获取聊天回复
async function streamChatResponse(userMessage, assistantMessage) {
  try {
    // 发送请求
    const response = await fetch(`${API_BASE_URL}/api/chat/sessions/${chatId.value}/chat`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({ message: userMessage }),
    });
    
    if (!response.ok) {
      throw new Error(`HTTP error! status: ${response.status}`);
    }
    
    // 处理流式响应
    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    let receivedChunks = 0;
    
    // 消息容器引用 - 用于直接操作DOM
    const messageEl = document.querySelector(`[data-message-id="${assistantMessage.id}"]`);
    
    while (true) {
      const { done, value } = await reader.read();
      
      if (done) {
        isTyping.value = false;
        // 滚动到底部
        scrollToBottom();
        break;
      }
      
      // 解码数据
      const chunk = decoder.decode(value, { stream: true });
      receivedChunks++;
      
      try {
        // 尝试解析为JSON
        const jsonChunks = chunk
          .split('\n')
          .filter(line => line.trim())
          .map(line => {
            try {
              return JSON.parse(line);
            } catch (e) {
              return null;
            }
          })
          .filter(item => item !== null);
        
        for (const jsonData of jsonChunks) {
          // 如果有content字段，立即添加到消息中
          if (jsonData.content) {
            assistantMessage.content += jsonData.content;
            
            // 直接更新DOM，不等待Vue的更新周期
            if (messageEl) {
              // 创建临时div来解析HTML
              const tempDiv = document.createElement('div');
              tempDiv.innerHTML = DOMPurify.sanitize(marked(assistantMessage.content));
              
              // 获取内容容器并更新
              const contentEl = messageEl.querySelector('.message-content');
              if (contentEl) {
                contentEl.innerHTML = tempDiv.innerHTML;
              }
            }
            
            // 滚动到底部
            scrollToBottom();
          }
        }
      } catch (e) {
        // 如果解析失败，直接将文本添加到消息中
        assistantMessage.content += chunk;
        
        // 直接更新DOM
        if (messageEl) {
          const tempDiv = document.createElement('div');
          tempDiv.innerHTML = DOMPurify.sanitize(marked(assistantMessage.content));
          
          const contentEl = messageEl.querySelector('.message-content');
          if (contentEl) {
            contentEl.innerHTML = tempDiv.innerHTML;
          }
        }
        
        // 滚动到底部
        scrollToBottom();
      }
    }
  } catch (error) {
    console.error('Failed to get streaming response:', error);
    assistantMessage.content = "Failed to get response. Please try again.";
    throw error; // 重新抛出错误，让外部函数处理
  }
}

// 处理文件上传
async function handleFileUpload(event) {
  const files = event.target.files;
  if (!files || files.length === 0) return;
  
  try {
    isUploading.value = true;
    
    for (let i = 0; i < files.length; i++) {
      const file = files[i];
      
      // 文件大小限制检查 (20MB)
      if (file.size > 20 * 1024 * 1024) {
        toast.error(`File ${file.name} is too large. Maximum size is 20MB.`);
        continue;
      }
      
      // 添加到待处理队列
      pendingFiles.value.push(file);
    }
    
    // 重置文件输入
    event.target.value = null;
    
    // 处理队列中的文件
    if (pendingFiles.value.length > 0) {
      processNextFile();
    }
  } catch (error) {
    console.error('File upload failed:', error);
    toast.error('File upload failed. Please try again.');
    isUploading.value = false;
  }
}

// 处理队列中的下一个文件
async function processNextFile() {
  if (pendingFiles.value.length === 0) {
    isUploading.value = false;
    return;
  }
  
  const file = pendingFiles.value[0];
  currentProcessingIndex.value = 0;
  processingFileName.value = file.name;
  isProcessingFile.value = true;
  
  try {
    const formData = new FormData();
    formData.append('file', file);
    
    const response = await axios.post(
      `${API_BASE_URL}/api/chat/sessions/${chatId.value}/upload`,
      formData,
      {
        headers: {
          'Content-Type': 'multipart/form-data'
        },
        onUploadProgress: (progressEvent) => {
          const percentCompleted = Math.round(
            (progressEvent.loaded * 100) / progressEvent.total
          );
          uploadProgress.value = percentCompleted;
        }
      }
    );
    
    // 将新文件添加到列表
    if (response.data) {
      pdfFiles.value.push(response.data);
      toast.success(`File ${file.name} uploaded successfully`);
    }
  } catch (error) {
    console.error('Failed to process file:', error);
    toast.error(`Failed to process file ${file.name}. Please try again.`);
  } finally {
    // 移除已处理的文件并处理下一个
    pendingFiles.value.shift();
    currentProcessingIndex.value++;
    
    if (pendingFiles.value.length > 0) {
      processNextFile();
    } else {
      isProcessingFile.value = false;
      processingFileName.value = '';
      uploadProgress.value = 0;
      isUploading.value = false;
      
      // 显示文件列表
      showFilesList.value = true;
    }
  }
}

// 选择PDF文件
function handleSelectFile(file) {
  selectedFileId.value = file.id;
  isPdfLoading.value = true; // 开始加载PDF
  currentFileName.value = file.name; // 设置当前文件名
  
  // 确保URL包含no_download=true参数，并添加随机参数避免浏览器缓存
  const timestamp = Date.now();
  currentPdfUrl.value = `${API_BASE_URL}/api/chat/files/${file.id}/view?no_download=true&t=${timestamp}`;
  showPdf.value = true;
  
  // 如果在移动设备上，自动关闭文件列表，只显示PDF
  if (window.innerWidth <= 768) {
    showFilesList.value = false;
  }
}

// 删除文件
async function deleteFile(file) {
  if (!confirm(`Are you sure you want to delete the file ${file.name}?`)) return;
  
  try {
    await axios.delete(`${API_BASE_URL}/api/chat/files/${file.id}`);
    
    // 从列表中移除
    pdfFiles.value = pdfFiles.value.filter(f => f.id !== file.id);
    
    // 如果当前显示的文件被删除，关闭预览
    if (selectedFileId.value === file.id) {
      closePdf();
    }
    
    toast.success(`File ${file.name} deleted successfully`);
  } catch (error) {
    console.error('Failed to delete file:', error);
    toast.error('Failed to delete file. Please try again.');
  }
}

// 切换文件列表显示
function toggleFilesList() {
  showFilesList.value = !showFilesList.value;
  
  // 如果关闭文件列表，也关闭PDF查看器
  if (!showFilesList.value) {
    closePdf();
  }
}

// 关闭PDF查看器
function closePdf() {
  currentPdfUrl.value = null;
  selectedFileId.value = null;
  showPdf.value = false;
  isPdfLoading.value = false;
  currentFileName.value = 'Document';
}

// 修改formatMessage函数，简化处理流程，避免复杂的缓存机制
function formatMessage(content) {
  if (!content) return '';
  
  // 使用marked将markdown转换为HTML
  const html = marked(content);
  
  // 使用DOMPurify清理HTML
  return DOMPurify.sanitize(html);
}

// 文件大小格式化
function formatFileSize(bytes) {
  if (bytes === 0) return '0 Bytes';
  
  const k = 1024;
  const sizes = ['Bytes', 'KB', 'MB', 'GB'];
  const i = Math.floor(Math.log(bytes) / Math.log(k));
  
  return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
}

// 滚动到底部
function scrollToBottom() {
  if (messagesContainer.value) {
    // 使用requestAnimationFrame确保浏览器已渲染出最新内容
    window.requestAnimationFrame(() => {
      messagesContainer.value.scrollTop = messagesContainer.value.scrollHeight;
    });
  }
}

// 改进watch以确保消息变化时更新滚动
watch(
  () => messages.value.map(m => m.content),
  () => {
    nextTick(() => {
      scrollToBottom();
    });
  },
  { deep: true }
);

// 监视PDF状态，当PDF激活时更新body类
watch(() => showPdf.value && currentPdfUrl.value, (isPdfActive) => {
  if (isPdfActive) {
    document.body.classList.add('pdf-active-page');
  } else {
    document.body.classList.remove('pdf-active-page');
  }
});

// 组件卸载时移除body类
onBeforeUnmount(() => {
  document.body.classList.remove('pdf-active-page');
});
</script>

<style scoped>
.chat-page {
  width: 100%;
  height: calc(100vh - 60px); /* 减去顶部导航栏的高度 */
  position: relative;
  display: flex;
  flex-direction: column;
  background-color: #f5f7fa;
  overflow: hidden;
}

.full-layout {
  display: flex;
  height: 100%;
  width: 100%;
  overflow: visible;
  margin: 0;
  padding: 12px;
  box-sizing: border-box;
  transition: all 0.3s ease;
}

.pdf-layout {
  padding: 8px;
}

.loading, .error {
  text-align: center;
  padding: 2rem;
  background-color: white;
  border-radius: 8px;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
  margin-bottom: 2rem;
}

.error {
  color: #d32f2f;
}

.action-button {
  padding: 0.5rem 1rem;
  border-radius: 4px;
  text-decoration: none;
  font-size: 1rem;
  transition: all 0.2s;
  display: inline-block;
  border: none;
  cursor: pointer;
  background-color: #f0f0f0;
  color: #333;
}

.action-button:hover {
  background-color: #e0e0e0;
}

/* 聊天相关样式 */
.chat-view {
  display: flex;
  flex-direction: column;
  flex: 1;
  min-width: 0;
  max-width: 100%;
  padding: 0;
  overflow: hidden;
  height: 100%;
  background-color: white;
  border-radius: 12px;
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.05);
  margin-right: 12px;
  transition: all 0.3s ease;
}

.chat-section {
  display: flex;
  flex-direction: column;
  height: 100%;
  width: 100%;
  padding: 1rem;
  overflow: hidden;
  box-sizing: border-box;
}

.chat-header {
  flex-shrink: 0;
  display: flex;
  flex-direction: column;
  margin-bottom: 1rem;
  padding-bottom: 1rem;
  border-bottom: 1px solid #eee;
  width: 100%;
}

.header-main {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 1rem;
  width: 100%;
}

.header-actions {
  display: flex;
  align-items: center;
  gap: 0.5rem;
}

.chat-header h2 {
  margin: 0;
  font-size: 1.4rem;
  color: #333;
  font-weight: 600;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.file-list-toggle {
  display: flex;
  align-items: center;
  justify-content: center;
  background-color: #f0f0f0;
  border: none;
  padding: 0.5rem;
  border-radius: 4px;
  cursor: pointer;
  position: relative;
  transition: all 0.2s;
  width: 32px;
  height: 32px;
  flex-shrink: 0;
}

.file-list-toggle.active {
  background-color: #e3f2fd;
  color: #1976d2;
}

.file-list-toggle .icon-svg {
  width: 18px;
  height: 18px;
}

.file-list-toggle .file-count {
  position: absolute;
  top: -5px;
  right: -5px;
  background-color: #1976d2;
  color: white;
  font-size: 0.7rem;
  font-weight: bold;
  border-radius: 50%;
  min-width: 16px;
  height: 16px;
  display: flex;
  align-items: center;
  justify-content: center;
}

.chat-container {
  display: flex;
  flex-direction: column;
  flex: 1;
  overflow: hidden;
  width: 100%;
}

.pdf-actions {
  display: flex;
  width: 100%;
  margin-bottom: 1rem;
  flex-shrink: 0;
}

.pdf-action-button {
  display: inline-flex;
  align-items: center;
  padding: 0.5rem;
  background-color: #f5f5f5;
  color: #333;
  border: 1px solid #ddd;
  border-radius: 8px;
  cursor: pointer;
  text-decoration: none;
  font-size: 0.9rem;
  transition: all 0.2s;
  flex: 1;
  justify-content: center;
  gap: 6px;
  overflow: hidden;
  white-space: nowrap;
}

.pdf-action-button span {
  overflow: hidden;
  text-overflow: ellipsis;
  display: inline-block;
}

.pdf-action-button.upload {
  background-color: #e8f5e9;
  color: #2e7d32;
  border-color: #c8e6c9;
}

.pdf-action-button.upload:hover {
  background-color: #c8e6c9;
}

.pdf-action-button .icon-svg {
  color: currentColor;
  flex-shrink: 0;
  width: 18px;
  height: 18px;
}

.chat-messages {
  flex: 1;
  overflow-y: auto;
  padding: 1rem;
  background-color: #f9f9f9;
  border-radius: 10px;
  margin-bottom: 1rem;
  width: 100%;
  box-sizing: border-box;
}

.chat-message {
  margin-bottom: 1rem;
  padding: 0.75rem 1rem;
  border-radius: 12px;
  max-width: 85%;
  box-shadow: 0 1px 2px rgba(0, 0, 0, 0.1);
  word-wrap: break-word;
  overflow-wrap: break-word;
  box-sizing: border-box;
}

.user-message {
  background-color: #e3f2fd;
  color: #0d47a1;
  margin-left: auto;
  border-top-right-radius: 2px;
}

.assistant-message {
  background-color: #f5f5f5;
  color: #333;
  margin-right: auto;
  border-top-left-radius: 2px;
}

.message-content {
  line-height: 1.6;
  white-space: pre-line;
  font-size: 0.95rem;
  word-break: break-word;
  overflow-wrap: break-word;
  will-change: contents; /* 提示浏览器该内容会频繁更改 */
  transition: none; /* 禁用可能的CSS过渡 */
}

/* 添加新的live-typing类样式 */
.message-content.live-typing::after {
  content: "";
  width: 6px;
  height: 15px;
  background: #3f51b5;
  display: inline-block;
  margin-left: 2px;
  animation: blink 1s step-start infinite;
  vertical-align: middle;
}

@keyframes blink {
  50% { opacity: 0; }
}

.chat-input-container {
  display: flex;
  gap: 0.5rem;
  margin-top: auto;
  flex-shrink: 0;
  background-color: #fff;
  padding: 0.5rem;
  border-radius: 10px;
  border: 1px solid #eaeaea;
  width: 100%;
  box-sizing: border-box;
}

.chat-input {
  flex: 1;
  padding: 0.75rem;
  border: 1px solid #eee;
  border-radius: 8px;
  resize: none;
  min-height: 50px;
  font-family: inherit;
  font-size: 1rem;
  box-shadow: inset 0 1px 3px rgba(0, 0, 0, 0.05);
  overflow: auto;
}

.chat-input:focus {
  outline: none;
  border-color: #3f51b5;
}

.chat-send-button {
  padding: 0.75rem;
  background-color: #3f51b5;
  color: white;
  border: none;
  border-radius: 8px;
  cursor: pointer;
  font-size: 1rem;
  font-weight: 500;
  transition: all 0.2s;
  flex-shrink: 0;
  white-space: nowrap;
  min-width: 60px;
}

.chat-send-button:hover:not(:disabled) {
  background-color: #303f9f;
  transform: translateY(-1px);
}

.chat-send-button:disabled {
  background-color: #bdbdbd;
  cursor: not-allowed;
}

.chat-loading {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  color: #666;
  font-style: italic;
  padding: 0.5rem;
}

.chat-loader {
  width: 20px;
  height: 20px;
  border: 2px solid #f3f3f3;
  border-top: 2px solid #3f51b5;
  border-radius: 50%;
  animation: spin 1s linear infinite;
  flex-shrink: 0;
}

@keyframes spin {
  0% { transform: rotate(0deg); }
  100% { transform: rotate(360deg); }
}

/* 文件列表和PDF查看器样式 */
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
  width: 50%; /* 使用百分比宽度确保响应式 */
  max-width: 800px; /* 设置最大宽度避免PDF区域过大 */
  min-width: 600px; /* 设置最小宽度确保PDF可读性 */
}

.files-sidebar.hidden {
  width: 0;
  margin: 0;
  padding: 0;
  opacity: 0;
}

.full-layout.pdf-layout {
  padding: 8px;
  display: flex;
  justify-content: space-between;
}

.full-layout.pdf-layout .chat-view {
  flex: 1;
  min-width: 450px;
  width: calc(50% - 12px);
  max-width: calc(100% - 620px);
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

/* PDF查看器样式 */
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
  top: 40px; /* 预留PDF标题栏高度 */
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
  height: calc(100% - 40px); /* 减去PDF标题栏高度 */
  border: none;
  flex: 1;
  transition: opacity 0.3s ease;
  background-color: white;
}

.pdf-fallback {
  padding: 2rem;
  text-align: center;
  background-color: #f5f5f5;
  border-radius: 8px;
  margin: 2rem;
}

.pdf-fallback a {
  color: #1976d2;
  text-decoration: underline;
}

.icon-svg {
  width: 20px;
  height: 20px;
}

/* 响应式布局 */
@media (min-width: 1400px) {
  .files-sidebar.pdf-active {
    width: 45%;
    max-width: 850px;
  }
  
  .full-layout.pdf-layout .chat-view {
    width: calc(55% - 12px);
  }
}

@media (max-width: 1200px) {
  .files-sidebar.pdf-active {
    width: 50%;
    min-width: 500px;
  }
  
  .full-layout.pdf-layout .chat-view {
    min-width: 400px;
    width: calc(50% - 12px);
  }
}

@media (max-width: 1024px) {
  .full-layout {
    flex-direction: column;
    padding: 8px;
  }
  
  .full-layout.pdf-layout .chat-view {
    max-width: 100%;
    min-width: 100%;
    width: 100%;
    margin-bottom: 12px;
  }
  
  .chat-view {
    margin-right: 0;
    margin-bottom: 12px;
  }
  
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
  .chat-page {
    position: relative;
    height: auto;
    min-height: calc(100vh - 60px);
  }
  
  .full-layout {
    padding: 6px;
  }
  
  .chat-section {
    padding: 0.75rem;
  }
  
  .files-sidebar {
    height: 350px;
  }
  
  .pdf-action-button {
    padding: 0.4rem;
    font-size: 0.85rem;
  }
  
  .chat-send-button {
    padding: 0.6rem;
    min-width: 50px;
  }
  
  .chat-header h2 {
    font-size: 1.2rem;
  }
}
</style>

<style>
/* 当PDF显示时，调整页面布局 */
body.pdf-active-page {
  --app-max-width: none !important;
  --container-padding: 0 !important;
}

body.pdf-active-page .container {
  max-width: none !important;
  padding: 0 !important;
  width: 100% !important;
}

/* 全局样式：去除主容器限制 */
body {
  --app-max-width: none !important;
  overflow-x: hidden;
}

.container, .container-fluid {
  max-width: none !important;
  padding-left: 0 !important;
  padding-right: 0 !important;
  width: 100% !important;
  margin: 0 !important;
}

.row {
  margin-left: 0 !important;
  margin-right: 0 !important;
}
</style> 