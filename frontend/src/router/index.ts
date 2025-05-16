import { createRouter, createWebHistory, RouteRecordRaw } from 'vue-router'
import HomeView from '../views/HomeView.vue'
import UserHistoryView from '../views/UserHistoryView.vue'

// 获取基础路径，默认为根路径'/'
// 如果应用部署在子路径上，可以通过环境变量配置
const BASE_PATH = import.meta.env.VITE_BASE_PATH || '/'

// Define routes with proper types
const routes: Array<RouteRecordRaw> = [
  {
    path: '/',
    name: 'home',
    component: HomeView,
    meta: {
      title: 'Home - DL Paper Monitor',
      requiresAuth: false
    }
  },
  {
    path: '/paper/:id',
    name: 'paper-detail',
    component: () => import('../views/PaperDetailView.vue'),
    props: true,
    meta: {
      title: 'Paper Details - DL Paper Monitor',
      requiresAuth: false
    }
  },
  {
    path: '/history',
    name: 'user-history',
    component: UserHistoryView,
    meta: {
      title: 'History - DL Paper Monitor',
      requiresAuth: false
    }
  },
  {
    path: '/chat/:id?',
    name: 'chat',
    component: () => import('../views/ChatView.vue'),
    props: true,
    meta: {
      title: 'Chat - DL Paper Monitor',
      requiresAuth: false
    }
  },
  {
    // Catch all route (404)
    path: '/:pathMatch(.*)*',
    name: 'not-found',
    component: () => import('../views/NotFoundView.vue'),
    meta: {
      title: '404 Not Found - DL Paper Monitor',
      requiresAuth: false
    }
  }
]

// Create router instance
const router = createRouter({
  // 使用BASE_PATH确保在不同环境下路由都能正确工作
  history: createWebHistory(BASE_PATH),
  routes,
  scrollBehavior(to, from, savedPosition) {
    // If there's a saved position, use it
    if (savedPosition) {
      return savedPosition;
    }
    
    // Check if there's a saved scroll position in sessionStorage for this route
    const savedScrollPos = sessionStorage.getItem(`scrollPos-${to.fullPath}`);
    if (savedScrollPos) {
      return { top: parseInt(savedScrollPos, 10) };
    }
    
    // Default: scroll to top
    return { top: 0 };
  }
})

// Global navigation guards
router.beforeEach((to, from, next) => {
  // Update page title
  document.title = to.meta.title as string || 'DL Paper Monitor';
  
  // 添加调试信息，帮助排查路由问题
  console.log(`Navigating from ${from.fullPath} to ${to.fullPath}`);
  
  // Continue navigation
  next();
});

export default router 