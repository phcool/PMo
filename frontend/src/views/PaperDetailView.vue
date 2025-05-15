<template>
  <div class="paper-detail">
    <div v-if="isLoading" class="loading">
      Loading paper details...
    </div>
    
    <div v-else-if="error" class="error">
      <p>{{ error }}</p>
      <button @click="goBack" class="back-link">Back</button>
    </div>
    
    <div v-else-if="paper" :class="['paper-container', { 'split-layout': showPdf || activeUploadedPdf }]">
      <div class="paper-content">
        <!-- Chat Mode -->
        <div v-if="chatMode" class="chat-interface">
          <div class="chat-header">
            <div class="header-main">
              <h2>Chat about this paper</h2>
              <div class="header-actions">
                <button 
                  v-if="uploadedPdfs.length > 0" 
                  @click="toggleFilesList" 
                  class="file-list-toggle"
                  :class="{ 'active': showFilesList }"
                >
                  <svg class="icon-svg" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
                    <path d="M19 3H5C3.9 3 3 3.9 3 5V19C3 20.1 3.9 21 5 21H19C20.1 21 21 20.1 21 19V5C21 3.9 20.1 3 19 3ZM5 19V5H19V19H5Z" fill="currentColor"/>
                    <path d="M7 7H17V9H7V7Z" fill="currentColor"/>
                    <path d="M7 11H17V13H7V11Z" fill="currentColor"/>
                    <path d="M7 15H13V17H7V15Z" fill="currentColor"/>
                  </svg>
                  <span class="file-count">{{ uploadedPdfs.length }}</span>
                </button>
                <button @click="toggleChatMode" class="action-button">Back to Paper</button>
              </div>
            </div>
            <div class="pdf-actions">
              <button @click="downloadPdf" class="pdf-action-button download">
                <svg class="icon-svg" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
                  <path d="M19 9H15V3H9V9H5L12 16L19 9ZM5 18V20H19V18H5Z" fill="currentColor"/>
                </svg>
                <span>Download PDF</span>
              </button>
              <label class="pdf-action-button upload">
                <svg class="icon-svg" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
                  <path d="M9 16H15V10H19L12 3L5 10H9V16ZM5 18H19V20H5V18Z" fill="currentColor"/>
                </svg>
                <span>Upload PDF</span>
                <input 
                  type="file" 
                  accept=".pdf" 
                  style="display: none;" 
                  @change="handleFileUpload"
                  multiple
                />
              </label>
            </div>
          </div>
          
          <div class="chat-container">
            <div class="chat-messages" 
              ref="chatMessagesEl" 
              @scroll="handleUserScroll"
            >
              <div v-for="(msg, index) in chatMessages" :key="index" 
                   :class="[
                     'chat-message', 
                     msg.role === 'user' ? 'user-message' : 'assistant-message',
                     index === chatMessages.length - 1 && isChatLoading && msg.role === 'assistant' ? 'typing' : ''
                   ]">
                <div class="message-content">{{ msg.content }}</div>
              </div>
              <div v-if="isChatLoading && chatMessages.length === 0" class="chat-loading">
                <div class="chat-loader"></div>
                <div>AI is thinking...</div>
              </div>
            </div>
            
            <div class="chat-input-container">
              <textarea 
                ref="chatInputEl" 
                v-model="chatInput"
                @keydown.enter.prevent="sendChatMessage"
                :placeholder="isProcessingFile 
                  ? pendingFiles.length > 1 
                    ? `Please wait while I process ${processingFileName}... (${currentProcessingIndex + 1}/${pendingFiles.length})` 
                    : `Please wait while I process ${processingFileName}...` 
                  : 'Type your message...'"
                :disabled="isChatLoading || isProcessingFile"
                class="chat-input"
              ></textarea>
              <button 
                @click="sendChatMessage" 
                :disabled="isChatLoading || !chatInput.trim() || isProcessingFile"
                class="chat-send-button"
              >
                <span v-if="isChatLoading">⏳</span>
                <span v-else-if="isProcessingFile">⌛</span>
                <span v-else>Send</span>
              </button>
            </div>
          </div>
        </div>
        
        <!-- Normal Paper View -->
        <div v-else>
          <div class="paper-header">
            <h1 class="paper-title">{{ paper.title }}</h1>
            
            <div class="paper-meta">
              <div class="authors">
                <strong>Authors:</strong> {{ paper.authors.join(', ') }}
              </div>
              
              <div class="date">
                <strong>Published:</strong> {{ formattedDate }}
              </div>
            </div>
            
            <div class="paper-categories">
              <strong>Categories:</strong>
              <span 
                v-for="category in paper.categories" 
                :key="category" 
                class="category-tag"
              >
                {{ getCategoryLabel(category) }}
              </span>
            </div>
          </div>
          
          <div class="paper-actions">
            <button @click="togglePdfViewer" class="action-button primary">
              {{ showPdf ? 'Hide PDF' : 'PDF' }}
            </button>
            <button @click="goBack" class="action-button">
              Back
            </button>
          </div>
          
          <div class="paper-abstract">
            <h2>Abstract</h2>
            <p>{{ paper.abstract }}</p>
          </div>
        </div>
      </div>
      
      <!-- PDF Files List (Overlay) -->
      <div v-if="showFilesList" class="pdf-files-list-overlay" @click.self="toggleFilesList">
        <div class="pdf-files-panel">
          <div class="panel-header">
            <h3>Uploaded Files</h3>
            <button @click="toggleFilesList" class="close-btn">&times;</button>
          </div>
          <div class="pdf-files-list">
            <div 
              v-for="(pdf, index) in uploadedPdfs" 
              :key="index"
              :class="['pdf-file-item', { active: activeUploadedPdfIndex === index }]"
            >
              <div class="pdf-file-icon">
                <svg class="icon-svg" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
                  <path d="M14 2H6C4.9 2 4.01 2.9 4.01 4L4 20C4 21.1 4.89 22 5.99 22H18C19.1 22 20 21.1 20 20V8L14 2ZM16 18H8V16H16V18ZM16 14H8V12H16V14ZM13 9V3.5L18.5 9H13Z" fill="currentColor"/>
                </svg>
              </div>
              <div class="pdf-file-info" @click="selectPdfAndCloseList(index)">
                <div class="pdf-file-name">{{ pdf.name }}</div>
                <div class="pdf-file-size">{{ formatFileSize(pdf.size) }}</div>
              </div>
              <button 
                class="pdf-file-delete" 
                @click.stop="deleteFile(index)" 
                title="Delete file"
              >
                <svg class="icon-svg" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
                  <path d="M6 19c0 1.1.9 2 2 2h8c1.1 0 2-.9 2-2V7H6v12zM19 4h-3.5l-1-1h-5l-1 1H5v2h14V4z" fill="currentColor"/>
                </svg>
              </button>
            </div>
          </div>
        </div>
      </div>
      
      <!-- PDF Viewer -->
      <div v-if="(showPdf && paper.pdf_url) || activeUploadedPdf" class="pdf-section">
        <button @click="closePdf" class="close-pdf-btn" title="Close PDF">
          <svg class="icon-svg" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
            <path d="M19 6.41L17.59 5 12 10.59 6.41 5 5 6.41 10.59 12 5 17.59 6.41 19 12 13.41 17.59 19 19 17.59 13.41 12 19 6.41z" fill="currentColor"/>
          </svg>
        </button>
        <iframe 
          :src="activeUploadedPdf || paper.pdf_url + '#toolbar=1&navpanes=1&scrollbar=1&view=FitH'" 
          class="pdf-iframe" 
          frameborder="0"
          allowfullscreen
        ></iframe>
      </div>
    </div>
  </div>
