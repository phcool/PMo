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
          </div>
          
          <!-- Paper tags standalone component -->
          <div v-if="isSearchingPapers || relatedPapers.length > 0" class="paper-tags-container standalone">
            <div class="paper-tags-header">
              <svg class="icon-svg" viewBox="0 0 24 24">
                <path d="M12,9A3,3 0 0,0 9,12A3,3 0 0,0 12,15A3,3 0 0,0 15,12A3,3 0 0,0 12,9M12,17A5,5 0 0,1 7,12A5,5 0 0,1 12,7A5,5 0 0,1 17,12A5,5 0 0,1 12,17M12,4.5C7,4.5 2.73,7.61 1,12C2.73,16.39 7,19.5 12,19.5C17,19.5 21.27,16.39 23,12C21.27,7.61 17,4.5 12,4.5Z" />
              </svg>
              <span v-if="isSearchingPapers">Searching for related papers...</span>
              <span v-else>Related papers found:</span>
            </div>
            
            <!-- Search in progress state -->
            <div v-if="isSearchingPapers" class="paper-search-loading">
              <div class="loader-circle"></div>
              <div class="search-message">Searching, please wait...</div>
            </div>
            
            <!-- Paper tags list -->
            <div v-else class="paper-tags-list">
              <a v-for="(paper, index) in relatedPapers" 
                 :key="index" 
                 :href="paper.url" 
                 target="_blank" 
                 class="paper-tag"
                 :title="paper.title">
                <svg class="icon-svg" viewBox="0 0 24 24">
                  <path d="M14,2H6A2,2 0 0,0 4,4V20A2,2 0 0,0 6,22H18A2,2 0 0,0 20,20V8L14,2M18,20H6V4H13V9H18V20Z" />
                </svg>
                <span class="paper-tag-title">{{ paper.title.length > 70 ? paper.title.substring(0, 70) + '...' : paper.title }}</span>
              </a>
              <!-- No papers found message -->
              <div v-if="relatedPapers.length === 0" class="no-papers-found">
                No related papers found
              </div>
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
              <div class="chat-input-wrapper" :class="{ 'search-mode': isSearchMode }">
                <textarea 
                  ref="inputField" 
                  v-model="userInput"
                  @keydown.enter.exact.prevent="sendMessage"
                  :placeholder="getPlaceholderText()"
                  :disabled="isLoading || isProcessingFile"
                  class="chat-input"
                ></textarea>
                <div class="input-actions">
                  <label class="action-button" :class="{ disabled: isLoading || isProcessingFile }">
                    <svg class="icon-svg" viewBox="0 0 24 24">
                      <path d="M19,13H13V19H11V13H5V11H11V5H13V11H19V13Z" />
                    </svg>
                    <input 
                      type="file" 
                      accept=".pdf" 
                      @change="handleFileUpload" 
                      style="display: none;"
                      :disabled="isLoading || isProcessingFile"
                    >
                  </label>
                  <button 
                    class="action-button" 
                    :class="{ 
                      disabled: isLoading || isProcessingFile,
                      active: isSearchMode
                    }"
                    title="Toggle search mode"
                    @click="toggleSearchMode"
                  >
                    <svg class="icon-svg" viewBox="0 0 24 24">
                      <path d="M9.5,3A6.5,6.5 0 0,1 16,9.5C16,11.11 15.41,12.59 14.44,13.73L14.71,14H15.5L20.5,19L19,20.5L14,15.5V14.71L13.73,14.44C12.59,15.41 11.11,16 9.5,16A6.5,6.5 0 0,1 3,9.5A6.5,6.5 0 0,1 9.5,3M9.5,5C7,5 5,7 5,9.5C5,12 7,14 9.5,14C12,14 14,12 14,9.5C14,7 12,5 9.5,5Z" />
                    </svg>
                  </button>
                </div>
              </div>
              <button 
                @click="sendMessage" 
                :disabled="isLoading || !userInput.trim() || isProcessingFile"
                class="chat-send-button"
                :class="{ 'search-mode': isSearchMode }"
              >
                <span v-if="isLoading">⏳</span>
                <span v-else-if="isProcessingFile">⌛</span>
                <span v-else>{{ isSearchMode ? 'Search' : 'Send' }}</span>
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
          <object 
            :data="currentPdfUrl" 
            type="application/pdf"
            class="pdf-iframe" 
            @load="isPdfLoading = false"
            :style="{ opacity: isPdfLoading ? 0 : 1 }"
          >
            <div class="pdf-fallback">
              Unable to display PDF directly, <a :href="currentPdfUrl" target="_blank">click here</a> to open in a new window
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
import { chatSessionStore } from '../stores/chatSession';

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || '';

const route = useRoute();
const router = useRouter();
const toast = useToast();

