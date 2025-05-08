<template>
  <div class="paper-detail">
    <div v-if="isLoading" class="loading">
      Loading paper details...
    </div>
    
    <div v-else-if="error" class="error">
      <p>{{ error }}</p>
      <button @click="goBack" class="back-link">Back</button>
    </div>
    
    <div v-else-if="paper" :class="['paper-container', { 'split-layout': showPdf }]">
      <div class="paper-content">
        <!-- Chat Mode -->
        <div v-if="chatMode" class="chat-interface">
          <div class="chat-header">
            <h2>Chat about this paper</h2>
            <button @click="toggleChatMode" class="action-button">Back to Paper</button>
          </div>
          
          <div class="chat-messages" ref="chatMessagesEl">
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
              v-model="chatInput" 
              class="chat-input" 
              placeholder="Ask a question about this paper..." 
              @keydown.enter.prevent="sendChatMessage"
              :disabled="isChatLoading"
            ></textarea>
            <button 
              @click="sendChatMessage" 
              class="chat-send-button" 
              :disabled="isChatLoading || !chatInput.trim()"
            >
              Send
            </button>
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
            <button @click="toggleChatMode" class="action-button primary">
              Chat with AI
            </button>
            <button @click="goBack" class="action-button">
              Back
            </button>
          </div>
          
          <div class="paper-abstract">
            <h2>Abstract</h2>
            <p>{{ paper.abstract }}</p>
          </div>
          
          <!-- Analysis results -->
          <div v-if="paper.analysis" class="paper-analysis">
            <h2>AI Analysis Results</h2>
            
            <div class="analysis-section" v-if="paper.analysis.summary">
              <h3>Summary</h3>
              <p class="analysis-text">{{ paper.analysis.summary }}</p>
            </div>
            
            <div class="analysis-section" v-if="paper.analysis.key_findings">
              <h3>Key Findings</h3>
              <p class="analysis-text">{{ paper.analysis.key_findings }}</p>
            </div>
            
            <div class="analysis-section" v-if="paper.analysis.contributions">
              <h3>Contributions</h3>
              <p class="analysis-text">{{ paper.analysis.contributions }}</p>
            </div>
            
            <div class="analysis-section" v-if="paper.analysis.methodology">
              <h3>Methodology</h3>
              <p class="analysis-text">{{ paper.analysis.methodology }}</p>
            </div>
            
            <div class="analysis-section" v-if="paper.analysis.limitations">
              <h3>Limitations</h3>
              <p class="analysis-text">{{ paper.analysis.limitations }}</p>
            </div>
            
            <div class="analysis-section" v-if="paper.analysis.future_work">
              <h3>Future Work</h3>
              <p class="analysis-text">{{ paper.analysis.future_work }}</p>
            </div>
          </div>
          
          <!-- Analysis controls -->
          <div v-else class="paper-analysis-control">
            <div v-if="isAnalyzing" class="analyzing">
              <p>Analyzing paper... This may take several minutes. Please be patient.</p>
              <div class="progress-spinner"></div>
            </div>
            <div v-else>
              <p class="no-analysis-message">This paper has not been analyzed yet.</p>
              <button @click="analyzePaper" class="action-button primary analyze-button">
                Analyze this paper
              </button>
            </div>
            
            <!-- Analysis error message -->
            <div v-if="analysisError" class="analysis-error">
              <p>{{ analysisError }}</p>
              <button @click="analysisError = null" class="action-button">Dismiss</button>
            </div>
          </div>
        </div>
      </div>
      
      <!-- PDF Viewer -->
      <div v-if="showPdf && paper.pdf_url" class="pdf-section">
        <iframe 
          :src="paper.pdf_url + '#toolbar=1&navpanes=1&scrollbar=1&view=FitH'" 
          class="pdf-iframe" 
          frameborder="0"
          allowfullscreen
        ></iframe>
      </div>
    </div>
  </div>
</template>

<script>
import { defineComponent, ref, onMounted, computed, watch, nextTick } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import api from '../services/api'  // Remove .ts extension
import { getCategoryLabel } from '../types/paper'

