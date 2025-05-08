import axios from 'axios';
import type { Paper, SearchRequest, SearchResponse, PaperAnalysis } from '@/types/paper';
import userService from './user';

// Create axios instance
const api = axios.create({
  baseURL: '',  // Use empty string as baseURL to avoid path issues
  timeout: 10000,
  headers: {
    'Content-Type': 'application/json',
  },
});

// Add request interceptor to include user ID in every request
api.interceptors.request.use(config => {
  // Get user ID
  const userId = userService.getUserId();
  
  // Add user ID to request header
  if (userId) {
    config.headers['X-User-ID'] = userId;
  }
  
  return config;
}, error => {
  return Promise.reject(error);
});

// API functions
export default {
  /**
   * Get recent papers with pagination
   */
  async getRecentPapers(limit: number = 10, offset: number = 0): Promise<Paper[]> {
    const response = await api.get('/api/papers', {
      params: { limit, offset }
    });
    return response.data;
  },

  /**
   * Get paper by ID
   */
  async getPaperById(paperId: string): Promise<Paper> {
    const response = await api.get(`/api/papers/${paperId}`);
    return response.data;
  },

  /**
   * Count total papers in database
   */
  async countPapers(): Promise<number> {
    const response = await api.get('/api/papers/count');
    return response.data.count;
  },

  /**
   * Fetch papers from arXiv
   */
  async fetchPapers(
    categories: string[] = ['cs.LG', 'cs.AI', 'cs.CV'],
    maxResults: number = 50
  ): Promise<{ count: number }> {
    const response = await api.post('/api/papers/fetch', null, {
      params: { categories, max_results: maxResults }
    });
    return response.data;
  },

  /**
   * Search papers using vector search
   */
  async searchPapers(searchRequest: SearchRequest): Promise<SearchResponse> {
    const response = await api.post('/api/search', searchRequest);
    return response.data;
  },

  /**
   * Get paper analysis by ID
   */
  async getPaperAnalysis(paperId: string): Promise<PaperAnalysis> {
    const response = await api.get(`/api/papers/${paperId}/analysis`);
    return response.data;
  },

  /**
   * Trigger paper analysis
   */
  async analyzePaper(paperId: string): Promise<any> {
    const response = await api.post(`/api/papers/${paperId}/analyze`, null, {
      timeout: 300000 // 5 minute timeout, paper analysis is a time-consuming operation
    });
    return response.data;
  },

  /**
   * Chat with AI about a paper
   */
  async chatWithPaper(
    paperId: string, 
    data: { message: string, context_messages?: Array<{role: string, content: string}> },
    onChunk?: (chunk: string, isDone: boolean) => void
  ): Promise<any> {
    // 如果提供了 onChunk 回调，使用流式处理
    if (onChunk) {
      try {
        const response = await fetch(`/api/papers/${paperId}/chat`, {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            'X-User-ID': userService.getUserId() || ''
          },
          body: JSON.stringify(data)
        });

        if (!response.ok) {
          throw new Error(`HTTP error! status: ${response.status}`);
        }

        const reader = response.body?.getReader();
        if (!reader) {
          throw new Error('Stream reader not available');
        }

        const decoder = new TextDecoder();
        let buffer = '';

        // 读取流数据
        while (true) {
          const { value, done } = await reader.read();
          
          if (done) {
            // 处理最后一个块
            if (buffer) {
              try {
                const chunk = JSON.parse(buffer);
                onChunk(chunk.content, chunk.done);
              } catch (e) {
                console.error('Error parsing final chunk:', buffer);
              }
            }
            break;
          }

          // 将数据添加到缓冲区并按行处理
          buffer += decoder.decode(value, { stream: true });
          
          // 按行处理数据
          const lines = buffer.split('\n');
          buffer = lines.pop() || ''; // 保留未完成的最后一行
          
          for (const line of lines) {
            if (line.trim()) {
              try {
                const chunk = JSON.parse(line);
                onChunk(chunk.content, chunk.done);
                if (chunk.done) {
                  return { success: true };
                }
              } catch (e) {
                console.error('Error parsing chunk:', line);
              }
            }
          }
        }
        
        return { success: true };
      } catch (error) {
        console.error('Error with streaming chat:', error);
        throw error;
      }
    } else {
      // 原方法作为后备，不使用流式处理
      const response = await api.post(`/api/papers/${paperId}/chat`, data, {
        timeout: 60000 // 1 minute timeout for chat responses
      });
      return response.data;
    }
  },

  /**
   * Trigger batch paper analysis
   */
  async analyzeBatchPapers(): Promise<any> {
    const response = await api.post('/api/papers/analyze-batch');
    return response.data;
  },
  
  /**
   * Get user access records
   */
  async getUserPreferences(): Promise<any> {
    const response = await api.get('/api/user/user');
    return response.data;
  },
  
  /**
   * Save user access records
   */
  async saveUserPreferences(preferences: any): Promise<any> {
    const response = await api.post('/api/user/user', preferences);
    return response.data;
  },

  /**
   * Save user search history
   */
  async saveSearchHistory(query: string): Promise<any> {
    const response = await api.post('/api/user/search-history', { query });
    return response.data;
  },
  
  /**
   * Get user search history
   */
  async getUserSearchHistory(): Promise<any> {
    const response = await api.get('/api/user/search-history');
    return response.data;
  },
  
  /**
   * Get recommended papers based on user search history
   */
  async getRecommendedPapers(limit: number = 5, offset: number = 0): Promise<Paper[]> {
    const response = await api.get('/api/papers/recommend/', {
      params: { limit, offset }
    });
    return response.data;
  },
  
  /**
   * Record user paper viewing history
   */
  async recordPaperView(paperId: string): Promise<any> {
    const response = await api.post(`/api/user/paper-view/${paperId}`);
    return response.data;
  },
  
  /**
   * Get user paper viewing history
   */
  async getUserPaperViews(limit: number = 20, days: number = 30): Promise<any> {
    const response = await api.get('/api/user/paper-views', {
      params: { limit, days }
    });
    return response.data;
  }
}; 