// Chat session data
const chatId = ref(null);
const messages = ref([]);
const userInput = ref('');
const isLoading = ref(false);  // Message loading status
const initialLoading = ref(true);  // Initial loading status
const isTyping = ref(false);
const currentTypingMessageId = ref(null); // Current typing message ID
const messagesContainer = ref(null);
const inputField = ref(null);
const error = ref(null);

// Search related
const isSearchMode = ref(false); // Whether in search mode
const isSearchingPapers = ref(false); // Whether searching for papers
const currentSearchQuery = ref(''); // Current search query

// PDF file management
const pdfFiles = ref([]);
const showFilesList = ref(false);
const showPdf = ref(false);
const currentPdfUrl = ref(null);
const selectedFileId = ref(null);
const isProcessingFile = ref(false);
const processingFileName = ref('');
const isPdfLoading = ref(false); // PDF loading status
const currentFileName = ref('Document'); // Current PDF filename

// PDF file upload progress
const isUploading = ref(false);
const uploadProgress = ref(0);
const pendingFiles = ref([]);
const currentProcessingIndex = ref(0);

// Related papers status
const relatedPapers = ref([]);
const relatedPapersMessageId = ref(null);

// Calculate input placeholder text
const inputPlaceholder = computed(() => {
  if (isProcessingFile.value) {
    return pendingFiles.value.length > 1 
      ? `Please wait while I process ${processingFileName.value}... (${currentProcessingIndex.value + 1}/${pendingFiles.value.length})` 
      : `Please wait while I process ${processingFileName.value}...`;
  }
  return isSearchMode.value ? 'Type your search query...' : 'Type your question...';
});

