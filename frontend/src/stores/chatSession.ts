import { reactive, ref } from 'vue';
import axios from 'axios';

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || '';

interface ChatSession {
  chatId: string | null;
  isLoading: boolean;
  error: string | null;
  pendingPaperId: string | null;
  processingPaper: boolean;
}

class ChatSessionStore {
  state = reactive<ChatSession>({
    chatId: null,
    isLoading: false,
    error: null,
    pendingPaperId: null,
    processingPaper: false
  });

  // 创建新聊天会话
  async createChatSession(paperId?: string): Promise<string | null> {
    try {
      this.state.isLoading = true;
      this.state.error = null;

      // 构建API请求参数
      const endpoint = `${API_BASE_URL}/api/chat/sessions`;
      const params = paperId ? { paper_id: paperId } : {};

      const response = await axios.post(endpoint, null, { params });
      const chatId = response.data.chat_id;
      
      // 保存聊天会话ID
      this.state.chatId = chatId;
      console.log('Chat session created:', chatId);
      
      return chatId;
    } catch (error: any) {
      console.error('Failed to create chat session:', error);
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
      
      const response = await axios.delete(`${API_BASE_URL}/api/chat/sessions/${this.state.chatId}`);
      console.log('Chat session ended:', this.state.chatId);
      
      // 清除状态
      this.state.chatId = null;
      return true;
    } catch (error: any) {
      console.error('Failed to end chat session:', error);
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
  }

  // 设置待处理论文ID
  setPendingPaperId(paperId: string): void {
    this.state.pendingPaperId = paperId;
    this.state.processingPaper = true;
  }

  // 获取待处理论文ID
  getPendingPaperId(): string | null {
    return this.state.pendingPaperId;
  }

  // 清除待处理论文ID
  clearPendingPaperId(): void {
    this.state.pendingPaperId = null;
    this.state.processingPaper = false;  // 同时清除处理状态
  }

  // 设置论文处理状态
  setProcessingPaper(isProcessing: boolean): void {
    this.state.processingPaper = isProcessing;
    if (!isProcessing) {
      // 如果处理完成，同时清除待处理ID
      this.state.pendingPaperId = null;
    }
  }

  // 获取论文处理状态
  isProcessingPaper(): boolean {
    return this.state.processingPaper;
  }

  // 重置所有处理状态
  resetProcessingState(): void {
    this.state.pendingPaperId = null;
    this.state.processingPaper = false;
  }
}

// 创建单例
export const chatSessionStore = new ChatSessionStore(); 