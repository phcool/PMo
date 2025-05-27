import { reactive } from 'vue';

interface ChatSession {
  isLoading: boolean;
  processingPaper: boolean;
}

class ChatSessionStore {
  state = reactive<ChatSession>({
    isLoading: false,
    processingPaper: false,
  });

  // 设置论文处理状态
  setProcessingPaper(isProcessing: boolean): void {
    this.state.processingPaper = isProcessing;
  }

  // 获取论文处理状态
  isProcessingPaper(): boolean {
    return this.state.processingPaper;
  }

  // 重置所有处理状态
  resetProcessingState(): void {
    this.state.processingPaper = false;
  }
}

// 创建单例
export const chatSessionStore = new ChatSessionStore(); 