import { createRouter, createWebHistory, RouteRecordRaw } from 'vue-router'
import HomeView from '../views/HomeView.vue'

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
    path: '/search',
    name: 'search',
    component: () => import('../views/SearchView.vue'),
    meta: {
      title: 'Search Papers - DL Paper Monitor',
      requiresAuth: false
    }
  },
  {
    path: '/paper',
    name: 'paper-detail',
    component: () => import('../views/PaperDetailView.vue'),
    meta: {
      title: 'Paper Details - DL Paper Monitor',
      requiresAuth: false
    }
  },
  {
    path: '/chat',
    name: 'chat',
    component: () => import('../views/ChatView.vue'),
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
  history: createWebHistory('/'),
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
  
  // Continue navigation
  next();
});

export default router 