// Initialization
onMounted(async () => {
  try {
    initialLoading.value = true;
    error.value = null;
    
    // 使用全局会话或特定路由参数会话
    if (route.params.id) {
      // 如果URL中有会话ID，使用该ID
      chatId.value = route.params.id;
      // 更新全局会话状态
      chatSessionStore.setChatId(chatId.value);
    } else if (chatSessionStore.hasActiveSession()) {
      // 如果全局已有会话，使用全局会话
      chatId.value = chatSessionStore.getChatId();
      // 更新URL
      router.push({ name: 'chat', params: { id: chatId.value } });
    } else {
      // 如果全局没有会话，则创建新会话
      await createChatSession();
    }
    
    // 加载会话消息和文件
    await loadChatSession();
    await loadSessionFiles();
    
    // 检查是否有待处理的论文ID
    const pendingPaperId = localStorage.getItem('pendingChatPaperId');
    if (pendingPaperId) {
      console.log(`Found pending paper ID: ${pendingPaperId}, downloading PDF...`);
      
      // 清除存储，避免重复处理
      localStorage.removeItem('pendingChatPaperId');
      
      // 开始处理论文
      await handlePendingPaperDownload(pendingPaperId);
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
  
  // Setup highlighting
  marked.setOptions({
    highlight: function(code, lang) {
      if (lang && hljs.getLanguage(lang)) {
        return hljs.highlight(code, { language: lang }).value;
      }
      return hljs.highlightAuto(code).value;
    }
  });
});

// Create new chat session
async function createChatSession() {
  try {
    isLoading.value = true;
    
    // 使用全局会话服务创建会话
    if (!chatSessionStore.hasActiveSession()) {
      await chatSessionStore.createChatSession();
    }
    
    // 从全局存储获取会话ID
    chatId.value = chatSessionStore.getChatId();
    
    // 更新URL以包含会话ID
    router.push({ name: 'chat', params: { id: chatId.value } });
    console.log('Using global chat session:', chatId.value);
  } catch (error) {
    console.error('Session creation failed:', error);
    toast.error('Failed to create chat session. Please try again.');
    // Don't set global error, just show toast message
  } finally {
    isLoading.value = false;
  }
}

// Load existing chat session
async function loadChatSession() {
  try {
    isLoading.value = true;
    const response = await axios.get(`${API_BASE_URL}/api/chat/sessions/${chatId.value}/messages`);
    
    // Get message list from API response structure
    if (response.data.messages) {
      messages.value = response.data.messages;
    } else {
      messages.value = [];
    }
    
    console.log('Loaded chat history:', messages.value.length);
    
    // Scroll to bottom
    await nextTick();
    scrollToBottom();
  } catch (error) {
    console.error('Failed to load session:', error);
    toast.error('Failed to load chat history. Please try again.');
    // Don't set global error, just show toast message
  } finally {
    isLoading.value = false;
  }
}

// Load session-related files
async function loadSessionFiles() {
  try {
    const response = await axios.get(`${API_BASE_URL}/api/chat/sessions/${chatId.value}/files`);
    pdfFiles.value = response.data;
    console.log('Loaded files:', pdfFiles.value.length);
  } catch (error) {
    console.error('Failed to load files:', error);
    toast.error('Failed to load file list');
    // Don't set global error, just show toast message
  }
}

// Toggle search mode
function toggleSearchMode() {
  isSearchMode.value = !isSearchMode.value;
  
  // Clear previous search results and status
  if (isSearchMode.value) {
    relatedPapers.value = [];
    isSearchingPapers.value = false;
    currentSearchQuery.value = '';
  } else {
    // When exiting search mode, clear papers if not in response
    if (!isSearchingPapers.value) {
      relatedPapers.value = [];
    }
  }
  
  // Focus input field
  if (isSearchMode.value) {
    nextTick(() => {
      if (inputField.value) {
        inputField.value.focus();
      }
    });
  }
}

// Send message or execute search
async function sendMessage() {
  if (!userInput.value.trim() || isLoading.value) return;
  
  const messageContent = userInput.value.trim();
  userInput.value = '';
  
  // If in search mode, first get relevant papers
  if (isSearchMode.value) {
    try {
      // Save current search query
      currentSearchQuery.value = messageContent;
      
      // Show searching status
      isSearchingPapers.value = true;
      
      // Send search request to get relevant papers
      const response = await fetch(`${API_BASE_URL}/api/papers/search`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ query: messageContent }),
      });
      
      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }
      
      const searchResults = await response.json();
      
      // Update related papers
      if (searchResults.papers && Array.isArray(searchResults.papers)) {
        relatedPapers.value = searchResults.papers;
        console.log(`Found ${relatedPapers.value.length} papers from direct search API`);
      } else {
        relatedPapers.value = [];
      }
      
      // Ensure UI updates
      await nextTick();
      
    } catch (error) {
      console.error('Paper search failed:', error);
      toast.error('Failed to search for papers');
      relatedPapers.value = [];
    } finally {
      isSearchingPapers.value = false;
    }
  }
  
  // Add user message to UI
  const userMessage = {
    id: Date.now().toString(),
    role: 'user',
    content: messageContent, // Display original content directly
    created_at: new Date().toISOString()
  };
  
  messages.value.push(userMessage);
  
  // Scroll to bottom
  await nextTick();
  scrollToBottom();
  
  // Start processing reply
  try {
    isLoading.value = true;
    isTyping.value = true;
    
    // Add an empty assistant message as placeholder
    const assistantMessage = {
      id: (Date.now() + 1).toString(),
      role: 'assistant',
      content: '',
      created_at: new Date().toISOString()
    };
    
    currentTypingMessageId.value = assistantMessage.id;
    messages.value.push(assistantMessage);
    
    // Use streaming response to get reply
    const finalContent = isSearchMode.value 
      ? `[SEARCH] ${messageContent}` // Add prefix to search mode messages
      : messageContent;
      
    await streamChatResponse(finalContent, assistantMessage);
    
    // If in search mode, exit after sending message
    if (isSearchMode.value) {
      isSearchMode.value = false;
    }
  } catch (err) {
    console.error('Failed to send message:', err);
    toast.error('Failed to send message. Please try again.');
    
    // Remove the last empty assistant message
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

// Stream chat response
async function streamChatResponse(userMessage, assistantMessage) {
  try {
    // Clear previous search results, but keep papers if already retrieved through direct search
    if (isSearchMode.value && !isSearchingPapers.value && relatedPapers.value.length === 0) {
      relatedPapers.value = [];
    }

    // Send request
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
    
    // Process streaming response
    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    let receivedChunks = 0;
    let accumulatedData = '';  // Accumulated received data
    let papersDataFound = false;
    let shouldSkipPaperData = isSearchMode.value && relatedPapers.value.length > 0; // Skip processing if papers already retrieved
    
    // Message container reference - for direct DOM manipulation
    const messageEl = document.querySelector(`[data-message-id="${assistantMessage.id}"]`);
    
    // First data block check, prioritize paper data processing
    const firstReadResult = await reader.read();
    if (!firstReadResult.done) {
      const firstChunk = decoder.decode(firstReadResult.value, { stream: true });
      accumulatedData += firstChunk;
      
      // Immediately check if contains paper data
      if (accumulatedData.includes('<!-- PAPERS_DATA:') && accumulatedData.includes(' -->') && !shouldSkipPaperData) {
        try {
          // Prioritize processing paper data
          accumulatedData = await processAndRemovePapersData(accumulatedData);
          papersDataFound = true;
          
          // Short delay to ensure UI updates
          await new Promise(resolve => setTimeout(resolve, 50));
        } catch (e) {
          console.error('Error processing papers data in first chunk:', e);
        }
      }
    }
    
    // Continue processing the remaining stream
    while (true) {
      const { done, value } = await reader.read();
      
      if (done) {
        // Final check to ensure no papers_data is missed
        if (accumulatedData.includes('<!-- PAPERS_DATA:') && accumulatedData.includes(' -->') && !shouldSkipPaperData) {
          try {
            await processAndRemovePapersData(accumulatedData);
            papersDataFound = true;
          } catch (e) {
            console.error('Error processing papers data at completion:', e);
          }
        }
        
        isTyping.value = false;
        // Scroll to bottom
        scrollToBottom();
        break;
      }
      
      // Decode data
      const chunk = decoder.decode(value, { stream: true });
      receivedChunks++;
      
      // Add new chunk to accumulated data
      accumulatedData += chunk;
      
      // Process papers_data tags
      if (accumulatedData.includes('<!-- PAPERS_DATA:') && accumulatedData.includes(' -->') && !shouldSkipPaperData) {
        try {
          // Process paper data and remove from accumulated data
          accumulatedData = await processAndRemovePapersData(accumulatedData);
          papersDataFound = true;
        } catch (e) {
          console.error('Error processing papers data:', e);
        }
      }
      
      try {
        // Try to parse JSON lines
        const lines = accumulatedData.split('\n');
        let remainingLines = [];
        
        for (let i = 0; i < lines.length; i++) {
          const line = lines[i];
          if (!line.trim()) continue;
          
          try {
            // Try to parse as JSON
            const jsonData = JSON.parse(line);
            // If successfully parsed, add to message content
            if (jsonData.content) {
              assistantMessage.content += jsonData.content;
              updateMessageDisplay(messageEl, assistantMessage.content);
            }
          } catch (e) {
            // If this line is not complete JSON, keep for next processing
            remainingLines.push(line);
          }
        }
        
        // Update accumulated data, only keeping unparsed parts
        accumulatedData = remainingLines.join('\n');
        
        // If there's remaining plain text data and doesn't contain papers_data tags, directly add to message
        if (accumulatedData && 
            (!accumulatedData.includes('<!-- PAPERS_DATA:') || shouldSkipPaperData) && 
            !accumulatedData.includes(' -->')) {
          assistantMessage.content += accumulatedData;
          updateMessageDisplay(messageEl, assistantMessage.content);
          accumulatedData = '';
        }
      } catch (e) {
        console.error('Error processing chunk:', e);
      }
    }

    // If in search mode but no paper data found, reset related papers
    if (isSearchMode.value && !papersDataFound && !shouldSkipPaperData && relatedPapers.value.length === 0) {
      relatedPapers.value = [];
    }
  } catch (error) {
    console.error('Failed to get streaming response:', error);
    assistantMessage.content = "Failed to get response. Please try again.";
    throw error; // Rethrow error for external function to handle
  }
}

// Helper function to process paper data
async function processAndRemovePapersData(data) {
  const papersDataMatch = data.match(/<!-- PAPERS_DATA:(.*?) -->/s);
  if (papersDataMatch && papersDataMatch[1]) {
    const papersData = JSON.parse(papersDataMatch[1]);
    if (papersData.type === 'papers_data' && Array.isArray(papersData.papers)) {
      // Update related papers data, triggers UI update - no longer associated with specific message
      relatedPapers.value = papersData.papers;
      console.log(`Found ${papersData.papers.length} papers, displaying as standalone component`);
      
      // Force DOM update to ensure paper tags display
      await nextTick();
    }
  }
  
  // Remove paper data tag and its content from text
  return data.replace(/<!-- PAPERS_DATA:.*? -->/s, '');
}

// Helper function to update message display
function updateMessageDisplay(messageEl, content) {
  if (messageEl) {
    // Create temporary div to parse HTML
    const tempDiv = document.createElement('div');
    tempDiv.innerHTML = DOMPurify.sanitize(marked(content));
    
    // Get content container and update
    const contentEl = messageEl.querySelector('.message-content');
    if (contentEl) {
      contentEl.innerHTML = tempDiv.innerHTML;
    }
  }
  
  // Scroll to bottom
  scrollToBottom();
}

// Handle file upload
async function handleFileUpload(event) {
  const files = event.target.files;
  if (!files || files.length === 0) return;
  
  try {
    isUploading.value = true;
    
    for (let i = 0; i < files.length; i++) {
      const file = files[i];
      
      // File size limit check (20MB)
      if (file.size > 20 * 1024 * 1024) {
        toast.error(`File ${file.name} is too large. Maximum size is 20MB.`);
        continue;
      }
      
      // Add to processing queue
      pendingFiles.value.push(file);
    }
    
    // Reset file input
    event.target.value = null;
    
    // Process files in queue
    if (pendingFiles.value.length > 0) {
      processNextFile();
    }
  } catch (error) {
    console.error('File upload failed:', error);
    toast.error('File upload failed. Please try again.');
    isUploading.value = false;
  }
}

// Process next file in queue
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
    
    // Add new file to list
    if (response.data) {
      pdfFiles.value.push(response.data);
      toast.success(`File ${file.name} uploaded successfully`);
    }
  } catch (error) {
    console.error('Failed to process file:', error);
    toast.error(`Failed to process file ${file.name}. Please try again.`);
  } finally {
    // Remove processed file and process next
    pendingFiles.value.shift();
    currentProcessingIndex.value++;
    
    if (pendingFiles.value.length > 0) {
      processNextFile();
    } else {
      isProcessingFile.value = false;
      processingFileName.value = '';
      uploadProgress.value = 0;
      isUploading.value = false;
      
      // Show file list
      showFilesList.value = true;
    }
  }
}

