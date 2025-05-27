<template>
  <div class="chat-page">
    <div v-if="initialLoading" class="loading">Loading...</div>
    <div v-else :class="['full-layout', {'pdf-layout': showPdf}]">
      <!-- Chat Area -->
      <div class="chat-view">
        <div class="chat-section">
          <div class="chat-header">
            <div class="header-main">
              <h2>AI Chat</h2>
              <div class="header-actions">
                <button 
                  @click="handleFileListToggle" 
                  class="file-list-toggle"
                  :class="{ 'active': showFilesList }"
                  :title="showFilesList ? 'Hide files' : 'Show files'"
                >
                  <svg class="icon-svg" viewBox="0 0 24 24">
                    <path d="M14,2H6C4.9,2 4,2.9 4,4V20C4,21.1 4.9,22 6,22H18C19.1,22 20,21.1 20,20V8L14,2M18,20H6V4H13V9H18V20Z" />
                  </svg>
                  <span v-if="fileCount > 0" class="file-count">{{ fileCount }}</span>
                </button>
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
              <div class="chat-input-wrapper" 
                :class="{ 
                  'processing-mode': isLoading || isPaperProcessing
                }"
              >
                <textarea 
                  ref="inputField" 
                  v-model="userInput"
                  @keydown.enter.exact.prevent="sendMessage"
                  :placeholder="inputPlaceholder"
                  :disabled="false"
                  class="chat-input"
                ></textarea>
              </div>
              <button 
                @click="sendMessage" 
                :disabled="isLoading || !userInput.trim() || isPaperProcessing"
                class="chat-send-button"
              >
                <span v-if="isLoading">⏳</span>
                <span v-else-if="isPaperProcessing">⌛</span>
                <span v-else>Send</span>
              </button>
            </div>
          </div>
        </div>
      </div>
      
      <!-- File List Component -->
      <FileList
        ref="fileListRef"
        :chat-id="chatId"
        v-model:show-files-list="showFilesList"
        @file-selected="handleFileSelected"
        @pdf-closed="handlePdfClosed"
        @files-updated="handleFilesUpdated"
      />
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted, onBeforeUnmount, watch, computed, nextTick } from 'vue';
import { marked } from 'marked';
import DOMPurify from 'dompurify';
import hljs from 'highlight.js';
import 'highlight.js/styles/github.css';
import { chatSessionStore } from '../stores/chatSession';
import FileList from '../components/FileList.vue';
import api from '../services/api'


// Chat data
const user_id = ref("");
const messages = ref([]);
const userInput = ref('');
const isLoading = ref(false);  // Message loading status
const initialLoading = ref(true);  // Initial loading status
const isTyping = ref(false);
const currentTypingMessageId = ref(null); // Current typing message ID
const messagesContainer = ref(null);
const inputField = ref(null);

// PDF file management
const showFilesList = ref(false);
const showPdf = ref(false);

// check if paper is processing
const isPaperProcessing = ref(false);

// watch paper processing state
watch(() => chatSessionStore.state.processingPaper, (isProcessing) => {
  isPaperProcessing.value = isProcessing;
}, { immediate: true });

onBeforeUnmount(() => {
  chatSessionStore.resetProcessingState();  // ensure state is reset before component unmount
});

// handle file selected event
const handleFileSelected = () => {
  showPdf.value = true;
};

// handle pdf closed event
const handlePdfClosed = () => {
  showPdf.value = false
};

const handleFilesUpdated = () => {
  showFilesList.value = true;
  showPdf.value = true;
};

// input placeholder
const inputPlaceholder = computed(() => {
  return 'Type your message...';
});

