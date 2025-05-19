import axios, { AxiosInstance, AxiosRequestConfig, AxiosResponse } from 'axios';
import type { Paper } from '@/types/paper';

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
 * Processing status interface
 */
interface ProcessingStatus {
  processing: boolean;
  file_name: string;
}

/**
 * API Service interface
 */
export interface IApiService {
  getRecentPapers(limit?: number, offset?: number): Promise<Paper[]>;
  getPaperById(paperId: string): Promise<Paper>;
  countPapers(): Promise<number>;
  fetchPapers(categories?: string[], maxResults?: number): Promise<{ count: number }>;
  createChatSession(paperId?: string): Promise<ChatSessionResponse>;
  sendChatMessage(chatId: string, message: string, onChunk?: (chunk: string, isDone: boolean) => void): Promise<any>;
  endChatSession(chatId: string): Promise<any>;
  getProcessingStatus(chatId: string): Promise<ProcessingStatus>;
  associatePaperWithChat(paperId: string, chatId: string): Promise<{success: boolean, message: string}>;
  searchPapers(payload: { query: string, limit?: number }): Promise<any>;
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
      timeout: 30000,  // Default timeout increased to 30 seconds
      headers: {
        'Content-Type': 'application/json',
      },
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
   * Create a new chat session
   * @returns Promise with chat session data
   */
  async createChatSession(): Promise<ChatSessionResponse> {
    try {
      const response = await this.api.post('/api/chat/sessions', null, {
      });
      return response.data;
    } catch (error) {
      console.error('Failed to create chat session:', error);
      throw error;
    }
  }
  
  /**
   * @param chatId Chat session ID
   * @param file File to upload
   * @returns Promise with upload result
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

  /**
   * Associate a paper with a chat session
   * @param paperId Paper ID to associate
   * @param chatId Chat session ID to associate with
   * @returns Promise with result
   */
  async associatePaperWithChat(paperId: string, chatId: string): Promise<{success: boolean, message: string}> {
    try {
      const response = await this.api.post(`/api/chat/sessions/${chatId}/attach_paper`, 
        { paper_id: paperId },
        { 
          timeout: 120000  // Extended timeout (2 minutes) for PDF processing and embeddings
        }
      );
      return response.data;
    } catch (error) {
      console.error('Failed to associate paper with chat:', error);
      throw error;
    }
  }

  /**
   * Search papers by query
   * @param payload { query, limit }
   * @returns Promise with search results
   */
  async searchPapers(payload: { query: string, limit?: number }): Promise<any> {
    try {
      const response = await this.api.post('/api/search/', {
        query: payload.query,
        limit: payload.limit ?? 30
      });
      return response.data;
    } catch (error) {
      console.error('Failed to search papers:', error);
      throw error;
    }
  }
}

// Export singleton instance
export default new ApiService(); 