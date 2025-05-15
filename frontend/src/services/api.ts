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
  // Optional: paper_id and created_at can be added if needed from your backend response model
  // paper_id?: string;
  // created_at?: string; 
}

/**
 * File upload response interface
 */
interface FileUploadResponse {
  // Adjust based on your actual backend response for upload
  id: string; // Assuming 'id' is the file_id
  name: string;
  size: number;
  upload_time: string;
  message?: string; 
}

/**
 * Processing status interface
 */
interface ProcessingStatus {
  processing: boolean;
  file_name: string;
  files_count?: number; // Added based on backend logic
  error?: string; // To capture potential errors during processing
}

/**
 * User preferences interface
 */
interface UserPreferences {
  [key: string]: any;
}

/**
 * Response from loading paper from OSS
 */
interface LoadPaperResponse {
  message: string;
  file_id: string;
  filename: string;
  size: number;
  load_time: string; // ISO date string
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
  // chatWithPaper method might be deprecated or refactored if using generic chat session flow
  // chatWithPaper(paperId: string, data: { message: string, context_messages?: Array<{role: string, content: string}> }, onChunk?: (chunk: string, isDone: boolean) => void): Promise<any>;
  createChatSession(paperId?: string): Promise<ChatSessionResponse>;
  uploadPdfToChat(chatId: string, file: File): Promise<FileUploadResponse>;
  loadPaperFromOSS(chatId: string, paperId: string): Promise<LoadPaperResponse>; // New method
  sendChatMessage(chatId: string, message: string, onChunk?: (chunk: string, isDone: boolean) => void): Promise<void>; // Return type changed to void as it handles chunks via callback
  endChatSession(chatId: string): Promise<any>; // Consider a more specific response type if applicable
  getUserPreferences(): Promise<UserPreferences>;
  saveUserPreferences(preferences: UserPreferences): Promise<any>;
  saveSearchHistory(query: string): Promise<any>;
  getUserSearchHistory(): Promise<Array<{query: string, timestamp: string}>>;
  getRecommendedPapers(limit?: number, offset?: number): Promise<Paper[]>;
  recordPaperView(paperId: string): Promise<any>;
  getUserPaperViews(limit?: number, days?: number): Promise<Array<{paper: Paper, view_count: number}>>;
  getProcessingStatus(chatId: string): Promise<ProcessingStatus>;
  // Consider adding methods for getting session files, viewing files, deleting files if these are managed via API
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
          timeout: 120000 // Longer timeout for file uploads (e.g., 2 minutes)
        }
      );
      
      return response.data; // Ensure this matches FileUploadResponse structure
    } catch (error) {
      console.error('Failed to upload PDF to chat:', error);
      throw error;
    }
  }
  
  /**
   * Load a paper from OSS into a chat session
   * @param chatId Chat session ID
   * @param paperId Paper ID to load from OSS
   * @returns Promise with load result
   */
  async loadPaperFromOSS(chatId: string, paperId: string): Promise<LoadPaperResponse> {
    try {
      const response = await this.api.post<LoadPaperResponse>(
        `/api/chat/sessions/${chatId}/load-paper-from-oss`,
        { paper_id: paperId } // Request body
      );
      return response.data;
    } catch (error) {
      console.error(`Failed to load paper ${paperId} from OSS for chat ${chatId}:`, error);
      // Consider more specific error handling or re-throwing a custom error object
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
  ): Promise<void> { // Changed return type to void
    if (!onChunk) {
      // This case should ideally not happen if streaming is always expected.
      // If non-streaming send is needed, create a separate method or handle it differently.
      console.warn('sendChatMessage called without onChunk callback. This is a streaming API.');
      // Fallback or error if non-streaming is not supported by this method directly.
      // For now, let it proceed but it won't stream to the caller without onChunk.
    }

    try {
      const response = await this.api.post(
        `/api/chat/sessions/${chatId}/chat`,
        { message }, 
        {
          responseType: 'stream',
          timeout: 300000, // 5 minutes timeout for potentially long LLM responses
        }
      );

      // Process the stream
      const reader = response.data.getReader();
      const decoder = new TextDecoder();
      let buffer = '';

      while (true) {
        const { done, value } = await reader.read();
        if (done) {
          if (buffer.trim()) { // Process any remaining part of a chunk
            try {
              const chunkData = JSON.parse(buffer.trim()) as ChatResponseChunk;
              if (onChunk) onChunk(chunkData.content, chunkData.done);
            } catch (e) {
              console.error('Error parsing final JSON chunk:', e, 'Buffer:', buffer.trim());
              if (onChunk) onChunk('', true); // Signal done even on error to prevent hangs
            }
          }
          if (onChunk) onChunk('', true); // Ensure done is always called
          break;
        }

        buffer += decoder.decode(value, { stream: true });
        
        // Process line by line (since chunks are newline-separated JSON)
        let newlineIndex;
        while ((newlineIndex = buffer.indexOf('\n')) !== -1) {
          const line = buffer.substring(0, newlineIndex).trim();
          buffer = buffer.substring(newlineIndex + 1);
          if (line) {
            try {
              const chunkData = JSON.parse(line) as ChatResponseChunk;
              if (onChunk) onChunk(chunkData.content, chunkData.done);
              if (chunkData.done) {
                // If a chunk signals done, we might want to stop processing further.
                // However, the stream should naturally end when the server closes it.
              }
            } catch (e) {
              console.error('Error parsing JSON chunk:', e, 'Line:', line);
              // Optionally, handle malformed chunk, e.g., by notifying about an error
            }
          }
        }
      }
    } catch (error) {
      console.error('Failed to send chat message:', error);
      if (onChunk) {
        // Try to send an error message through the onChunk callback
        // This depends on how the frontend handles error content
        const errorMessage = error instanceof Error ? error.message : 'Failed to send message.';
        onChunk(`Error: ${errorMessage}`, true); 
      }
      throw error; // Re-throw to allow further error handling by the caller if needed
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
      const response = await this.api.get(`/api/chat/sessions/${chatId}/status`);
      return response.data;
    } catch (error) {
      console.error('Failed to get processing status:', error);
      throw error;
    }
  }
}

// Export singleton instance
export default new ApiService(); 