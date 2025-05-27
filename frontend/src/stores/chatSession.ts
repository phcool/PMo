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

  // set paper processing state
  setProcessingPaper(isProcessing: boolean): void {
    this.state.processingPaper = isProcessing;
  }

  // get paper processing state
  isProcessingPaper(): boolean {
    return this.state.processingPaper;
  }

  // reset all processing states
  resetProcessingState(): void {
    this.state.processingPaper = false;
  }
}

// create singleton
export const chatSessionStore = new ChatSessionStore(); 