// Select PDF file
function handleSelectFile(file) {
  selectedFileId.value = file.id;
  isPdfLoading.value = true; // Start loading PDF
  currentFileName.value = file.name; // Set current filename
  
  // Ensure URL includes no_download=true parameter and add random parameter to avoid browser caching
  const timestamp = Date.now();
  currentPdfUrl.value = `${API_BASE_URL}/api/chat/files/${file.id}/view?no_download=true&t=${timestamp}`;
  showPdf.value = true;
  
  // If on mobile device, automatically close file list, only show PDF
  if (window.innerWidth <= 768) {
    showFilesList.value = false;
  }
}

// Delete file
async function deleteFile(file) {
  if (!confirm(`Are you sure you want to delete the file ${file.name}?`)) return;
  
  try {
    await axios.delete(`${API_BASE_URL}/api/chat/files/${file.id}`);
    
    // Remove from list
    pdfFiles.value = pdfFiles.value.filter(f => f.id !== file.id);
    
    // If currently displayed file is deleted, close preview
    if (selectedFileId.value === file.id) {
      closePdf();
    }
    
    toast.success(`File ${file.name} deleted successfully`);
  } catch (error) {
    console.error('Failed to delete file:', error);
    toast.error('Failed to delete file. Please try again.');
  }
}

