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