import axios, { AxiosInstance, AxiosRequestConfig, AxiosResponse } from 'axios';
import type { Paper, SearchRequest, SearchResponse } from '@/types/paper';
import userService from './user';

/**
 * Chat response chunk interface
 */
interface ChatResponseChunk {
  content: string;
  done: boolean;
}

/**
 * Chat session response interface
 */
interface ChatSessionResponse {
  chat_id: string;
}

/**
 * File upload response interface
 */
interface FileUploadResponse {
  success: boolean;
  file_id: string;
  file_name: string;
}

/**
 * Processing status interface
 */
interface ProcessingStatus {
  processing: boolean;
  file_name: string;
}

/**
 * User preferences interface
 */
interface UserPreferences {
  [key: string]: any;
}

/**
 * API Service interface
 */
export interface IApiService {
  getRecentPapers(limit?: number, offset?: number): Promise<Paper[]>;
  getPaperById(paperId: string): Promise<Paper>;
  countPapers(): Promise<number>;
  fetchPapers(categories?: string[], maxResults?: number): Promise<{ count: number }>;
  searchPapers(searchRequest: SearchRequest): Promise<SearchResponse>;
  chatWithPaper(paperId: string, data: { message: string, context_messages?: Array<{role: string, content: string}> }, onChunk?: (chunk: string, isDone: boolean) => void): Promise<any>;
  createChatSession(paperId?: string): Promise<ChatSessionResponse>;
  uploadPdfToChat(chatId: string, file: File): Promise<FileUploadResponse>;
  sendChatMessage(chatId: string, message: string, onChunk?: (chunk: string, isDone: boolean) => void): Promise<any>;
  endChatSession(chatId: string): Promise<any>;
  getUserPreferences(): Promise<UserPreferences>;
  saveUserPreferences(preferences: UserPreferences): Promise<any>;
  saveSearchHistory(query: string): Promise<any>;
  getUserSearchHistory(): Promise<Array<{query: string, timestamp: string}>>;
  getRecommendedPapers(limit?: number, offset?: number): Promise<Paper[]>;
  recordPaperView(paperId: string): Promise<any>;
  getUserPaperViews(limit?: number, days?: number): Promise<Array<{paper: Paper, view_count: number}>>;
  getProcessingStatus(chatId: string): Promise<ProcessingStatus>;
  loadPaperFromOss(chatId: string, paperId: string): Promise<FileUploadResponse>;
  getSessionFiles(chatId: string): Promise<Array<{id: string, name: string, size: number, upload_time: string}>>;
}

/**
 * API Service implementation
 */
class ApiService implements IApiService {
  private api: AxiosInstance;
  
