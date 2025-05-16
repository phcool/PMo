import { reactive, ref } from 'vue';
import axios from 'axios';

// 获取API基础URL，确保在所有环境中都能正确工作
const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || '';
console.log('API Base URL:', API_BASE_URL); // 添加调试信息

// 构建API端点，确保路径正确
function buildApiEndpoint(path: string): string {
  // 如果API_BASE_URL为空，则直接使用/api前缀
  if (!API_BASE_URL) {
    return `/api${path}`;
  }
  // 否则使用配置的API_BASE_URL
  return `${API_BASE_URL}${path}`;
}

interface ChatSession {
  chatId: string | null;
  isLoading: boolean;
  error: string | null;
}

class ChatSessionStore {
  state = reactive<ChatSession>({
    chatId: null,
    isLoading: false,
    error: null
  });

  // 创建新聊天会话
  async createChatSession(paperId?: string): Promise<string | null> {
    try {
      this.state.isLoading = true;
      this.state.error = null;

      // 构建API请求参数
      const endpoint = buildApiEndpoint('/chat/sessions');
      console.log('Creating chat session at:', endpoint); // 添加调试信息
      
      const params = paperId ? { paper_id: paperId } : {};

      const response = await axios.post(endpoint, null, { params });
      const chatId = response.data.chat_id;
      
      // 保存聊天会话ID
      this.state.chatId = chatId;
      console.log('Chat session created:', chatId);
      
      return chatId;
    } catch (error: any) {
      console.error('Failed to create chat session:', error);
      // 详细记录错误信息，帮助调试
      if (error.response) {
        console.error('Error response:', error.response.status, error.response.data);
      } else if (error.request) {
        console.error('No response received:', error.request);
      } else {
        console.error('Error message:', error.message);
      }
      
      this.state.error = error.response?.data?.detail || error.message || 'Failed to create chat session';
      return null;
    } finally {
      this.state.isLoading = false;
    }
  }

  // 结束聊天会话
  async endChatSession(): Promise<boolean> {
    if (!this.state.chatId) {
      console.warn('No active chat session to end');
      return false;
    }

    try {
      this.state.isLoading = true;
      
      const endpoint = buildApiEndpoint(`/chat/sessions/${this.state.chatId}`);
      console.log('Ending chat session at:', endpoint); // 添加调试信息
      
      const response = await axios.delete(endpoint);
      console.log('Chat session ended:', this.state.chatId);
      
      // 清除状态
      this.state.chatId = null;
      return true;
    } catch (error: any) {
      console.error('Failed to end chat session:', error);
      // 详细记录错误信息，帮助调试
      if (error.response) {
        console.error('Error response:', error.response.status, error.response.data);
      } else if (error.request) {
        console.error('No response received:', error.request);
      } else {
        console.error('Error message:', error.message);
      }
      
      this.state.error = error.response?.data?.detail || error.message || 'Failed to end chat session';
      return false;
    } finally {
      this.state.isLoading = false;
    }
  }

  // 获取当前聊天会话ID
  getChatId(): string | null {
    return this.state.chatId;
  }

  // 检查是否有活动的聊天会话
  hasActiveSession(): boolean {
    return !!this.state.chatId;
  }

  // 设置聊天会话ID（用于从URL加载）
  setChatId(chatId: string): void {
    this.state.chatId = chatId;
    console.log('Chat session ID set:', chatId); // 添加调试信息
  }
}

// 创建单例
export const chatSessionStore = new ChatSessionStore(); 