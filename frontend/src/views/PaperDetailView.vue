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
        
        <!-- 分析结果 -->
        <div v-if="paper.analysis" class="paper-analysis">
          <h2>Analysis</h2>
          
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
        
        <!-- 分析控制 -->
        <div v-else class="paper-analysis-control">
          <div v-if="isAnalyzing" class="analyzing">
            <p>Analyzing paper... This may take several minutes. Please be patient.</p>
            <div class="progress-spinner"></div>
          </div>
          <button v-else @click="analyzePaper" class="action-button primary">
            Analyze Paper
          </button>
          
          <!-- 分析错误提示 -->
          <div v-if="analysisError" class="analysis-error">
            <p>{{ analysisError }}</p>
            <button @click="analysisError = null" class="action-button">Dismiss</button>
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
import { defineComponent, ref, onMounted, computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import api from '../services/api'  // 移除.ts后缀
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
    
    // Go back to previous page
    const goBack = () => {
      // 保存上一页的滚动位置到 sessionStorage
      if (document.referrer.includes(window.location.host)) {
        // 获取来源页面的路径
        const referrer = new URL(document.referrer).pathname;
        // 将之前保存的滚动位置恢复到 sessionStorage
        sessionStorage.setItem(`scrollPos-${referrer}`, '0');
      }
      router.go(-1);
    };
    
    // 分析论文
    const analyzePaper = async () => {
      if (!paper.value || isAnalyzing.value) return;
      
      try {
        isAnalyzing.value = true;
        
        // 调用分析API
        await api.analyzePaper(paper.value.paper_id);
        
        // 获取最新的论文数据（包含分析结果）
        paper.value = await api.getPaperById(paper.value.paper_id);
        
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
        paper.value = await api.getPaperById(paperId);
      } catch (e) {
        error.value = 'Failed to load paper details. The paper may not exist.';
        console.error('Error loading paper:', e);
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
      analysisError
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

/* 分栏布局 */
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

/* 响应式布局 */
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
  padding: 1rem;
  background-color: #f8f9fa;
  border-radius: 8px;
  text-align: center;
}

.analyzing {
  color: #3f51b5;
  font-style: italic;
}

/* 分析文本样式 */
.analysis-text {
  white-space: pre-line; /* 保留换行符 */
  line-height: 1.6;
  margin-top: 0.5rem;
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
</style> 