<template>
  <div class="home">
    <div class="hero-section">
      <!-- Search Box -->
      <SearchBox
        v-model="searchQuery"
        :is-loading="false"
        @search="handleSearch"
      />
    </div>
    
    <!-- Papers Sections Container -->
    <div class="papers-container">
      <!-- Recent Papers List -->
      <div class="recent-papers">
        <h2>Recent Papers</h2>
        
        <div v-if="isLoading" class="loading">
          Loading papers...
        </div>
        
        <div v-else-if="papers.length === 0" class="no-papers">
          <p>No papers found</p>
        </div>
        
        <div v-else class="papers-list">
          <PaperCard v-for="paper in papers" :key="paper.paper_id" :paper="paper" />
        </div>
        
        <!-- Load More button for Recent Papers -->
        <div v-if="papers.length > 0" class="section-load-more">
          <button 
            v-if="hasMorePapers" 
            @click="loadMoreRecent" 
            :disabled="isLoadingMoreRecent"
            class="secondary-button"
          >
            {{ isLoadingMoreRecent ? 'Loading...' : 'Load More Recent' }}
          </button>
        </div>
      </div>
    </div>
  </div>
</template>

<script>
import { defineComponent, ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import PaperCard from '../components/PaperCard.vue'
import SearchBox from '../components/SearchBox.vue'
import api from '../services/api'

export default defineComponent({
  name: 'HomeView',
  
  components: {
    PaperCard,
    SearchBox
  },
  
  setup() {
    const router = useRouter();
    
    // --- Define refs first ---
    const papers = ref([]);
    const paperCount = ref(null);
    const isLoading = ref(false);
    const isLoadingMoreRecent = ref(false);
    const offset = ref(0);
    const limit = ref(10);
    const hasMorePapers = ref(true);
    const searchQuery = ref('');

    // Handle search
    const handleSearch = (query) => {
      router.push({ 
        name: 'search',
        query: { q: query }
      });
    };

    // --- Define other async loading methods ---
    // Load recent papers
    const loadPapers = async () => {
      try {
        isLoading.value = true;
        papers.value = await api.getRecentPapers(limit.value, 0);
        offset.value = papers.value.length;
        paperCount.value = await api.countPapers();
        hasMorePapers.value = papers.value.length < (paperCount.value || 0);
      } catch (error) { console.error('Error loading papers:', error); }
      finally { isLoading.value = false; }
    };

    // Load more recent papers
    const loadMoreRecent = async () => {
      try {
        isLoadingMoreRecent.value = true;
        const morePapers = await api.getRecentPapers(limit.value, offset.value);
        papers.value = [...papers.value, ...morePapers];
        offset.value += morePapers.length;
        hasMorePapers.value = morePapers.length === limit.value;
      } catch (error) { console.error('Error loading more recent papers:', error); }
      finally { isLoadingMoreRecent.value = false; }
    };

    onMounted(() => {
      loadPapers();
    });
    
    // --- Return all refs and methods ---
    return {
      papers, paperCount, isLoading, 
      isLoadingMoreRecent, loadMoreRecent,
      offset, limit, hasMorePapers,
      searchQuery, handleSearch
    };
  }
})
</script>

<style scoped>
.home {
  max-width: 1000px;
  margin: 0 auto;
}

.hero-section {
  text-align: center;
  padding: 2rem 0;
  margin-bottom: 2rem;
}

.search-container {
  background-color: white;
  border-radius: 8px;
  padding: 1rem;
  margin-bottom: 1.5rem;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
  max-width: 600px;
  margin-left: auto;
  margin-right: auto;
}

.search-form {
  display: flex;
}

.search-input {
  flex: 1;
  padding: 0.75rem 1rem;
  font-size: 1rem;
  border: 1px solid #ddd;
  border-radius: 4px 0 0 4px;
  outline: none;
}

.search-input:focus {
  border-color: #3f51b5;
}

.search-button {
  padding: 0.75rem 1.5rem;
  background-color: #3f51b5;
  color: white;
  border: none;
  border-radius: 0 4px 4px 0;
  cursor: pointer;
  font-size: 1rem;
  transition: background-color 0.2s;
}

.search-button:hover {
  background-color: #303f9f;
}

.search-button:disabled {
  background-color: #c5cae9;
  cursor: not-allowed;
}


.primary-button, .secondary-button {
  padding: 0.75rem 1.5rem;
  border-radius: 4px;
  font-size: 1rem;
  cursor: pointer;
  transition: all 0.2s;
  text-decoration: none;
  display: inline-block;
}

.primary-button {
  background-color: #3f51b5;
  color: white;
  border: none;
}

.primary-button:hover {
  background-color: #303f9f;
}

.primary-button:disabled {
  background-color: #c5cae9;
  cursor: not-allowed;
}

.secondary-button {
  background-color: transparent;
  color: #3f51b5;
  border: 1px solid #3f51b5;
}

.secondary-button:hover {
  background-color: rgba(63, 81, 181, 0.1);
}

.secondary-button:disabled {
  color: #9fa8da;
  border-color: #9fa8da;
  cursor: not-allowed;
}

.papers-container {
  margin-bottom: 3rem;
}

.recent-papers {
  margin-bottom: 2rem;
  padding: 0 0.5rem;
  box-sizing: border-box;
  max-width: 100%;
}

.recent-papers h2 {
  margin-bottom: 1.5rem;
  color: #333;
  border-bottom: 1px solid #eee;
  padding-bottom: 0.75rem;
  font-size: 1.5rem;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.papers-list {
  display: grid;
  grid-template-columns: 1fr;
  gap: 1rem;
  overflow: hidden;
}

.loading, .no-papers {
  text-align: center;
  padding: 2rem;
  color: #666;
  background-color: white;
  border-radius: 8px;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
}

.section-load-more {
  display: flex;
  justify-content: center;
  margin-top: 1.5rem;
}
</style> 