// Toggle file list display
function toggleFilesList() {
  showFilesList.value = !showFilesList.value;
  
  // If file list is closed, also close PDF viewer
  if (!showFilesList.value) {
    closePdf();
  }
}

// Close PDF viewer
function closePdf() {
  currentPdfUrl.value = null;
  selectedFileId.value = null;
  showPdf.value = false;
  isPdfLoading.value = false;
  currentFileName.value = 'Document';
}

// Modify formatMessage function, simplify processing to avoid complex caching
function formatMessage(content) {
  if (!content) return '';
  
  // Process paper data tags - if any, remove them
  content = content.replace(/<!-- PAPERS_DATA:.*? -->/sg, '');
  
  // Use marked to convert markdown to HTML
  const html = marked(content);
  
  // Use DOMPurify to clean HTML
  return DOMPurify.sanitize(html);
}

// Format file size
function formatFileSize(bytes) {
  if (bytes === 0) return '0 Bytes';
  
  const k = 1024;
  const sizes = ['Bytes', 'KB', 'MB', 'GB'];
  const i = Math.floor(Math.log(bytes) / Math.log(k));
  
  return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
}

// Scroll to bottom
function scrollToBottom() {
  if (messagesContainer.value) {
    // Use requestAnimationFrame to ensure browser has rendered the latest content
    window.requestAnimationFrame(() => {
      messagesContainer.value.scrollTop = messagesContainer.value.scrollHeight;
    });
  }
}

// Watch PDF status, update body class when PDF is active
watch(() => showPdf.value && currentPdfUrl.value, (isPdfActive) => {
  if (isPdfActive) {
    document.body.classList.add('pdf-active-page');
  } else {
    document.body.classList.remove('pdf-active-page');
  }
});

// Improve watch to ensure scroll updates when messages change
watch(
  () => messages.value.map(m => m.content),
  () => {
    nextTick(() => {
      scrollToBottom();
    });
  },
  { deep: true }
);

// Remove body class when component is unmounted
onBeforeUnmount(() => {
  document.body.classList.remove('pdf-active-page');
});

// Return different placeholder based on current mode
function getPlaceholderText() {
  return isSearchMode.value ? 'Type your search query...' : 'Type your question...';
}

// 监听全局会话状态
watch(() => chatSessionStore.state.chatId, (newChatId) => {
  if (newChatId && newChatId !== chatId.value) {
    chatId.value = newChatId;
    
    // 如果路由参数中的ID与全局ID不匹配，更新路由
    if (route.params.id !== newChatId) {
      router.push({ name: 'chat', params: { id: newChatId } });
    }
  }
});

// 组件卸载前保留会话
onBeforeUnmount(() => {
  // 不再结束聊天会话，而是将其保留在全局状态中
  console.log('Chat component unmounting, keeping global session:', chatId.value);
});

