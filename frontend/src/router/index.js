import { createRouter, createWebHistory } from 'vue-router'
import HomeView from '../views/HomeView.vue'

// Define routes
const routes = [
  {
    path: '/',
    name: 'home',
    component: HomeView
  },
  {
    path: '/paper/:id',
    name: 'paper-detail',
    component: () => import('../views/PaperDetailView.vue'),
    props: true
  },
  {
    path: '/history',
    name: 'user-history',
    component: () => import('../views/UserHistoryView.vue')
  },
  {
    // Catch all route (404)
    path: '/:pathMatch(.*)*',
    name: 'not-found',
    component: () => import('../views/NotFoundView.vue')
  }
]

// Create router instance
const router = createRouter({
  history: createWebHistory(),
  routes,
  scrollBehavior() {
    // 禁用自动滚动，由组件自行控制
    return false;
  }
})

export default router 