<template>
  <div id="app">
    <header class="app-header">
      <nav>
        <router-link to="/">Home</router-link>
        <router-link to="/chat">Chat</router-link>
      </nav>
    </header>
    
    <main class="app-content">
      <router-view v-slot="{ Component }">
        <keep-alive :include="['HomeView']" :max="5">
          <component :is="Component" :key="$route.fullPath" />
        </keep-alive>
      </router-view>
    </main>
    
    <footer class="app-footer">
    </footer>
  </div>
</template>

<script lang="ts">
import { defineComponent, onMounted, onBeforeUnmount } from 'vue'
import { useRouter } from 'vue-router'
import { chatSessionStore } from './stores/chatSession'

export default defineComponent({
  name: 'App',
  
  setup() {
    const router = useRouter();
    
    // 保存页面滚动位置
    const saveScrollPosition = (path: string): void => {
      sessionStorage.setItem(
        `scrollPos-${path}`,
        window.scrollY.toString()
      );
    };
    
    // 初始化全局聊天会话
    const initGlobalChatSession = async (): Promise<void> => {
      try {
        // 只有当没有活动会话时才创建新会话
        if (!chatSessionStore.hasActiveSession()) {
          console.log('Initializing global chat session');
          await chatSessionStore.createChatSession();
        }
      } catch (error) {
        console.error('Failed to initialize global chat session:', error);
      }
    };
    
    // 在窗口关闭前结束聊天会话
    const endChatSessionBeforeUnload = async (): Promise<void> => {
      if (chatSessionStore.hasActiveSession()) {
        console.log('Ending global chat session before unload');
        await chatSessionStore.endChatSession();
      }
    };
    
    onMounted(async () => {
      // 添加导航钩子
      router.beforeEach((to, from) => {
        saveScrollPosition(from.fullPath);
      });
      
      // 初始化全局聊天会话
      await initGlobalChatSession();
      
      // 添加窗口关闭事件监听器
      window.addEventListener('beforeunload', endChatSessionBeforeUnload);
    });
    
    onBeforeUnmount(() => {
      // 在组件卸载前结束聊天会话
      endChatSessionBeforeUnload();
      
      // 移除窗口关闭事件监听器
      window.removeEventListener('beforeunload', endChatSessionBeforeUnload);
    });
  }
})
</script>

<style>
body {
  margin: 0;
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen,
    Ubuntu, Cantarell, 'Open Sans', 'Helvetica Neue', sans-serif;
  -webkit-font-smoothing: antialiased;
  -moz-osx-font-smoothing: grayscale;
  background-color: #f8f9fa;
  color: #333;
  line-height: 1.6;
}

#app {
  display: flex;
  flex-direction: column;
  min-height: 100vh;
}

.app-header {
  background-color: #3f51b5;
  color: white;
  padding: 1rem;
  box-shadow: 0 2px 4px rgba(0, 0, 0, 0.1);
}

.app-header h1 {
  margin: 0.5rem 0;
  font-size: 1.8rem;
  font-weight: 500;
}

.app-header nav {
  margin-bottom: 0.5rem;
}

.app-header nav a {
  color: white;
  text-decoration: none;
  margin-right: 1rem;
  opacity: 0.8;
  transition: opacity 0.2s;
}

.app-header nav a:hover {
  opacity: 1;
}

.app-header nav a.router-link-active {
  opacity: 1;
  font-weight: 600;
}

.app-content {
  flex: 1;
  padding: 0;
  max-width: none;
  width: 100%;
  margin: 0;
  display: flex;
  flex-direction: column;
}

.app-footer {
  background-color: #f1f3f5;
  padding: 1rem;
  text-align: center;
  font-size: 0.9rem;
  color: #666;
}
</style> 