// 处理待下载论文的函数
async function handlePendingPaperDownload(paperId) {
  try {
    // 先获取论文信息
    const paper = await axios.get(`${API_BASE_URL}/api/papers/${paperId}`);
    
    if (!paper || !paper.data) {
      toast.error('Failed to get paper information');
      return;
    }
    
    // 添加用户消息，表明正在处理论文
    messages.value.push({
      id: Date.now().toString(),
      role: 'user',
      content: `Please analyze the paper: "${paper.data.title}"`,
      created_at: new Date().toISOString()
    });
    
    // 设置处理状态
    isProcessingFile.value = true;
    processingFileName.value = `${paperId}.pdf`;
    
    // 添加"正在处理"消息
    messages.value.push({
      id: (Date.now() + 1).toString(),
      role: 'assistant',
      content: `I'm downloading and processing the paper "${paper.data.title}". This may take a moment depending on the size of the PDF. I'll let you know when it's ready for discussion.`,
      created_at: new Date().toISOString()
    });
    
    // 滚动到底部
    await nextTick();
    scrollToBottom();
    
    // 从OSS下载PDF并与会话关联
    const downloadResponse = await axios.post(`${API_BASE_URL}/api/papers/download-pdf-for-chat`, {
      paper_id: paperId,
      chat_id: chatId.value
    });
    
    if (downloadResponse.data.success) {
      // 启动处理状态检查
      if (statusCheckInterval) {
        clearInterval(statusCheckInterval);
      }
      
      // 每3秒检查一次处理状态
      statusCheckInterval = window.setInterval(checkProcessingStatus, 3000);
      
      console.log('PDF download initiated successfully');
    } else {
      // 下载失败
      isProcessingFile.value = false;
      messages.value.push({
        id: Date.now().toString(),
        role: 'assistant',
        content: 'Sorry, I was unable to download the paper. Please try uploading it manually.',
        created_at: new Date().toISOString()
      });
      
      // 滚动到底部
      await nextTick();
      scrollToBottom();
    }
  } catch (error) {
    console.error('Error downloading paper:', error);
    isProcessingFile.value = false;
    
    let errorMessage = 'Sorry, I was unable to download the paper. Please try uploading it manually.';
    if (error.response && error.response.data && error.response.data.detail) {
      errorMessage = `Error: ${error.response.data.detail}. Please try uploading the PDF manually.`;
    }
    
    messages.value.push({
      id: Date.now().toString(),
      role: 'assistant',
      content: errorMessage,
      created_at: new Date().toISOString()
    });
    
    // 滚动到底部
    await nextTick();
    scrollToBottom();
  }
}

// 检查文件处理状态
let statusCheckInterval = null;
onBeforeUnmount(() => {
  if (statusCheckInterval) {
    clearInterval(statusCheckInterval);
    statusCheckInterval = null;
  }
});

async function checkProcessingStatus() {
  try {
    const response = await axios.get(`${API_BASE_URL}/api/chat/sessions/${chatId.value}/processing-status`);
    
    // 更新处理状态
    isProcessingFile.value = response.data.processing;
    
    if (response.data.processing) {
      processingFileName.value = response.data.file_name || 'PDF';
    } else if (statusCheckInterval) {
      // 处理完成，停止检查
      clearInterval(statusCheckInterval);
      statusCheckInterval = null;
      
      // 添加处理完成消息
      messages.value.push({
        id: Date.now().toString(),
        role: 'assistant',
        content: `I've finished processing the paper. Now I can answer your questions about it. Feel free to ask me anything about the methodology, results, or any specific section of the paper.`,
        created_at: new Date().toISOString()
      });
      
      // 刷新文件列表
      await loadSessionFiles();
      
      // 滚动到底部
      await nextTick();
      scrollToBottom();
    }
  } catch (error) {
    console.error('Error checking processing status:', error);
    if (statusCheckInterval) {
      clearInterval(statusCheckInterval);
      statusCheckInterval = null;
    }
  }
}
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
  display: flex;
  align-items: center;
  justify-content: center;
  color: #757575;
  background: none;
  border: none;
  cursor: pointer;
  transition: all 0.2s;
  flex-shrink: 0;
  padding: 6px;
  border-radius: 50%;
  width: 32px;
  height: 32px;
}

.action-button:hover {
  color: #3f51b5;
}

.action-button.active {
  color: white;
  background-color: #3f51b5;
}

.action-button.disabled {
  opacity: 0.5;
  cursor: not-allowed;
  pointer-events: none;
}

.action-button .icon-svg {
  width: 20px;
  height: 20px;
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
}

.chat-section {
  display: flex;
  flex-direction: column;
  flex: 1;
  height: 100%;
  overflow: hidden;
  padding: 1rem;
}

.chat-header {
  display: flex;
  flex-direction: column;
  padding-bottom: 0.75rem;
}

.header-main {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 0.75rem;
}

