import { createRouter, createWebHistory, RouteRecordRaw } from 'vue-router'
import HomeView from '@/views/HomeView.vue'

// Define routes
const routes: Array<RouteRecordRaw> = [
  {
    path: '/',
    name: 'home',
    component: HomeView
  },
  {
    path: '/search',
    name: 'search',
    // Use lazy loading for non-essential pages to improve initial load time
    component: () => import(/* webpackChunkName: "search" */ '@/views/SearchView.vue')
  },
  {
    path: '/paper/:id',
    name: 'paper-detail',
    component: () => import(/* webpackChunkName: "paper-detail" */ '@/views/PaperDetailView.vue'),
    props: true
  },
  {
    // Catch all route (404)
    path: '/:pathMatch(.*)*',
    name: 'not-found',
    component: () => import(/* webpackChunkName: "not-found" */ '@/views/NotFoundView.vue')
  }
]

// Create router instance
const router = createRouter({
  history: createWebHistory(process.env.BASE_URL),
  routes
})

export default router 