  constructor() {
    // Create axios instance
    this.api = axios.create({
      baseURL: '',  // Use empty string as baseURL to avoid path issues
      timeout: 10000,
      headers: {
        'Content-Type': 'application/json',
      },
    });
    
    // Add request interceptor to include user ID in every request
    this.api.interceptors.request.use(config => {
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
  }

  /**
   * Get recent papers with pagination
   * @param limit Number of papers to retrieve
   * @param offset Pagination offset
   * @returns Promise with array of papers
   */
  async getRecentPapers(limit: number = 10, offset: number = 0): Promise<Paper[]> {
    try {
      const response = await this.api.get('/api/papers', {
        params: { limit, offset }
      });
      return response.data;
    } catch (error) {
      console.error('Failed to get recent papers:', error);
      throw error;
    }
  }

  /**
   * Get paper by ID
   * @param paperId The ID of the paper to retrieve
   * @returns Promise with paper data
   */
  async getPaperById(paperId: string): Promise<Paper> {
    try {
      const response = await this.api.get(`/api/papers/${paperId}`);
      return response.data;
    } catch (error) {
      console.error(`Failed to get paper ${paperId}:`, error);
      throw error;
    }
  }

  /**
   * Count total papers in database
   * @returns Promise with paper count
   */
  async countPapers(): Promise<number> {
    try {
      const response = await this.api.get('/api/papers/count');
      return response.data.count;
    } catch (error) {
      console.error('Failed to count papers:', error);
      throw error;
    }
  }

  /**
   * Fetch papers from arXiv
   * @param categories Array of arXiv categories to fetch
   * @param maxResults Maximum number of results to fetch
   * @returns Promise with count of fetched papers
   */
  async fetchPapers(
    categories: string[] = ['cs.LG', 'cs.AI', 'cs.CV'],
    maxResults: number = 50
  ): Promise<{ count: number }> {
    try {
      const response = await this.api.post('/api/papers/fetch', null, {
        params: { categories, max_results: maxResults }
      });
      return response.data;
    } catch (error) {
      console.error('Failed to fetch papers:', error);
      throw error;
    }
  }

  /**
   * Search papers using vector search
   * @param searchRequest Search parameters
   * @returns Promise with search results
   */
  async searchPapers(searchRequest: SearchRequest): Promise<SearchResponse> {
    try {
      const response = await this.api.post('/api/search', searchRequest);
      return response.data;
    } catch (error) {
      console.error('Failed to search papers:', error);
      throw error;
    }
  }

  /**
   * Chat with AI about a paper
   * @param paperId The ID of the paper to chat about
   * @param data Message data
   * @param onChunk Optional callback for streaming responses
   * @returns Promise with chat response
   */
  async chatWithPaper(
    paperId: string, 
    data: { message: string, context_messages?: Array<{role: string, content: string}> },
    onChunk?: (chunk: string, isDone: boolean) => void
  ): Promise<any> {
    try {
      // Create a new chat session linked to the paper
      const createSessionResponse = await this.api.post('/api/chat/sessions', null, {
        params: { paper_id: paperId }
      });
      
      const chatId = createSessionResponse.data.chat_id;
      
      // Use the streaming API to send a message and get a response
      return this.sendChatMessage(chatId, data.message, onChunk);
    } catch (error) {
      console.error('Failed to chat with paper:', error);
      throw error;
    }
  }
  
  /**
   * Create a new chat session, optionally linked to a paper
   * @param paperId Optional paper ID to link to the session
   * @returns Promise with chat session data
   */
  async createChatSession(paperId?: string): Promise<ChatSessionResponse> {
    try {
      const response = await this.api.post('/api/chat/sessions', null, {
        params: paperId ? { paper_id: paperId } : undefined
      });
      return response.data;
    } catch (error) {
      console.error('Failed to create chat session:', error);
      throw error;
    }
  }
  
  /**
   * Upload a PDF file to a chat session
   * @param chatId Chat session ID
   * @param file File to upload
   * @returns Promise with upload result
   */
  async uploadPdfToChat(chatId: string, file: File): Promise<FileUploadResponse> {
    try {
      const formData = new FormData();
      formData.append('file', file);
      
      const response = await this.api.post(
        `/api/chat/sessions/${chatId}/upload`, 
        formData,
        {
          headers: {
            'Content-Type': 'multipart/form-data'
          },
          timeout: 60000 // Longer timeout for file uploads
        }
      );
      
      return response.data;
    } catch (error) {
      console.error('Failed to upload PDF:', error);
      throw error;
    }
  }
  
  /**
   * Send a message to a chat session and get a streaming response
   * @param chatId Chat session ID
   * @param message Message to send
   * @param onChunk Optional callback for streaming responses
   * @returns Promise with chat response
   */
  async sendChatMessage(
    chatId: string,
    message: string,
    onChunk?: (chunk: string, isDone: boolean) => void
  ): Promise<any> {
    // If callback provided, use streaming
    if (onChunk) {
      try {
        const response = await fetch(`/api/chat/sessions/${chatId}/chat`, {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            'X-User-ID': userService.getUserId() || ''
          },
          body: JSON.stringify({ message })
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

        // Process stream data
        while (true) {
          const { value, done } = await reader.read();
          
          if (done) {
            // Process final chunk
            if (buffer) {
              try {
                const chunk = JSON.parse(buffer) as ChatResponseChunk;
                onChunk(chunk.content, chunk.done);
              } catch (e) {
                console.error('Error parsing final chunk:', buffer);
              }
            }
            break;
          }

          // Add data to buffer and process by line
          buffer += decoder.decode(value, { stream: true });
          
          // Process data by line
          const lines = buffer.split('\n');
          buffer = lines.pop() || ''; // Keep incomplete last line
          
          for (const line of lines) {
            if (line.trim()) {
              try {
                const chunk = JSON.parse(line) as ChatResponseChunk;
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
        console.error('Error in streaming chat:', error);
        throw error;
      }
    } else {
      // Non-streaming fallback
      try {
        const response = await this.api.post(`/api/chat/sessions/${chatId}/chat`, { message });
        return response.data;
      } catch (error) {
        console.error('Failed to send chat message:', error);
        throw error;
      }
    }
  }
  
  /**
   * End a chat session
   * @param chatId Chat session ID
   * @returns Promise with result
   */
  async endChatSession(chatId: string): Promise<any> {
    try {
      const response = await this.api.delete(`/api/chat/sessions/${chatId}`);
      return response.data;
    } catch (error) {
      console.error('Failed to end chat session:', error);
      throw error;
    }
  }
  
  /**
   * Get user preferences
   * @returns Promise with user preferences
   */
  async getUserPreferences(): Promise<UserPreferences> {
    try {
      const response = await this.api.get('/api/user/preferences');
      return response.data;
    } catch (error) {
      console.error('Failed to get user preferences:', error);
      throw error;
    }
  }
  
  /**
   * Save user preferences
   * @param preferences User preferences to save
   * @returns Promise with result
   */
  async saveUserPreferences(preferences: UserPreferences): Promise<any> {
    try {
      const response = await this.api.post('/api/user/preferences', preferences);
      return response.data;
    } catch (error) {
      console.error('Failed to save user preferences:', error);
      throw error;
    }
  }
  
  /**
   * Save search history
   * @param query Search query to save
   * @returns Promise with result
   */
  async saveSearchHistory(query: string): Promise<any> {
    try {
      const response = await this.api.post('/api/user/search-history', { query });
      return response.data;
    } catch (error) {
      console.error('Failed to save search history:', error);
      throw error;
    }
  }
  
  /**
   * Get user search history
   * @returns Promise with search history
   */
  async getUserSearchHistory(): Promise<Array<{query: string, timestamp: string}>> {
    try {
      const response = await this.api.get('/api/user/search-history');
      return response.data;
    } catch (error) {
      console.error('Failed to get search history:', error);
      throw error;
    }
  }
  
  /**
   * Get recommended papers
   * @param limit Number of recommendations to retrieve
   * @param offset Pagination offset
   * @returns Promise with recommended papers
   */
  async getRecommendedPapers(limit: number = 5, offset: number = 0): Promise<Paper[]> {
    try {
      const response = await this.api.get('/api/papers/recommend/', {
        params: { limit, offset }
      });
      return response.data;
    } catch (error) {
      console.error('Failed to get recommended papers:', error);
      throw error;
    }
  }
  
  /**
   * Record paper view
   * @param paperId Paper ID that was viewed
   * @returns Promise with result
   */
  async recordPaperView(paperId: string): Promise<any> {
    try {
      const response = await this.api.post('/api/user/paper-views', { paper_id: paperId });
      return response.data;
    } catch (error) {
      console.error('Failed to record paper view:', error);
      throw error;
    }
  }
  
  /**
   * Get user paper views
   * @param limit Maximum number of views to retrieve
   * @param days Time window in days
   * @returns Promise with paper view history
   */
  async getUserPaperViews(limit: number = 20, days: number = 30): Promise<Array<{paper: Paper, view_count: number}>> {
    try {
      const response = await this.api.get('/api/user/paper-views', {
        params: { limit, days }
      });
      return response.data;
    } catch (error) {
      console.error('Failed to get paper views:', error);
      throw error;
    }
  }
  
  /**
   * Get processing status for a chat session
   * @param chatId Chat session ID
   * @returns Promise with processing status
   */
  async getProcessingStatus(chatId: string): Promise<ProcessingStatus> {
    try {
      const response = await this.api.get(`/api/chat/sessions/${chatId}/processing-status`);
      return response.data;
    } catch (error) {
      console.error('Failed to get processing status:', error);
      throw error;
    }
  }
  
  /**
   * Load a paper PDF from OSS to a chat session
   * @param chatId Chat session ID
   * @param paperId Paper ID to load from OSS
   * @returns Promise with file information
   */
  async loadPaperFromOss(chatId: string, paperId: string): Promise<FileUploadResponse> {
    try {
      const response = await this.api.post(
        `/api/chat/sessions/${chatId}/load-paper?paper_id=${paperId}`,
        null,
        {
          timeout: 60000 // Longer timeout for file processing
        }
      );
      
      return response.data;
    } catch (error) {
      console.error('Failed to load paper from OSS:', error);
      throw error;
    }
  }

  /**
   * Get session files
   * @param chatId Chat session ID
   * @returns Promise with session files
   */
  async getSessionFiles(chatId: string): Promise<Array<{id: string, name: string, size: number, upload_time: string}>> {
    try {
      const response = await this.api.get(`/api/chat/sessions/${chatId}/files`);
      return response.data;
    } catch (error) {
      console.error('Failed to get session files:', error);
      throw error;
    }
  }
}

// Export singleton instance
export default new ApiService(); 