.header-main h2 {
  margin: 0;
  font-size: 1.5rem;
  color: #333;
}

.header-actions {
  display: flex;
  gap: 8px;
}

.file-list-toggle {
  background: none;
  border: none;
  color: #555;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 0.4rem;
  position: relative;
  border-radius: 50%;
  width: 36px;
  height: 36px;
}

.file-list-toggle:hover {
  background-color: #f0f0f0;
}

.file-list-toggle.active {
  color: #3f51b5;
  background-color: #e8eaf6;
}

.file-count {
  position: absolute;
  top: -5px;
  right: -5px;
  background-color: #f44336;
  color: white;
  border-radius: 50%;
  width: 20px;
  height: 20px;
  font-size: 0.75rem;
  display: flex;
  align-items: center;
  justify-content: center;
}

.chat-container {
  flex: 1;
  display: flex;
  flex-direction: column;
  overflow: hidden;
  background-color: #f5f7fa;
  border-radius: 8px;
}

.chat-messages {
  flex: 1;
  overflow-y: auto;
  padding: 1rem;
  display: flex;
  flex-direction: column;
  gap: 1rem;
}

.chat-message {
  max-width: 80%;
  padding: 10px 14px;
  border-radius: 12px;
  position: relative;
  line-height: 1.5;
  display: flex;
  align-items: flex-start;
  margin-bottom: 0.5rem;
}

.chat-message.user-message {
  align-self: flex-end;
  background-color: #e3f2fd;
  color: #0d47a1;
  border-bottom-right-radius: 2px;
}

.chat-message.assistant-message {
  align-self: flex-start;
  background-color: #fff;
  color: #333;
  border-bottom-left-radius: 2px;
  box-shadow: 0 1px 2px rgba(0,0,0,0.1);
}

.message-content {
  overflow-wrap: break-word;
  word-wrap: break-word;
  word-break: break-word;
  font-size: 0.95rem;
}

.message-content p {
  margin: 0 0 0.75rem;
}

.message-content p:last-child {
  margin-bottom: 0;
}

.chat-input-container {
  display: flex;
  align-items: center;
  padding: 0.75rem;
  border-top: 1px solid #eee;
  background-color: white;
  border-radius: 0 0 8px 8px;
  gap: 0.5rem;
}

.chat-input-wrapper {
  flex: 1;
  display: flex;
  flex-direction: column;
  position: relative;
  border: 1px solid #ddd;
  border-radius: 24px;
  background-color: #fff;
  transition: all 0.2s;
  overflow: hidden;
  padding: 0.5rem 1rem 0;
}

.chat-input-wrapper:focus-within {
  border-color: #3f51b5;
  box-shadow: 0 0 0 2px rgba(63, 81, 181, 0.2);
}

.input-actions {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 4px 0;
  margin-left: -6px;
}

.chat-input {
  width: 100%;
  min-height: 44px;
  max-height: 120px;
  padding: 0.25rem 0;
  border: none;
  outline: none;
  resize: none;
  font-family: inherit;
  font-size: 0.95rem;
  line-height: 1.4;
  overflow-y: auto;
  background-color: transparent;
}

.chat-send-button {
  background-color: #3f51b5;
  color: white;
  border: none;
  border-radius: 50%;
  min-width: 44px;
  height: 44px;
  cursor: pointer;
  transition: all 0.2s;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
  padding: 0 14px;
}

.chat-send-button.search-mode {
  background-color: #1976d2;
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
  
  .chat-send-button {
    padding: 0.6rem;
    min-width: 50px;
  }
  
  .chat-header h2 {
    font-size: 1.2rem;
  }
}

/* 搜索模式样式 */
.chat-input-wrapper.search-mode {
  border-color: #3f51b5;
  background-color: #f8f9ff;
}

/* 相关论文容器 */
.related-papers-container {
  margin-top: 16px;
  border-top: 1px solid #e0e0e0;
  padding-top: 12px;
}

.related-papers-title {
  font-size: 16px;
  font-weight: 600;
  color: #333;
  margin-bottom: 12px;
}

.related-papers-list {
  display: flex;
  flex-wrap: wrap;
  gap: 12px;
  margin-bottom: 8px;
}

/* 论文卡片样式 */
.paper-card {
  border: 1px solid #e0e0e0;
  border-radius: 8px;
  padding: 12px;
  background-color: #f9f9f9;
  width: calc(50% - 6px);
  box-shadow: 0 2px 4px rgba(0, 0, 0, 0.05);
  transition: transform 0.2s, box-shadow 0.2s;
  position: relative;
  overflow: hidden;
}

.paper-card:hover {
  transform: translateY(-2px);
  box-shadow: 0 4px 8px rgba(0, 0, 0, 0.1);
}

