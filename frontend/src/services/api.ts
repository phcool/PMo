import axios from 'axios';
import type { Paper, SearchRequest, SearchResponse, PaperAnalysis } from '@/types/paper';

// Create axios instance
const api = axios.create({
  baseURL: '/api',  // 使用相对路径，避免硬编码域名
  timeout: 10000,
  headers: {
    'Content-Type': 'application/json',
  },
});

// API functions
export default {
  /**
   * Get recent papers with pagination
   */
  async getRecentPapers(limit: number = 10, offset: number = 0): Promise<Paper[]> {
    const response = await api.get('/papers', {
      params: { limit, offset }
    });
    return response.data;
  },

  /**
   * Get paper by ID
   */
  async getPaperById(paperId: string): Promise<Paper> {
    const response = await api.get(`/papers/${paperId}`);
    return response.data;
  },

  /**
   * Count total papers in database
   */
  async countPapers(): Promise<number> {
    const response = await api.get('/papers/count');
    return response.data.count;
  },

  /**
   * Fetch papers from arXiv
   */
  async fetchPapers(
    categories: string[] = ['cs.LG', 'cs.AI', 'cs.CV'],
    maxResults: number = 50
  ): Promise<{ count: number }> {
    const response = await api.post('/papers/fetch', null, {
      params: { categories, max_results: maxResults }
    });
    return response.data;
  },

  /**
   * Search papers using vector search
   */
  async searchPapers(searchRequest: SearchRequest): Promise<SearchResponse> {
    const response = await api.post('/search', searchRequest);
    return response.data;
  },

  /**
   * Get paper analysis by ID
   */
  async getPaperAnalysis(paperId: string): Promise<PaperAnalysis> {
    const response = await api.get(`/papers/${paperId}/analysis`);
    return response.data;
  },

  /**
   * Trigger paper analysis
   */
  async analyzePaper(paperId: string): Promise<any> {
    const response = await api.post(`/papers/${paperId}/analyze`, null, {
      timeout: 300000 // 5分钟超时，论文分析是一个耗时操作
    });
    return response.data;
  },

  /**
   * Trigger batch paper analysis
   */
  async analyzeBatchPapers(): Promise<any> {
    const response = await api.post('/papers/analyze-batch');
    return response.data;
  }
}; 