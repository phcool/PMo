<template>
  <div class="user-history-view">
    <h1>Your Reading History</h1>
    
    <div class="tabs">
      <button 
        :class="['tab-button', { active: activeTab === 'views' }]" 
        @click="activeTab = 'views'"
      >
        View History
      </button>
      <button 
        :class="['tab-button', { active: activeTab === 'searches' }]" 
        @click="activeTab = 'searches'"
      >
        Search History
      </button>
    </div>
    
    <!-- View History -->
    <div v-if="activeTab === 'views'" class="history-content">
      <div v-if="isLoadingViews" class="loading">
        <p>Loading view history...</p>
      </div>
      
      <div v-else-if="paperViews.length === 0" class="empty-state">
        <p>You haven't viewed any papers yet</p>
        <router-link to="/" class="action-button">Browse Papers</router-link>
      </div>
      
      <div v-else class="paper-views-list">
        <div v-for="view in paperViews" :key="view.paper_id" class="paper-view-item">
          <div class="view-info">
            <div class="view-date">
              {{ formatDate(view.view_date) }} 
              <span class="view-count">({{ view.view_count }} times)</span>
            </div>
            <router-link :to="{ name: 'paper-detail', params: { id: view.paper_id } }" class="paper-title">
              {{ view.title || view.paper_id }}
            </router-link>
          </div>
        </div>
      </div>
    </div>
    
    <!-- Search History -->
    <div v-if="activeTab === 'searches'" class="history-content">
      <div v-if="isLoadingSearches" class="loading">
        <p>Loading search history...</p>
      </div>
      
      <div v-else-if="searchHistory.length === 0" class="empty-state">
        <p>You haven't made any searches yet</p>
        <router-link to="/" class="action-button">Go Search</router-link>
      </div>
      
      <div v-else class="search-history-list">
        <div v-for="(search, index) in searchHistory" :key="index" class="search-item">
          <div class="search-time">{{ formatDateTime(search.timestamp) }}</div>
          <div class="search-query">
            <a href="#" @click.prevent="executeSearch(search.query)" class="search-link">
              {{ search.query }}
            </a>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script lang="ts">
import { defineComponent, ref, onMounted } from 'vue';
import { useRouter } from 'vue-router';
import api from '../services/api';

export default defineComponent({
  name: 'UserHistoryView',
  
  setup() {
    const router = useRouter();
    const activeTab = ref('views');
    const paperViews = ref<Array<{paper_id: string, title: string, view_count: number, view_date: string}>>([]);
    const searchHistory = ref<Array<{query: string, timestamp: string}>>([]);
    const isLoadingViews = ref(true);
    const isLoadingSearches = ref(true);
    
    // Format date display
    const formatDate = (dateStr: string) => {
      const date = new Date(dateStr);
      return date.toLocaleDateString('en-US', {
        year: 'numeric',
        month: 'long',
        day: 'numeric'
      });
    };
    
    // Format date time display
    const formatDateTime = (dateStr: string) => {
      const date = new Date(dateStr);
      return date.toLocaleDateString('en-US', {
        year: 'numeric',
        month: 'long',
        day: 'numeric',
        hour: '2-digit',
        minute: '2-digit'
      });
    };
    
    // Execute search directly from history
    const executeSearch = async (query: string) => {
      try {
        // Save search history
        await api.saveSearchHistory(query);
        
        // Navigate to home page with query parameter
        // This will trigger the search via the route watcher we added to HomeView
        router.push({
          path: '/',
          query: { q: query }
        });
      } catch (error) {
        console.error('Error executing search:', error);
      }
    };
    
    // Load paper views
    const loadPaperViews = async () => {
      try {
        isLoadingViews.value = true;
        const response = await api.getUserPaperViews(50, 30); // Last 30 days, up to 50 records
        paperViews.value = response.views || [];
      } catch (error) {
        console.error('Failed to load paper view history:', error);
        paperViews.value = [];
      } finally {
        isLoadingViews.value = false;
      }
    };
    
    // Load search history
    const loadSearchHistory = async () => {
      try {
        isLoadingSearches.value = true;
        const response = await api.getUserSearchHistory();
        searchHistory.value = response.searches || [];
      } catch (error) {
        console.error('Failed to load search history:', error);
        searchHistory.value = [];
      } finally {
        isLoadingSearches.value = false;
      }
    };
    
    onMounted(() => {
      loadPaperViews();
      loadSearchHistory();
    });
    
    return {
      activeTab,
      paperViews,
      searchHistory,
      isLoadingViews,
      isLoadingSearches,
      formatDate,
      formatDateTime,
      executeSearch
    };
  }
});
</script>

<style scoped>
.user-history-view {
  max-width: 1000px;
  margin: 0 auto;
  padding: 20px;
}

h1 {
  font-size: 2rem;
  margin-bottom: 1.5rem;
  color: #333;
}

.tabs {
  display: flex;
  margin-bottom: 20px;
  border-bottom: 1px solid #eee;
}

.tab-button {
  padding: 10px 20px;
  background: none;
  border: none;
  cursor: pointer;
  font-size: 1rem;
  color: #666;
  border-bottom: 2px solid transparent;
  transition: all 0.3s;
}

.tab-button.active {
  color: #1976d2;
  border-bottom-color: #1976d2;
}

.tab-button:hover {
  color: #1976d2;
}

.history-content {
  margin-top: 20px;
}

.loading {
  text-align: center;
  padding: 20px;
  color: #666;
}

.empty-state {
  text-align: center;
  padding: 40px 20px;
  background-color: #f9f9f9;
  border-radius: 8px;
  color: #666;
}

.action-button {
  display: inline-block;
  margin-top: 10px;
  padding: 8px 16px;
  background-color: #1976d2;
  color: white;
  border-radius: 4px;
  text-decoration: none;
  transition: background-color 0.3s;
}

.action-button:hover {
  background-color: #1565c0;
}

.paper-views-list, .search-history-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.paper-view-item, .search-item {
  padding: 15px;
  background-color: white;
  border-radius: 8px;
  box-shadow: 0 2px 4px rgba(0, 0, 0, 0.1);
  transition: transform 0.2s;
}

.paper-view-item:hover, .search-item:hover {
  transform: translateY(-2px);
  box-shadow: 0 4px 8px rgba(0, 0, 0, 0.1);
}

.view-info, .search-info {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.view-date, .search-time {
  font-size: 0.9rem;
  color: #666;
}

.view-count {
  font-size: 0.8rem;
  color: #888;
  margin-left: 5px;
}

.paper-title {
  font-size: 1.1rem;
  color: #1976d2;
  text-decoration: none;
  font-weight: 500;
}

.paper-title:hover {
  text-decoration: underline;
}

.search-query {
  font-size: 1.1rem;
  margin-top: 5px;
}

.search-link {
  color: #1976d2;
  text-decoration: none;
  cursor: pointer;
}

.search-link:hover {
  text-decoration: underline;
}
</style> 