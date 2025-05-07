<template>
  <div id="app">
    <header class="app-header">
      <nav>
        <router-link to="/">Home</router-link>
        <router-link to="/history">History</router-link>
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

<script>
import { defineComponent, onMounted, onUnmounted } from 'vue'
import { useRouter } from 'vue-router'
import userService from './services/user'
import api from './services/api'

export default defineComponent({
  name: 'App',
  
  setup() {
    const router = useRouter();
    
    // Save scroll position before navigation
    const saveScrollPositionBeforeLeave = (to, from) => {
      // Save current page scroll position
      sessionStorage.setItem(
        `scrollPos-${from.fullPath}`,
        window.scrollY.toString()
      );
    };

    // Update user visit records
    const updateUserVisit = async () => {
      try {
        // Ensure user ID is initialized
        const userId = userService.getUserId();
        // Call API to save user visit records (empty object, as server will use info from request headers)
        await api.saveUserPreferences({});
      } catch (error) {
        console.error('Failed to update user visit records:', error);
      }
    };
    
    onMounted(() => {
      // Add global navigation hook
      router.beforeEach(saveScrollPositionBeforeLeave);
      
      // Update user visit records
      updateUserVisit();

      // Add route listener to update user visit records on each route change
      router.afterEach(() => {
        updateUserVisit();
      });
    });
    
    onUnmounted(() => {
      // Cleanup
      router.beforeEach(() => {});
    });
    
    return {};
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
  padding: 2rem;
  max-width: 1200px;
  width: 100%;
  margin: 0 auto;
}

.app-footer {
  background-color: #f1f3f5;
  padding: 1rem;
  text-align: center;
  font-size: 0.9rem;
  color: #666;
}
</style> 