</template>

<script>
import { defineComponent, ref, onMounted, computed, watch, nextTick, onBeforeUnmount } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import api from '../services/api'  // Remove .ts extension
import { getCategoryLabel } from '../types/paper'
import { chatSessionStore } from '../stores/chatSession'

export default defineComponent({
  name: 'PaperDetailView',
  
  setup() {
    const route = useRoute();
    const router = useRouter();
    const paper = ref(null);
    const isLoading = ref(true);
    const error = ref(null);
    const showPdf = ref(false);
    
    // PDF files management
    const uploadedPdfs = ref([]); // 存储多个上传的PDF文件
    const activeUploadedPdfIndex = ref(-1); // 当前活动PDF索引
    const showFilesList = ref(false); // 控制文件列表显示
    
    // Add chatSessionId to store the chat session ID
    const chatSessionId = ref('');
    
    // Computed property for the active PDF URL
    const activeUploadedPdf = computed(() => {
      if (activeUploadedPdfIndex.value >= 0 && uploadedPdfs.value[activeUploadedPdfIndex.value]) {
        return uploadedPdfs.value[activeUploadedPdfIndex.value].url;
      }
      return null;
    });
    
    // Chat state
    const chatMode = ref(false);
    const chatInput = ref('');
    const chatMessages = ref([]);
    const isChatLoading = ref(false);
    const chatError = ref(null);
    
    // Reference for chat messages container
    const chatMessagesEl = ref(null);
    
    // Format the date
    const formattedDate = computed(() => {
      if (!paper.value) return '';
      
      try {
        const date = new Date(paper.value.published_date);
        return date.toLocaleDateString('en-US', {
          year: 'numeric',
          month: 'long',
          day: 'numeric'
        });
      } catch (e) {
        return paper.value.published_date;
      }
    });
    
    // Format file size
    const formatFileSize = (bytes) => {
      if (bytes === 0) return '0 Bytes';
      const k = 1024;
      const sizes = ['Bytes', 'KB', 'MB', 'GB'];
      const i = Math.floor(Math.log(bytes) / Math.log(k));
      return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
    };
    
    // Toggle files list
    const toggleFilesList = () => {
      showFilesList.value = !showFilesList.value;
      // 如果打开文件列表，暂时隐藏PDF
      if (showFilesList.value) {
        showPdf.value = false;
      } else if (activeUploadedPdfIndex.value >= 0) {
        // 如果关闭文件列表且有选中的文件，则显示PDF
        showPdf.value = true;
      }
    };
    
    // Select a PDF from the list and close list
    const selectPdfAndCloseList = (index) => {
      activeUploadedPdfIndex.value = index;
      showPdf.value = true;
      showFilesList.value = false; // 关闭文件列表
    };
    
    // Select a PDF from the list (without closing)
    const selectPdf = (index) => {
      activeUploadedPdfIndex.value = index;
      showPdf.value = true;
    };
    
    // Toggle PDF viewer
    const togglePdfViewer = () => {
      showPdf.value = !showPdf.value;
    };
    
    // Close PDF viewer
    const closePdf = () => {
      showPdf.value = false;
      // 如果是查看上传的PDF，也关闭
      if (activeUploadedPdf.value) {
        activeUploadedPdfIndex.value = -1;
      }
    };
    
    // 处理状态变量
    const isProcessingFile = ref(false);
    const processingFileName = ref('');
    const statusCheckInterval = ref(null);
    const pendingFiles = ref([]); // 存储待处理的文件
    const currentProcessingIndex = ref(0); // 当前正在处理的文件索引
    
    // 清理定时器
    onBeforeUnmount(() => {
      if (statusCheckInterval.value) {
        clearInterval(statusCheckInterval.value);
      }
    });
    
    // 检查文件处理状态
    const checkProcessingStatus = async () => {
      if (!chatSessionId.value) return;
      
      try {
        const status = await api.getProcessingStatus(chatSessionId.value);
        isProcessingFile.value = status.processing;
        
        if (status.processing) {
          processingFileName.value = status.file_name;
        } else if (pendingFiles.value.length > 0 && currentProcessingIndex.value < pendingFiles.value.length - 1) {
          // 当前文件处理完成，处理下一个文件
          currentProcessingIndex.value++;
          const nextFile = pendingFiles.value[currentProcessingIndex.value];
          
          // 更新消息，显示正在处理的新文件
          chatMessages.value.push({
            role: 'assistant',
            content: `I've finished processing ${pendingFiles.value[currentProcessingIndex.value-1].name}. Now processing ${nextFile.name} (${currentProcessingIndex.value + 1}/${pendingFiles.value.length})...`
          });
          
          // 滚动到底部
          nextTick(() => {
            smartScrollToBottom();
          });
          
          // 更新当前处理的文件名
          processingFileName.value = nextFile.name;
          isProcessingFile.value = true;
          
          // 上传下一个文件
          try {
            await api.uploadPdfToChat(chatSessionId.value, nextFile);
          } catch (e) {
            console.error('Error uploading PDF for RAG processing:', e);
            
            // 提取错误信息
            let errorMessage = "";
            if (e.response && e.response.data && e.response.data.detail) {
              errorMessage = e.response.data.detail;
            } else {
              errorMessage = "I encountered an error processing this file. It might be too large or complex.";
            }
            
            chatMessages.value.push({
              role: 'assistant',
              content: `Error processing ${nextFile.name}: ${errorMessage}`
            });
            
            // 滚动到底部
            nextTick(() => {
              smartScrollToBottom();
            });
            
            // 继续下一个文件或完成处理
            if (currentProcessingIndex.value < pendingFiles.value.length - 1) {
              currentProcessingIndex.value++;
              // 递归调用以处理下一个文件
              setTimeout(() => checkProcessingStatus(), 100);
            } else {
              // 所有文件处理完成
              completeProcessing(status);
            }
          }
        } else if (!status.processing && statusCheckInterval.value) {
          // 所有文件处理完成
          completeProcessing(status);
        }
      } catch (e) {
        console.error('Error checking processing status:', e);
        // 发生错误，停止检查
        if (statusCheckInterval.value) {
          clearInterval(statusCheckInterval.value);
          statusCheckInterval.value = null;
        }
      }
    };
    
    // 所有文件处理完成
    const completeProcessing = (status = null) => {
      clearInterval(statusCheckInterval.value);
      statusCheckInterval.value = null;
      isProcessingFile.value = false;
      
      // 获取处理完成的文件总数
      const filesCount = status && status.files_count ? status.files_count : pendingFiles.value.length;
      
      // 添加处理完成消息
      let message = '';
      if (filesCount === 1) {
        // 单文件处理完成
        const fileName = pendingFiles.value.length === 1 ? 
          pendingFiles.value[0].name : 
          (status && status.file_name ? status.file_name : "the document");
          
        message = `I've finished processing ${fileName}. Now I can answer your questions about this document. You can access the document anytime via the file button in the top right corner.`;
      } else {
        // 多文件处理完成
        if (pendingFiles.value.length > 0) {
          // 如果是本次上传的多个文件
          const fileNames = pendingFiles.value.map(f => f.name).join(', ');
          message = `I've finished processing all ${pendingFiles.value.length} documents: ${fileNames}. You can now ask me questions about any of these documents. You can access any document via the file button in the top right corner.`;
        } else {
          // 如果是之前上传的和本次上传的混合
          message = `I've finished processing all documents. You now have ${filesCount} documents available. You can ask me questions about any of these documents. You can access any document via the file button in the top right corner.`;
        }
      }
      
      // 添加消息
      chatMessages.value.push({
        role: 'assistant',
        content: message
      });
      
      // 清空待处理队列
      pendingFiles.value = [];
      currentProcessingIndex.value = 0;
      
      // 滚动到底部
      nextTick(() => {
        smartScrollToBottom();
      });
    };

    // 创建或获取聊天会话
    const getChatSession = async () => {
      let chatId = '';
      
      // 检查是否存在全局会话
      if (chatSessionStore.hasActiveSession()) {
        // 使用全局会话
        chatId = chatSessionStore.getChatId();
        chatSessionId.value = chatId;
        console.log('Using global chat session:', chatId);
      } else {
        // 如果没有全局会话，创建一个新的
        try {
          await chatSessionStore.createChatSession(paper.value?.paper_id);
          chatId = chatSessionStore.getChatId();
          chatSessionId.value = chatId;
          console.log('Created new global chat session:', chatId);
        } catch (e) {
          console.error('Error creating chat session:', e);
          chatError.value = 'Failed to create chat session';
          return null;
        }
      }
      
      return chatId;
    };

    // Handle file upload
    const handleFileUpload = async (event) => {
      const files = event.target.files;
      if (!files || files.length === 0) return;
      
      // 重置自动滚动
      shouldAutoScroll.value = true;
      
      // 处理上传的每个文件
      for (let i = 0; i < files.length; i++) {
        const file = files[i];
        
        // 为文件创建URL
        const fileUrl = URL.createObjectURL(file);
        
        // 添加到上传文件列表
        uploadedPdfs.value.push({
          name: file.name,
          size: file.size,
          url: fileUrl,
          uploadedAt: new Date()
        });
      }
      
      // 默认不选中任何PDF，避免自动显示
      activeUploadedPdfIndex.value = -1;
      
      // 确保关闭PDF查看
      showPdf.value = false;
      // 不自动打开文件列表
      showFilesList.value = false;
      
      // 获取聊天会话ID
      const chatId = await getChatSession();
      if (!chatId) return;
      
      // 清空之前的待处理文件队列
      pendingFiles.value = [];
      currentProcessingIndex.value = 0;
      
      // 将所有文件添加到待处理队列
      for (let i = 0; i < files.length; i++) {
        pendingFiles.value.push(files[i]);
      }
      
      // 为上传的文件添加一条消息
      if (files.length === 1) {
        // 单文件上传
        chatMessages.value.push({
          role: 'user',
          content: `I've uploaded the paper: ${files[0].name}`
        });
        
        // 设置处理状态
        isProcessingFile.value = true;
        processingFileName.value = files[0].name;
        
        // 添加"正在处理"消息，告知用户可以通过文件按钮查看
        chatMessages.value.push({
          role: 'assistant',
          content: `I'm currently processing ${files[0].name}. Please wait while I analyze the document. This may take a moment depending on the size of the PDF. You can access the document anytime by clicking the file button in the top right corner.`
        });
      } else {
        // 多文件上传
        const fileNames = Array.from(files).map(f => f.name).join(', ');
        chatMessages.value.push({
          role: 'user',
          content: `I've uploaded ${files.length} papers: ${fileNames}`
        });
        
        // 设置处理状态
        isProcessingFile.value = true;
        processingFileName.value = files[0].name;
        
        // 添加"正在处理"消息，通知进度
        chatMessages.value.push({
          role: 'assistant',
          content: `I'm going to process all ${files.length} documents: ${fileNames}. Starting with ${files[0].name} (1/${files.length}). Please wait while I analyze these documents one by one. You can access any document anytime by clicking the file button in the top right corner.`
        });
      }
      
      // 开始上传第一个文件
      try {
        await api.uploadPdfToChat(chatId, pendingFiles.value[0]);
        
        // 开始定期检查处理状态
        if (statusCheckInterval.value) {
          clearInterval(statusCheckInterval.value);
        }
        statusCheckInterval.value = window.setInterval(checkProcessingStatus, 3000);
        
      } catch (e) {
        console.error('Error uploading PDF for RAG processing:', e);
        isProcessingFile.value = false;
        
        // 提取更详细的错误信息
        let errorMessage = "";
        if (e.response && e.response.data && e.response.data.detail) {
          errorMessage = e.response.data.detail;
        } else {
          errorMessage = "I encountered an error processing your file. It might be too large or complex.";
        }
        
        chatMessages.value.push({
          role: 'assistant',
          content: `${errorMessage} Please try uploading again with a smaller or simpler PDF.`
        });
      }
      
      // Reset file input
      event.target.value = '';
      
      // 滚动到底部
      nextTick(() => {
        smartScrollToBottom();
      });
    };
    
    // Download PDF directly
    const downloadPdf = async () => {
      if (!paper.value || !paper.value.pdf_url) return;
      
      try {
        // Get filename from URL
        const url = paper.value.pdf_url;
        
        // Create safe filename from paper title
        const sanitizedTitle = paper.value.title
          .replace(/[\/\\:*?"<>|]/g, '_') // Replace invalid chars with underscore
          .replace(/\s+/g, '_')          // Replace spaces with underscore
          .replace(/__+/g, '_')          // Replace multiple underscores with single
          .replace(/^_+|_+$/g, '')       // Remove leading/trailing underscores
          .substring(0, 200);            // Limit length to avoid too long filenames
        
        const filename = `${sanitizedTitle}.pdf`;
        
        // Fetch the PDF
        const response = await fetch(url);
        const blob = await response.blob();
        
        // Create download link
        const downloadUrl = window.URL.createObjectURL(blob);
        const link = document.createElement('a');
        link.href = downloadUrl;
        link.download = filename;
        
        // Append to document, click and remove
        document.body.appendChild(link);
        link.click();
        document.body.removeChild(link);
        
        // Clean up the URL object
        setTimeout(() => {
          window.URL.revokeObjectURL(downloadUrl);
        }, 100);
      } catch (e) {
        console.error('Error downloading PDF:', e);
        // Fallback to opening in new tab if download fails
        window.open(paper.value.pdf_url, '_blank');
      }
    };
    
    // Toggle chat mode
    const toggleChatMode = async () => {
      chatMode.value = !chatMode.value;
      
      if (!chatMode.value) {
        // 退出聊天模式时清理上传的PDF和缓存
        // 清理所有创建的对象URL
        uploadedPdfs.value.forEach(pdf => {
          if (pdf.url) {
            URL.revokeObjectURL(pdf.url);
          }
        });
        
        // 不再结束聊天会话，保留全局状态
        
        // 重置上传的PDF相关状态
        uploadedPdfs.value = [];
        activeUploadedPdfIndex.value = -1;
        showPdf.value = false;
        showFilesList.value = false;
        
        // 清空聊天消息
        chatMessages.value = [];
      } else if (chatMode.value) {
        // 使用全局会话
        try {
          // 获取或创建会话
          await getChatSession();
          
          // 检查是否成功获取会话ID
          if (chatSessionId.value) {
            // 添加问候消息
            chatMessages.value.push({
              role: 'assistant',
              content: `Hello! I'm an AI assistant that can help you understand the paper: "${paper.value.title}". 

**Important:** Please upload the PDF of this paper using the "Upload PDF" button above. Without the PDF, I can only provide general information based on the title and abstract. With the PDF, I can analyze the paper in detail including methodology, results, figures, and tables.

What would you like to know about this paper?`
            });
            
            // 如果没有上传的PDF文件且paper.value存在，尝试自动从OSS加载PDF
            if (uploadedPdfs.value.length === 0 && paper.value && paper.value.paper_id) {
              try {
                // 设置处理状态
                isProcessingFile.value = true;
                processingFileName.value = `${paper.value.title}.pdf`;
                
                // 添加一条提示消息
                chatMessages.value.push({
                  role: 'system',
                  content: `正在从OSS自动加载论文"${paper.value.title}"的PDF文件，请稍候...`
                });
                
                // 滚动到底部
                nextTick(() => {
                  smartScrollToBottom();
                });
                
                // 调用API加载论文
                const response = await api.loadPaperFromOss(chatSessionId.value, paper.value.paper_id);
                
                // 添加一条成功消息
                chatMessages.value.push({
                  role: 'system',
                  content: `已成功加载论文"${paper.value.title}"的PDF文件，现在可以开始提问了。`
                });
                
                // 重新加载会话文件列表
                const files = await api.getSessionFiles(chatSessionId.value);
                
                // 更新上传的PDF列表
                uploadedPdfs.value = files.map(file => ({
                  name: file.name,
                  size: file.size,
                  url: `/api/chat/files/${file.id}/view?no_download=true`,
                  uploadedAt: new Date(file.upload_time)
                }));
                
                // 滚动到底部
                nextTick(() => {
                  smartScrollToBottom();
                });
              } catch (error) {
                console.error('Failed to auto-load paper PDF:', error);
                let errorMsg = '未知错误';
                
                if (error.response && error.response.data) {
                  errorMsg = error.response.data.detail || error.response.statusText;
                } else if (error.message) {
                  errorMsg = error.message;
                }
                
                // 添加一条错误消息
                chatMessages.value.push({
                  role: 'system',
                  content: `无法自动加载论文PDF文件: ${errorMsg}。请使用"Upload PDF"按钮手动上传。`
                });
              } finally {
                // 重置处理状态
                isProcessingFile.value = false;
                
                // 滚动到底部
                nextTick(() => {
                  smartScrollToBottom();
                });
              }
            }
          }
        } catch (e) {
          console.error('Error getting chat session:', e);
          chatError.value = 'Failed to initialize chat session';
          
          // 添加一个简单的问候消息作为回退
          chatMessages.value.push({
            role: 'assistant',
            content: `Hello! I'm an AI assistant that can help you understand this paper. Please upload the PDF using the button above for detailed assistance.`
          });
        }
      }
    };
    
    // Send a chat message to the backend
    const sendChatMessage = async () => {
      if (!chatInput.value.trim() || isChatLoading.value || isProcessingFile.value) return;
      
      // Add user message to chat
      const userMessage = chatInput.value.trim();
      chatMessages.value.push({ role: 'user', content: userMessage });
      chatInput.value = ''; // Clear input
      isChatLoading.value = true;
      
      // 重置自动滚动
      shouldAutoScroll.value = true;
      
      // 添加一个空的助手消息，用于流式填充内容
      const assistantMessageIndex = chatMessages.value.length;
      chatMessages.value.push({
        role: 'assistant',
        content: ''
      });
      
      // 发送消息后滚动到底部
      nextTick(() => {
        smartScrollToBottom();
      });
      
      try {
        // 确保我们有一个有效的聊天会话ID
        if (!chatSessionId.value) {
          await getChatSession();
        }
        
        // 发送消息到会话
        await api.sendChatMessage(
          chatSessionId.value,
          userMessage,
          // 流式回调处理函数
          (content, isDone) => {
            // 将内容追加到当前助手消息
            if (content) {
              chatMessages.value[assistantMessageIndex].content += content;
              
              // 每次有新内容时，根据用户位置决定是否滚动到底部
              nextTick(() => {
                smartScrollToBottom();
              });
            }
            
            // 如果是最后一个块，完成加载
            if (isDone) {
              isChatLoading.value = false;
            }
          }
        );
      } catch (e) {
        console.error('Error in chat:', e);
        chatError.value = 'Failed to get a response. Please try again.';
        // 如果出错，更新消息内容
        chatMessages.value[assistantMessageIndex].content = 
          'Sorry, I encountered an error processing your request. Please try again.';
        isChatLoading.value = false;
      }
    };
    
    // Go back to previous page
    const goBack = () => {
      // Save previous page scroll position to sessionStorage
      if (document.referrer.includes(window.location.host)) {
        // Get the referring page path
        const referrer = new URL(document.referrer).pathname;
        // Restore the previously saved scroll position to sessionStorage
        sessionStorage.setItem(`scrollPos-${referrer}`, '0');
      }
      router.go(-1);
    };
    
    // Clean up resources when component unmounts
    const cleanup = () => {
      // 清理所有创建的对象URL
      uploadedPdfs.value.forEach(pdf => {
        if (pdf.url) {
          URL.revokeObjectURL(pdf.url);
        }
      });
    };
    
    // 删除文件
    const deleteFile = (index) => {
      // 如果删除的是当前显示的文件
      if (index === activeUploadedPdfIndex.value) {
        // 如果是最后一个文件，关闭PDF查看器
        if (uploadedPdfs.value.length === 1) {
          showPdf.value = false;
          activeUploadedPdfIndex.value = -1;
        } else {
          // 如果不是最后一个文件，则显示前一个或后一个文件
          activeUploadedPdfIndex.value = index === 0 ? 0 : index - 1;
        }
      } else if (index < activeUploadedPdfIndex.value) {
        // 如果删除的文件在当前显示文件之前，调整索引
        activeUploadedPdfIndex.value--;
      }
      
      // 释放对象URL
      if (uploadedPdfs.value[index].url) {
        URL.revokeObjectURL(uploadedPdfs.value[index].url);
      }
      
      // 从数组中移除该文件
      uploadedPdfs.value.splice(index, 1);
      
      // 如果没有文件了，关闭文件列表
      if (uploadedPdfs.value.length === 0) {
        showFilesList.value = false;
      }
    };
    
    // 控制自动滚动的变量
    const shouldAutoScroll = ref(true);
    const isUserScrolling = ref(false);
    
    // 检测用户是否在底部
    const checkIfUserAtBottom = () => {
      if (!chatMessagesEl.value) return true;
      
      const element = chatMessagesEl.value;
      const scrollBottom = element.scrollHeight - element.scrollTop - element.clientHeight;
      // 如果用户距离底部很近(20px以内)，认为用户在底部
      return scrollBottom < 20;
    };
    
    // 处理用户滚动事件
    const handleUserScroll = () => {
      if (!chatMessagesEl.value) return;
      
      isUserScrolling.value = true;
      shouldAutoScroll.value = checkIfUserAtBottom();
      
      // 防抖：用户停止滚动200ms后重置状态
      setTimeout(() => {
        isUserScrolling.value = false;
      }, 200);
    };
    
    // 智能滚动到底部（只有用户在底部时才滚动）
    const smartScrollToBottom = () => {
      if (!chatMessagesEl.value || isUserScrolling.value) return;
      
      if (shouldAutoScroll.value) {
        const element = chatMessagesEl.value;
        element.scrollTop = element.scrollHeight;
      }
    };
    
    const scrollToBottom = () => {
      if (chatMessagesEl.value && shouldAutoScroll.value) {
        const element = chatMessagesEl.value;
        element.scrollTop = element.scrollHeight;
      }
    };
    
    // Fetch paper details
    onMounted(async () => {
      const paperId = route.params.id;
      
      if (!paperId) {
        error.value = 'Paper ID is required';
        isLoading.value = false;
        return;
      }
      
      try {
        // Get paper details
        paper.value = await api.getPaperById(paperId);
        
        // Record paper view
        try {
          await api.recordPaperView(paperId);
        } catch (e) {
          console.error('Error recording paper view:', e);
          // Does not affect main process, only logs the error
        }
      } catch (e) {
        console.error('Error fetching paper details:', e);
        error.value = 'Failed to fetch paper details. Please try again later.';
      } finally {
        isLoading.value = false;
      }
      
      // 清理资源
      window.addEventListener('beforeunload', cleanup);
    });
    
    // 组件卸载时清理资源
    onBeforeUnmount(() => {
      cleanup();
      window.removeEventListener('beforeunload', cleanup);
      
      // 不再结束聊天会话，保留在全局状态中
      console.log('Paper detail component unmounting, keeping global session:', chatSessionId.value);
    });
    
    // 监听全局会话状态
    watch(() => chatSessionStore.state.chatId, (newChatId) => {
      if (newChatId && newChatId !== chatSessionId.value) {
        chatSessionId.value = newChatId;
        console.log('Updated chat session ID from global store:', newChatId);
      }
    });
    
    return {
      paper,
      isLoading,
      error,
      showPdf,
      formattedDate,
      togglePdfViewer,
      goBack,
      chatMode,
      toggleChatMode,
      chatInput,
      chatMessages,
      isChatLoading,
      sendChatMessage,
      chatMessagesEl,
      handleFileUpload,
      downloadPdf,
      getCategoryLabel,
      uploadedPdfs,
      activeUploadedPdfIndex,
      activeUploadedPdf,
      formatFileSize,
      showFilesList,
      toggleFilesList,
      selectPdfAndCloseList,
      isProcessingFile,
      processingFileName,
      pendingFiles,
      currentProcessingIndex,
      deleteFile,
      closePdf,
      handleUserScroll,
      shouldAutoScroll,
      scrollToBottom
    };
  }
})
</script>

<style scoped>
.paper-detail {
  max-width: 1200px;
  margin: 0 auto;
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

.back-link {
  display: inline-block;
  margin-top: 1rem;
  color: #3f51b5;
  text-decoration: none;
}

.paper-container {
  background-color: white;
  border-radius: 8px;
  padding: 2rem;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
}

/* Split layout */
.split-layout {
  display: flex;
  gap: 2rem;
  padding: 0;
  max-height: 90vh;
  overflow: hidden;
  justify-content: center;
}

.split-layout .paper-content {
  flex: 0 0 35%;
  min-width: 350px;
  padding: 1.8rem;
  overflow-y: auto;
  max-height: 90vh;
}

.split-layout .pdf-section {
  flex: 1;
  margin: 0;
  height: 90vh;
  display: flex;
  justify-content: flex-start;
}

.paper-header {
  margin-bottom: 2rem;
}

.paper-title {
  margin-top: 0;
  margin-bottom: 1rem;
  font-size: 1.6rem;
  line-height: 1.4;
  color: #333;
  word-wrap: break-word;
}

.paper-meta {
  display: flex;
  flex-wrap: wrap;
  justify-content: space-between;
  margin-bottom: 1rem;
  color: #555;
}

.paper-meta > div {
  margin-bottom: 0.5rem;
}

.paper-categories {
  margin-bottom: 1.5rem;
}

.category-tag {
  display: inline-block;
  background-color: #e3f2fd;
  color: #1976d2;
  padding: 0.25rem 0.75rem;
  border-radius: 4px;
  font-size: 0.9rem;
  margin-right: 0.5rem;
  margin-bottom: 0.5rem;
}

.paper-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 1rem;
  margin-bottom: 2rem;
}

.action-button {
  padding: 0.75rem 1.5rem;
  border-radius: 4px;
  text-decoration: none;
  font-size: 1rem;
  transition: all 0.2s;
  display: inline-block;
  border: none;
  cursor: pointer;
}

.action-button.primary {
  background-color: #3f51b5;
  color: white;
}

.action-button.primary:hover {
  background-color: #303f9f;
}

.action-button:not(.primary) {
  background-color: #f0f0f0;
  color: #333;
}

.action-button:not(.primary):hover {
  background-color: #e0e0e0;
}

.pdf-section {
  margin-bottom: 2rem;
  width: 100%;
  height: 80vh;
  position: relative;
}

.pdf-iframe {
  width: 100%;
  height: 100%;
  border: none;
}

/* Chat interface */
.chat-interface {
  display: flex;
  flex-direction: column;
  height: 100%;
}

.chat-header {
  display: flex;
  flex-direction: column;
  margin-bottom: 1rem;
  padding-bottom: 1rem;
  border-bottom: 1px solid #eee;
}

.header-main {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 1rem;
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
}

.file-list-toggle {
  display: flex;
  align-items: center;
  justify-content: center;
  background-color: #f0f0f0;
  border: none;
  padding: 0.5rem 0.6rem;
  border-radius: 4px;
  cursor: pointer;
  position: relative;
  transition: all 0.2s;
  width: 36px;
  height: 36px;
}

.file-list-toggle.active {
  background-color: #e3f2fd;
  color: #1976d2;
}

.file-list-toggle .icon-svg {
  width: 20px;
  height: 20px;
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
  min-width: 18px;
  height: 18px;
  display: flex;
  align-items: center;
  justify-content: center;
}

.chat-container {
  display: flex;
  flex-direction: column;
  flex: 1;
  min-height: 0;
  width: 100%;
}

/* PDF Files List Overlay */
.pdf-files-list-overlay {
  position: fixed;
  top: 0;
  right: 0;
  bottom: 0;
  left: 0;
  background-color: rgba(0, 0, 0, 0.5);
  z-index: 100;
  display: flex;
  justify-content: flex-end;
}

.pdf-files-panel {
  width: 300px;
  background-color: white;
  height: 100%;
  overflow-y: auto;
  display: flex;
  flex-direction: column;
  box-shadow: -2px 0 10px rgba(0, 0, 0, 0.1);
}

.panel-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 1rem;
  border-bottom: 1px solid #eee;
}

.panel-header h3 {
  margin: 0;
  font-size: 1.2rem;
  color: #333;
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
  gap: 0.5rem;
  flex: 1;
  overflow-y: auto;
}

.pdf-file-item {
  display: flex;
  align-items: center;
  padding: 0.75rem;
  border-radius: 4px;
  cursor: pointer;
  transition: background-color 0.2s;
}

.pdf-file-item:hover {
  background-color: #f5f5f5;
}

.pdf-file-item.active {
  background-color: #e3f2fd;
}

.pdf-file-icon {
  margin-right: 0.75rem;
}

.pdf-file-info {
  flex: 1;
  overflow: hidden;
  cursor: pointer;
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
}

.pdf-file-delete:hover {
  background-color: #ffebee;
  color: #e53935;
  opacity: 1;
}

.pdf-file-item:hover .pdf-file-delete {
  opacity: 1;
}

.pdf-file-name {
  font-size: 0.95rem;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  margin-bottom: 0.25rem;
}

.pdf-file-size {
  font-size: 0.8rem;
  color: #777;
}

.pdf-actions {
  display: flex;
  gap: 1rem;
  margin-bottom: 1rem;
  width: 100%;
}

.pdf-action-button {
  display: inline-flex;
  align-items: center;
  padding: 0.6rem 1rem;
  background-color: #f5f5f5;
  color: #333;
  border: 1px solid #ddd;
  border-radius: 4px;
  cursor: pointer;
  text-decoration: none;
  font-size: 0.9rem;
  transition: all 0.2s;
  flex: 1;
  justify-content: center;
  gap: 8px;
}

.pdf-action-button.download {
  background-color: #e3f2fd;
  color: #1976d2;
  border-color: #bbdefb;
}

.pdf-action-button.download:hover {
  background-color: #bbdefb;
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
}

.chat-messages {
  flex: 1;
  overflow-y: auto;
  padding: 1rem;
  background-color: #f9f9f9;
  border-radius: 8px;
  margin-bottom: 1rem;
  min-height: 300px;
  max-height: 60vh;
}

.chat-message {
  margin-bottom: 1rem;
  padding: 0.75rem 1rem;
  border-radius: 8px;
  max-width: 85%;
}

.user-message {
  background-color: #e3f2fd;
  color: #0d47a1;
  margin-left: auto;
  border-top-right-radius: 0;
}

.assistant-message {
  background-color: #f5f5f5;
  color: #333;
  margin-right: auto;
  border-top-left-radius: 0;
}

.message-content {
  line-height: 1.5;
  white-space: pre-line;
}

/* 打字动画效果 */
.assistant-message.typing .message-content::after {
  content: "";
  width: 6px;
  height: 15px;
  background: #3f51b5;
  display: inline-block;
  margin-left: 2px;
  animation: blink 1s step-start infinite;
}

@keyframes blink {
  50% { opacity: 0; }
}

/* 当AI完成回复时，不显示光标 */
.assistant-message:not(:last-child) .message-content::after,
.assistant-message:last-child:not(.typing) .message-content::after {
  display: none;
}

.chat-input-container {
  display: flex;
  gap: 0.5rem;
}

.chat-input {
  flex: 1;
  padding: 0.75rem;
  border: 1px solid #ddd;
  border-radius: 4px;
  resize: none;
  min-height: 50px;
  font-family: inherit;
  font-size: 1rem;
}

.chat-send-button {
  padding: 0.75rem 1.5rem;
  background-color: #3f51b5;
  color: white;
  border: none;
  border-radius: 4px;
  cursor: pointer;
  font-size: 1rem;
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
}

@keyframes spin {
  0% { transform: rotate(0deg); }
  100% { transform: rotate(360deg); }
}

.paper-abstract h2 {
  margin-top: 0;
  font-size: 1.3rem;
  color: #333;
  margin-bottom: 0.8rem;
}

.paper-abstract p {
  line-height: 1.6;
  margin-top: 0;
  white-space: pre-line;
}

@media (max-width: 768px) {
  .split-layout {
    flex-direction: column;
    max-height: none;
    padding: 0;
  }
  
  .split-layout .paper-content,
  .split-layout .pdf-section {
    flex: none;
    width: 100%;
    min-width: 0;
    max-height: none;
    height: auto;
  }
  
  .split-layout .pdf-section {
    height: 70vh;
    margin-top: 1rem;
  }
  
  .pdf-actions {
    flex-direction: column;
  }
  
  .pdf-files-panel {
    width: 80%;
  }
}

.icon-svg {
  width: 20px;
  height: 20px;
}

.pdf-file-icon .icon-svg {
  width: 24px;
  height: 24px;
  color: #1976d2;
}

.pdf-action-button {
  display: inline-flex;
  align-items: center;
  padding: 0.6rem 1rem;
  background-color: #f5f5f5;
  color: #333;
  border: 1px solid #ddd;
  border-radius: 4px;
  cursor: pointer;
  text-decoration: none;
  font-size: 0.9rem;
  transition: all 0.2s;
  flex: 1;
  justify-content: center;
  gap: 8px;
}

.pdf-action-button .icon-svg {
  color: currentColor;
}

.pdf-viewer-header {
  display: none;
}

.pdf-viewer-header h3 {
  display: none;
}

.close-pdf-btn {
  position: absolute;
  top: 10px;
  right: 10px;
  z-index: 10;
  background-color: rgba(255, 255, 255, 0.7);
  border: none;
  border-radius: 50%;
  width: 36px;
  height: 36px;
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  box-shadow: 0 2px 5px rgba(0, 0, 0, 0.2);
  transition: all 0.2s;
}

.close-pdf-btn:hover {
  background-color: rgba(255, 255, 255, 0.9);
  transform: scale(1.1);
}

.close-pdf-btn .icon-svg {
  width: 24px;
  height: 24px;
  color: #333;
}
</style> 