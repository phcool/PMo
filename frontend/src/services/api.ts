import axios from 'axios';
import type { Paper, SearchRequest, SearchResponse, PaperAnalysis } from '@/types/paper';
import userService from './user';

// 创建axios实例
const api = axios.create({
  baseURL: '',  // 使用空字符串作为baseURL，避免路径问题
  timeout: 10000,
  headers: {
    'Content-Type': 'application/json',
  },
});

// 添加请求拦截器，在每个请求中添加用户ID
api.interceptors.request.use(config => {
  // 获取用户ID
  const userId = userService.getUserId();
  
  // 在请求头中添加用户ID
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
      timeout: 300000 // 5分钟超时，论文分析是一个耗时操作
    });
    return response.data;
  },

  /**
   * Trigger batch paper analysis
   */
  async analyzeBatchPapers(): Promise<any> {
    const response = await api.post('/api/papers/analyze-batch');
    return response.data;
  },
  
  /**
   * 获取用户偏好设置
   */
  async getUserPreferences(): Promise<any> {
    const response = await api.get('/api/user/preferences');
    return response.data;
  },
  
  /**
   * 保存用户偏好设置
   */
  async saveUserPreferences(preferences: any): Promise<any> {
    const response = await api.post('/api/user/preferences', preferences);
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
   * 记录用户论文浏览记录
   */
  async recordPaperView(paperId: string): Promise<any> {
    const response = await api.post(`/api/user/paper-view/${paperId}`);
    return response.data;
  },
  
  /**
   * 获取用户论文浏览记录
   */
  async getUserPaperViews(limit: number = 20, days: number = 30): Promise<any> {
    const response = await api.get('/api/user/paper-views', {
      params: { limit, days }
    });
    return response.data;
  }
}; 