export default defineComponent({
  name: 'PaperDetailView',
  
  setup() {
    const route = useRoute();
    const router = useRouter();
    const paper = ref(null);
    const isLoading = ref(true);
    const error = ref(null);
    const showPdf = ref(false);
    const isAnalyzing = ref(false);
    const analysisError = ref(null);
    
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
    
    // Toggle PDF viewer
    const togglePdfViewer = () => {
      showPdf.value = !showPdf.value;
    };
    
    // Toggle chat mode
    const toggleChatMode = () => {
      chatMode.value = !chatMode.value;
      if (chatMode.value && chatMessages.value.length === 0) {
        // Add a greeting message when starting chat
        chatMessages.value.push({
          role: 'assistant',
          content: `Hello! I'm an AI assistant that can help you understand this paper: "${paper.value.title}". What would you like to know about it?`
        });
      }
    };
    
    // Send a chat message to the backend
    const sendChatMessage = async () => {
      if (!chatInput.value.trim() || isChatLoading.value) return;
      
      // Add user message to chat
      const userMessage = chatInput.value.trim();
      chatMessages.value.push({ role: 'user', content: userMessage });
      chatInput.value = ''; // Clear input
      isChatLoading.value = true;
      
      // 添加一个空的助手消息，用于流式填充内容
      const assistantMessageIndex = chatMessages.value.length;
      chatMessages.value.push({
        role: 'assistant',
        content: ''
      });
      
      try {
        // Prepare conversation history for context (除最后一条用户消息)
        const contextMessages = chatMessages.value.slice(0, assistantMessageIndex - 1).map(msg => ({
          role: msg.role,
          content: msg.content
        }));
        
        // Call API with streaming
        await api.chatWithPaper(
          paper.value.paper_id, 
          {
            message: userMessage,
            context_messages: contextMessages
          },
          // 流式回调处理函数
          (content, isDone) => {
            // 将内容追加到当前助手消息
            if (content) {
              chatMessages.value[assistantMessageIndex].content += content;
              
              // 每次有新内容时，滚动到底部
              nextTick(() => {
                if (chatMessagesEl.value) {
                  const element = chatMessagesEl.value;
                  element.scrollTop = element.scrollHeight;
                }
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
      
      // 滚动到底部
      await nextTick();
      if (chatMessagesEl.value) {
        const element = chatMessagesEl.value;
        element.scrollTop = element.scrollHeight;
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
    
    // Analyze paper
    const analyzePaper = async () => {
      if (!paper.value || isAnalyzing.value) return;
      
      try {
        isAnalyzing.value = true;
        
        // Call analysis API
        await api.analyzePaper(paper.value.paper_id);
        
        // Get the latest paper data (including analysis results)
        paper.value = await api.getPaperById(paper.value.paper_id);
        
        // Record paper view
        try {
          await api.recordPaperView(paper.value.paper_id);
        } catch (e) {
          console.error('Error recording paper view:', e);
          // Does not affect main process, only logs the error
        }
      } catch (e) {
        console.error('Error analyzing paper:', e);
        analysisError.value = 'An error occurred while analyzing the paper. Please try again later.';
      } finally {
        isAnalyzing.value = false;
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
    });
    
    return {
      paper,
      isLoading,
      error,
      formattedDate,
      getCategoryLabel,
      showPdf,
      togglePdfViewer,
      goBack,
      analyzePaper,
      isAnalyzing,
      analysisError,
      chatMode,
      toggleChatMode,
      chatMessages,
      chatInput,
      isChatLoading,
      sendChatMessage,
      chatError,
      chatMessagesEl
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
}

.pdf-iframe {
  width: 100%;
  height: 100%;
  border: 1px solid #ddd;
  border-radius: 4px;
}

.paper-abstract h2 {
  margin-top: 0;
  font-size: 1.3rem;
  color: #333;
  margin-bottom: 0.8rem;
}

.paper-abstract p {
  line-height: 1.6;
  white-space: normal;
  word-wrap: break-word;
  font-size: 0.95rem;
  overflow-wrap: break-word;
}

/* Responsive layout */
@media (max-width: 900px) {
  .split-layout {
    flex-direction: column;
    max-height: none;
    overflow: visible;
  }
  
  .split-layout .paper-content,
  .split-layout .pdf-section {
    flex: 1 1 auto;
    width: 100%;
    max-height: none;
  }
  
  .split-layout .paper-content {
    overflow-y: visible;
  }
}

.split-layout .paper-abstract p {
  margin-top: 0;
}

.paper-analysis {
  margin-top: 2rem;
}

.paper-analysis h2 {
  margin-top: 0;
  font-size: 1.4rem;
  color: #333;
  margin-bottom: 1rem;
}

.analysis-section {
  margin-bottom: 1.5rem;
}

.analysis-section h3 {
  font-size: 1.1rem;
  color: #555;
  margin-bottom: 0.5rem;
}

.analysis-section p {
  line-height: 1.6;
  color: #333;
  white-space: pre-line;
}

.paper-analysis-control {
  margin-top: 2rem;
  padding: 1.5rem;
  background-color: #f8f9fa;
  border-radius: 8px;
  text-align: center;
}

.analyzing {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 1rem;
  color: #3f51b5;
}

.no-analysis-message {
  color: #666;
  font-style: italic;
  margin: 1rem 0;
}

.analyze-button {
  margin-top: 1rem;
  background-color: #4caf50;
  font-weight: 500;
  display: inline-block;
  transition: all 0.3s;
}

.analyze-button:hover {
  background-color: #388e3c;
  transform: translateY(-2px);
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.2);
}

.progress-spinner {
  border: 4px solid rgba(0, 0, 0, 0.1);
  border-top: 4px solid #3f51b5;
  border-radius: 50%;
  width: 20px;
  height: 20px;
  animation: spin 1s linear infinite;
  margin: 0 auto;
}

@keyframes spin {
  0% { transform: rotate(0deg); }
  100% { transform: rotate(360deg); }
}

.analysis-error {
  margin-top: 1rem;
  padding: 1rem;
  background-color: #f8f9fa;
  border-radius: 8px;
  text-align: center;
}

/* Responsive layout */
@media (max-width: 768px) {
  .paper-container {
    padding: 1.5rem;
  }
}

/* Chat Interface Styles */
.chat-interface {
  display: flex;
  flex-direction: column;
  height: 100%;
  max-height: 90vh;
}

.chat-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding-bottom: 1rem;
  border-bottom: 1px solid #eee;
  margin-bottom: 1rem;
}

.chat-header h2 {
  margin: 0;
  font-size: 1.3rem;
}

.chat-messages {
  flex: 1;
  overflow-y: auto;
  padding: 1rem 0;
  display: flex;
  flex-direction: column;
  gap: 1rem;
  margin-bottom: 1rem;
}

.chat-message {
  padding: 1rem;
  border-radius: 8px;
  max-width: 85%;
  word-wrap: break-word;
  position: relative;
}

.user-message {
  align-self: flex-end;
  background-color: #e3f2fd;
  color: #333;
}

.assistant-message {
  align-self: flex-start;
  background-color: #f5f5f5;
  color: #333;
}

.assistant-message:last-child.assistant-message {
  position: relative;
}

/* 为正在生成的最后一条消息添加闪烁光标效果 */
.assistant-message:last-child.assistant-message .message-content {
  display: inline-block;
}

.assistant-message:last-child.assistant-message .message-content::after {
  content: "";
  width: 2px;
  height: 14px;
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

.paper-analysis {
  margin-top: 2rem;
}

.paper-analysis h2 {
  margin-top: 0;
  font-size: 1.3rem;
  color: #333;
  margin-bottom: 1.5rem;
}

.analysis-section {
  margin-bottom: 1.5rem;
}

.analysis-section h3 {
  margin-top: 0;
  margin-bottom: 0.5rem;
  font-size: 1.1rem;
  color: #333;
}

.analysis-text {
  white-space: pre-line;
  line-height: 1.6;
  margin-top: 0.5rem;
}

.paper-analysis-control {
  margin-top: 2rem;
  padding: 1.5rem;
  background-color: #f8f9fa;
  border-radius: 8px;
  text-align: center;
}

.analyzing {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 1rem;
}

.progress-spinner {
  border: 4px solid rgba(0, 0, 0, 0.1);
  border-left-color: #3f51b5;
  border-radius: 50%;
  width: 30px;
  height: 30px;
  animation: spin 1s linear infinite;
}

.analysis-error {
  margin-top: 1rem;
  color: #d32f2f;
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
}
</style> 