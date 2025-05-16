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
            {{ showPdf ? 'Hide' : 'preview' }}
          </button>
          <a :href="paper.pdf_url" target="_blank" class="action-button">
            Open PDF
          </a>
          <button @click="startChatWithPaper" class="action-button">
            Chat
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
      
      <!-- PDF Viewer -->
      <div v-if="showPdf && paper.pdf_url" class="pdf-section">
        <button @click="closePdf" class="close-pdf-btn" title="Close PDF">
          <svg class="icon-svg" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
            <path d="M19 6.41L17.59 5 12 10.59 6.41 5 5 6.41 10.59 12 5 17.59 6.41 19 12 13.41 17.59 19 19 17.59 13.41 12 19 6.41z" fill="currentColor"/>
          </svg>
        </button>
        <embed 
          :src="paper.pdf_url" 
          class="pdf-iframe" 
          type="application/pdf" 
        />
      </div>
    </div>
  </div>
</template>

<script lang="ts">
import { defineComponent, ref, onMounted, computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import api from '../services/api'
import { getCategoryLabel } from '../types/paper'
import { chatSessionStore } from '../stores/chatSession'
import { useToast } from 'vue-toastification'

export default defineComponent({
  name: 'PaperDetailView',
  
  setup() {
    const route = useRoute();
    const router = useRouter();
    const toast = useToast();
    const paper = ref(null);
    const isLoading = ref(true);
    const error = ref('');
    const showPdf = ref(false);
    
    // Format the date
    const formattedDate = computed(() => {
      if (!paper.value || !paper.value.published_date) return '';
      
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
    
    // 切换PDF查看器
    const togglePdfViewer = () => {
      showPdf.value = !showPdf.value;
    };
    
    // 关闭PDF查看器
    const closePdf = () => {
      showPdf.value = false;
    };
    
    // 返回上一页
    const goBack = () => {
      if (document.referrer.includes(window.location.host)) {
        const referrer = new URL(document.referrer).pathname;
        sessionStorage.setItem(`scrollPos-${referrer}`, '0');
      }
      router.go(-1);
    };
    
    // 开始与论文聊天
    const startChatWithPaper = async () => {
      // 确保我们有论文信息
      if (!paper.value) {
        toast.error('论文信息不可用，请重试');
        return;
      }

      try {
        // 确保有活跃的聊天会话
        if (!chatSessionStore.hasActiveSession()) {
          await chatSessionStore.createChatSession();
        }
        
        const chatId = chatSessionStore.getChatId();
        
        // 存储论文 ID 到会话中，以便在聊天页面中使用
        chatSessionStore.setPendingPaperId(paper.value.paper_id);
        
        // 显示消息
        toast.info(`正在跳转到聊天页面，论文将在后台处理...`);
        
        // 直接跳转到聊天页面，不等待论文处理
        router.push({ name: 'chat', params: { id: chatId } });
        
        // 在后台发起论文关联请求，不阻塞用户流程
        setTimeout(async () => {
          try {
            await api.associatePaperWithChat(paper.value.paper_id, chatId);
            console.log(`Successfully associated paper ${paper.value.paper_id} with chat ${chatId} in background`);
          } catch (error) {
            console.error('Error associating paper with chat in background:', error);
          }
        }, 100);
        
      } catch (error) {
        console.error('Error starting chat with paper:', error);
        toast.error('无法创建聊天会话，请重试');
        
        // 出错时也尝试跳转到聊天页面
        if (chatSessionStore.hasActiveSession()) {
          router.push({ 
            name: 'chat',
            params: { id: chatSessionStore.getChatId() } 
          });
        } else {
          router.push({ name: 'chat' });
        }
      }
    };
    
    // 获取论文详情
    onMounted(async () => {
      const paperId = route.params.id;
      
      if (!paperId) {
        error.value = 'Paper ID is required';
        isLoading.value = false;
        return;
      }
      
      try {
        paper.value = await api.getPaperById(paperId);
        
        try {
          await api.recordPaperView(paperId);
        } catch (e) {
          console.error('Error recording paper view:', e);
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
      showPdf,
      formattedDate,
      togglePdfViewer,
      goBack,
      getCategoryLabel,
      closePdf,
      startChatWithPaper
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
}

.icon-svg {
  width: 20px;
  height: 20px;
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