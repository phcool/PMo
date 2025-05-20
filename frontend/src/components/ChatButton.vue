<template>
  <button @click="startChatWithPaper" class="action-button chat-button">
    Chat
  </button>
</template>

<script lang="ts">
import { defineComponent } from 'vue'
import { useRouter } from 'vue-router'
import { chatSessionStore } from '../stores/chatSession'
import { useToast } from 'vue-toastification'
import axios from 'axios'

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || ''

export default defineComponent({
  name: 'ChatButton',
  
  props: {
    paperId: {
      type: String,
      required: true
    }
  },
  
  setup(props) {
    const router = useRouter();
    const toast = useToast();
    
    // Start chat with paper
    const startChatWithPaper = async () => {
      try {
        // 显示加载提示
        toast.info('Preparing chat session, please wait...');
        
        // 确保有活跃的聊天会话
        if (!chatSessionStore.hasActiveSession()) {
          await chatSessionStore.createChatSession();
        }
        
        const chatId = chatSessionStore.getChatId();
        if (!chatId) {
          throw new Error('Failed to create chat session');
        }
        
        // 存储论文ID到会话中
        chatSessionStore.setPendingPaperId(props.paperId);
        
        // 同步获取PDF并更新文件列表
        try {
          // 先同步获取PDF
          const attachResponse = await axios.post(
            `${API_BASE_URL}/api/chat/sessions/${chatId}/attach_paper`,
            { paper_id: props.paperId }
          );
          
          if (!attachResponse.data.success) {
            throw new Error(attachResponse.data.message || 'Failed to attach paper to chat session');
          }
          
          // 等待一小段时间确保文件列表已更新
          await new Promise(resolve => setTimeout(resolve, 500));
          
          // 检查文件是否已添加到会话
          const filesResponse = await axios.get<Array<{id: string, name: string}>>(
            `${API_BASE_URL}/api/chat/sessions/${chatId}/files`
          );
          
          if (filesResponse.data.length === 0) {
            throw new Error('Paper PDF was not added to the chat session');
          }
          
          // 文件已成功添加，现在可以跳转到聊天页面
          toast.success('Paper loaded successfully, redirecting to chat...');
          router.push({ name: 'chat', params: { id: chatId } });
          
          // 在后台处理向量化
          setTimeout(async () => {
            try {
              // 开始处理向量化
              const processResponse = await axios.post(
                `${API_BASE_URL}/api/chat/sessions/${chatId}/process_embeddings`,
                { paper_id: props.paperId }
              );
              
              if (!processResponse.data.success) {
                console.error('Failed to process embeddings:', processResponse.data.message);
                chatSessionStore.resetProcessingState();  // 重置所有状态
                toast.error('Failed to process paper embeddings. You can still chat with the paper.');
                return;
              }

              console.log('Paper embeddings processing completed in background');
              chatSessionStore.resetProcessingState();  // 使用新的重置方法
              toast.success('Paper processing completed successfully');

            } catch (error) {
              console.error('Error in background embeddings processing:', error);
              chatSessionStore.resetProcessingState();  // 确保错误时也重置状态
              toast.error('Error processing paper embeddings. You can still chat with the paper.');
            }
          }, 100);
          
        } catch (error) {
          console.error('Error preparing chat session:', error);
          toast.error('Failed to prepare chat session. Please try again.');
          throw error;
        }
        
      } catch (error) {
        console.error('Error starting chat with paper:', error);
        toast.error('Failed to start chat session. Please try again.');
        
        // 如果出错但会话已创建，仍然尝试跳转到聊天页面
        if (chatSessionStore.hasActiveSession()) {
          router.push({ 
            name: 'chat',
            params: { id: chatSessionStore.getChatId() } 
          });
        } else {
          router.push({ name: 'chat' });
        }
      }
    };
    
    return {
      startChatWithPaper
    };
  }
})
</script>

<style scoped>
.action-button {
  padding: 0.5rem 1rem;
  background-color: #f0f0f0;
  color: #333;
  border-radius: 4px;
  text-decoration: none;
  font-size: 0.9rem;
  transition: background-color 0.2s;
  border: none;
  cursor: pointer;
}

.action-button:hover {
  background-color: #e0e0e0;
}

.chat-button {
  background-color: #3f51b5;
  color: white;
}

.chat-button:hover {
  background-color: #303f9f;
}
</style> 