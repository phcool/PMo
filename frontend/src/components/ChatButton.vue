<template>
  <button @click="attachPaper" class="action-button chat-button">
    Chat
  </button>
</template>

<script lang="ts">
import { defineComponent } from 'vue'
import { useRouter } from 'vue-router'
import { chatSessionStore } from '../stores/chatSession'
import api from '../services/api'


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
    
    // Start chat with paper
    const attachPaper = async () => {
      try {
        chatSessionStore.setProcessingPaper(true);

        const user_id = localStorage.getItem('X-User-ID');
        if (!user_id) {
          throw new Error('User ID not found');
        }        

        try {
          const attachResponse = await api.attach_paper(props.paperId);
          
          if (!attachResponse) {
            throw new Error('Failed to attach paper to chat session');
          }

          router.push({ name: 'chat'});
          
          // 在后台处理向量化
          setTimeout(async () => {
            try {
              // 开始处理向量化
              const embeddingResponse = await api.process_embeddings(props.paperId);
              
              if (!embeddingResponse) {
                console.error('Failed to process embeddings');
                chatSessionStore.resetProcessingState(); 
                return;
              }

              chatSessionStore.resetProcessingState(); 

            } catch (error) {
              chatSessionStore.resetProcessingState(); 
            }
          }, 100);
          
        } catch (error) {
          console.error('Error preparing chat', error);
          throw error;
        }
        
      } catch (error) {
        console.error('Error starting chat with paper:', error);
      }
    };
    
    return {
      attachPaper
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