// Initialization
onMounted(async () => {
  try {
    initialLoading.value = true;
    
    user_id.value = localStorage.getItem('X-User-ID');

    await loadChatSession();
    
    initialLoading.value = false;
  } catch (err) {
    console.error('Initialization error:', err);
    if (err.response) {
      console.error('API response:', err.response.status, err.response.data);
    } else if (err.request) {
      console.error('No response received:', err.request);
    } else {
      console.error('Error message:', err.message);
    }
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

// Load existing chat session
async function loadChatSession() {
  try {
    isLoading.value = true;
    const response = await api.get_messages();
    
    if (response) {
      messages.value = response;
    } else {
      messages.value = [];
    }
    
    await nextTick();
    scrollToBottom();
  } catch (error) {
    console.error('Failed to load session:');
  } finally {
    isLoading.value = false;
  }
}

// Send message or execute search
async function sendMessage() {
  // if input is empty or loading or processing, return
  if (!userInput.value.trim() || isLoading.value) return;
  
  // check if paper is processing
  if (isPaperProcessing.value) {
    return;
  }
  
  const messageContent = userInput.value.trim();
  userInput.value = '';
  
  // Add user message to UI
  const userMessage = {
    id: Date.now().toString(),
    role: 'user',
    content: messageContent,
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
    
    await streamChatResponse(messageContent, assistantMessage);
  } catch (err) {
    console.error('Failed to send message:', err);
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
    // Send request
    const response = await api.stream_chat(userMessage);
    
    if (!response.ok) {
      throw new Error(`HTTP error! status: ${response.status}`);
    }
    
    // Process streaming response
    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    let receivedChunks = 0;
    let accumulatedData = '';
    
    // Message container reference - for direct DOM manipulation
    const messageEl = document.querySelector(`[data-message-id="${assistantMessage.id}"]`);
    
    while (true) {
      const { done, value } = await reader.read();
      
      if (done) {
        isTyping.value = false;
        scrollToBottom();
        break;
      }
      
      // Decode data
      const chunk = decoder.decode(value, { stream: true });
      receivedChunks++;
      
      // Add new chunk to accumulated data
      accumulatedData += chunk;
      
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
        
        // If there's remaining plain text data, directly add to message
        if (accumulatedData) {
          assistantMessage.content += accumulatedData;
          updateMessageDisplay(messageEl, assistantMessage.content);
          accumulatedData = '';
        }
      } catch (e) {
        console.error('Error processing chunk:', e);
      }
    }
  } catch (error) {
    console.error('Failed to get streaming response:', error);
    assistantMessage.content = "Failed to get response. Please try again.";
    throw error;
  }
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

// Modify formatMessage function, simplify processing to avoid complex caching
function formatMessage(content) {
  if (!content) return '';
  const html = marked(content);
  return DOMPurify.sanitize(html);
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
watch(() => showPdf.value, (isPdfActive) => {
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

// add method in setup
const handleFileListToggle = () => {
  if (showPdf.value && fileListRef.value && typeof fileListRef.value.closePdf === 'function') {
    fileListRef.value.closePdf();
  } else {
    showFilesList.value = !showFilesList.value;
  }
};

const fileListRef = ref(null);
</script>

<style scoped>
.chat-page {
  width: 100%;
  height: calc(100vh - 60px);
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

.loading{
  text-align: center;
  padding: 2rem;
  background-color: white;
  border-radius: 8px;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
  margin-bottom: 2rem;
}


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
  from { transform: rotate(0deg); }
  to { transform: rotate(360deg); }
}

.chat-input:disabled {
  background-color: #f8f9fa;
  color: #6c757d;
  cursor: not-allowed;
}

button:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

.chat-input-wrapper.processing-mode {
  border-color: #ffb74d;
  background-color: #fff8e1;
}

.chat-input-wrapper.processing-mode .chat-input {
  background-color: transparent;
}

.chat-input-wrapper.processing-mode::after {
  content: "";
  position: absolute;
  bottom: 0;
  left: 0;
  height: 2px;
  background-color: #ff9800;
  animation: processing-bar 2s infinite linear;
  width: 100%;
  transform: scaleX(0);
  transform-origin: 0 0;
}

@keyframes processing-bar {
  0% {
    transform: scaleX(0);
  }
  50% {
    transform: scaleX(1);
  }
  100% {
    transform: scaleX(0);
    transform-origin: 100% 0;
  }
}
</style>

<style>
/* when pdf is active, adjust page layout */
body.pdf-active-page {
  --app-max-width: none !important;
  --container-padding: 0 !important;
}

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