.paper-card-header {
  margin-bottom: 8px;
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.paper-number {
  background-color: #3f51b5;
  color: white;
  width: 24px;
  height: 24px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 12px;
  font-weight: bold;
}

.paper-title {
  font-size: 15px;
  font-weight: 600;
  margin: 0 0 8px 0;
  color: #1a1a1a;
  line-height: 1.3;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

.paper-authors {
  font-size: 13px;
  color: #555;
  margin-bottom: 8px;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.paper-categories {
  display: flex;
  flex-wrap: wrap;
  gap: 4px;
  margin-bottom: 12px;
}

.paper-category {
  font-size: 11px;
  background-color: #e3f2fd;
  color: #1976d2;
  padding: 2px 6px;
  border-radius: 12px;
  white-space: nowrap;
}

.paper-link {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  background-color: #1976d2;
  color: white;
  padding: 6px 12px;
  border-radius: 4px;
  font-size: 13px;
  font-weight: 500;
  text-decoration: none;
  transition: background-color 0.2s;
}

.paper-link:hover {
  background-color: #1565c0;
}

.paper-link .icon-svg {
  width: 16px;
  height: 16px;
  fill: currentColor;
}

/* 响应式设计 */
@media (max-width: 768px) {
  .paper-card {
    width: 100%;
  }
}

/* 内联论文链接样式 */
.paper-link-inline {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  background-color: #e7f2fd;
  color: #1976d2;
  padding: 2px 8px;
  border-radius: 4px;
  font-size: 13px;
  font-weight: 500;
  text-decoration: none;
  transition: background-color 0.2s;
  white-space: nowrap;
  margin: 0 2px;
}

.paper-link-inline:hover {
  background-color: #bbdefb;
  text-decoration: none;
}

.paper-link-inline .icon-svg {
  width: 14px;
  height: 14px;
  fill: currentColor;
}

/* 论文标签容器样式 */
.paper-tags-container {
  margin-bottom: 12px;
  background-color: #f9f9ff;
  border-radius: 8px;
  padding: 8px 12px;
  border-left: 3px solid #5c6bc0;
}

/* 搜索加载状态 */
.paper-search-loading {
  display: flex;
  flex-direction: column;
  align-items: center;
  padding: 16px 0;
  gap: 12px;
}

.loader-circle {
  width: 36px;
  height: 36px;
  border: 3px solid #e0e0e0;
  border-top: 3px solid #3f51b5;
  border-radius: 50%;
  animation: spin-circle 1.2s cubic-bezier(0.5, 0, 0.5, 1) infinite;
}

.search-message {
  color: #555;
  font-size: 14px;
}

.no-papers-found {
  padding: 12px;
  text-align: center;
  color: #757575;
  font-style: italic;
  width: 100%;
}

@keyframes spin-circle {
  0% { transform: rotate(0deg); }
  100% { transform: rotate(360deg); }
}

/* 独立的论文标签容器 */
.paper-tags-container.standalone {
  margin: 0 0 12px 0;
  box-shadow: 0 2px 6px rgba(0,0,0,0.08);
  animation: fadeInDown 0.4s ease-out;
  transition: all 0.3s ease;
  max-height: 500px;
  overflow-y: auto;
}

@keyframes fadeInDown {
  from {
    opacity: 0;
    transform: translateY(-10px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}

.paper-tags-header {
  display: flex;
  align-items: center;
  gap: 6px;
  margin-bottom: 8px;
  color: #3949ab;
  font-weight: 500;
  font-size: 14px;
}

.paper-tags-header .icon-svg {
  width: 18px;
  height: 18px;
  fill: #3949ab;
}

.paper-tags-list {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.paper-tag {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  padding: 4px 10px;
  border-radius: 50px;
  background-color: #e8eaf6;
  color: #3f51b5;
  text-decoration: none;
  font-size: 13px;
  max-width: 100%;
  transition: all 0.2s ease;
  overflow: hidden;
  white-space: nowrap;
}

.paper-tag:hover {
  background-color: #c5cae9;
  box-shadow: 0 2px 5px rgba(0,0,0,0.1);
  transform: translateY(-1px);
}

.paper-tag .icon-svg {
  width: 16px;
  height: 16px;
  fill: currentColor;
  flex-shrink: 0;
}

.paper-tag-title {
  overflow: hidden;
  text-overflow: ellipsis;
}

/* 移动设备上的响应式样式 */
@media (max-width: 768px) {
  .paper-tag {
    max-width: 100%;
    margin-bottom: 5px;
  }
  
  .paper-tags-container {
    padding: 8px;
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

/* 添加文件上传和处理的动画效果 */
@keyframes pulse {
  0% { transform: scale(1); }
  50% { transform: scale(1.1); }
  100% { transform: scale(1); }
}

.uploading {
  animation: pulse 1.5s infinite ease-in-out;
}
</style> 