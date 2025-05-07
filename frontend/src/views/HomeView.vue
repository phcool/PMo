<template>
  <div class="home">
    <div class="hero-section">
      <!-- Search Box -->
      <div class="search-container">
        <div class="search-form">
          <input 
            v-model="searchQuery" 
            class="search-input" 
            placeholder="Search papers..." 
            @keyup.enter="performSearch(false)" 
            aria-label="Search papers"
          />
          <button @click="performSearch(false)" class="search-button" :disabled="isSearching || !searchQuery.trim()">
            <font-awesome-icon v-if="!isSearching" icon="search" />
            <span v-else>Searching...</span>
          </button>
        </div>
      </div>
      
      <div class="paper-count" v-if="paperCount !== null">
        <p>Currently indexed <strong>{{ paperCount }}</strong> papers</p>
      </div>
    </div>
    
    <!-- Search Results Section -->
    <div v-if="showSearchResults" class="search-results-section">
      <h2>Search Results</h2>
      
      <div v-if="isSearching" class="loading">
        <p>Searching papers...</p>
      </div>
      
      <div v-else-if="searchResults.length === 0" class="no-results">
        <p>No results found for "{{ searchQuery }}"</p>
        <button @click="resetSearch" class="secondary-button">Show Recent Papers</button>
      </div>
      
      <div v-else class="papers-list">
        <PaperCard v-for="paper in searchResults" :key="paper.paper_id" :paper="paper" />
      </div>
      
      <div class="search-actions">
        <button @click="resetSearch" class="secondary-button">Back to Recent Papers</button>
      </div>
    </div>
    
    <!-- Papers Sections Container (shown when not searching) -->
    <div v-if="!showSearchResults" class="papers-container">
      <!-- Recent Papers List -->
      <div class="recent-papers">
        <h2>Recent Papers</h2>
        
        <div v-if="isLoading" class="loading">
          Loading papers...
        </div>
        
        <div v-else-if="papers.length === 0" class="no-papers">
          <p>No papers found. Our system will automatically fetch new papers periodically.</p>
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
      
      <!-- Recommended Papers Based on Search History -->
      <div v-if="recommendedPapers.length > 0" class="recommended-papers">
        <h2>Recommendations</h2>
        
        <div v-if="isLoadingRecommended" class="loading">
          Loading recommendations...
        </div>
        
        <div v-else class="papers-list">
          <PaperCard v-for="paper in recommendedPapers" :key="paper.paper_id" :paper="paper" />
        </div>
        
        <!-- Load More button for Recommended Papers -->
        <div v-if="recommendedPapers.length > 0" class="section-load-more">
          <button 
            v-if="hasMoreRecommended" 
            @click="loadMoreRecommended" 
            :disabled="isLoadingMoreRecommended"
            class="secondary-button"
          >
            {{ isLoadingMoreRecommended ? 'Loading...' : 'Load More Recommendations' }}
          </button>
        </div>
      </div>
    </div>
  </div>
</template>

<script>
import { defineComponent, ref, onMounted, computed, watch } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import PaperCard from '../components/PaperCard.vue'
import api from '../services/api'

export default defineComponent({
  name: 'HomeView',
  
  components: {
    PaperCard
  },
  
  setup() {
    const router = useRouter();
    const route = useRoute();
    
    // --- Define refs first ---
    const papers = ref([]);
    const paperCount = ref(null);
    const isLoading = ref(false);
    const isLoadingMoreRecent = ref(false);
    const isLoadingMoreRecommended = ref(false);
    const offset = ref(0);
    const limit = ref(10);
    const hasMorePapers = ref(true);
    const recommendedPapers = ref([]);
    const isLoadingRecommended = ref(false);
    const recommendedOffset = ref(0);
    const hasMoreRecommended = ref(true);
    const searchQuery = ref('');
    const searchResults = ref([]);
    const isSearching = ref(false);
    const showSearchResults = computed(() => searchResults.value.length > 0 || (searchQuery.value && isSearching.value));

    // --- Define methods that might be called by watchers or onMount ---
    // Perform search
    const performSearch = async (isRouteTriggered = false) => {
      const query = searchQuery.value.trim();
      if (!query) return;
      
      console.log(`Performing search for: "${query}", Triggered by route: ${isRouteTriggered}`);
      
      try {
        if (!isRouteTriggered) {
          console.log('Saving search history (direct user action)');
          await api.saveSearchHistory(query);
        } else {
          console.log('Skipping search history save (triggered by route change)');
        }
        
        isSearching.value = true;
        searchResults.value = [];
        
        const searchPayload = { query: query }; 
        const results = await api.searchPapers(searchPayload);
        
        // Adjust based on actual API response structure
        searchResults.value = Array.isArray(results) ? results : (results?.results || []);
        
        if (!isRouteTriggered && route.query.q !== query) {
          router.replace({ query: { ...route.query, q: query } }).catch(err => {});
        }
        
      } catch (error) {
        console.error('Error performing search:', error);
        searchResults.value = [];
      } finally {
        isSearching.value = false;
      }
    };

    // Reset search state
    const resetSearch = () => {
      searchQuery.value = '';
      searchResults.value = [];
      isSearching.value = false;
      if (route.query.q) {
        router.replace({ query: { ...route.query, q: undefined } }).catch(err => {});
      }
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
    
    // Load recommended papers
    const loadRecommendedPapers = async () => {
      try {
        isLoadingRecommended.value = true;
        recommendedPapers.value = await api.getRecommendedPapers(limit.value);
        recommendedOffset.value = recommendedPapers.value.length;
        hasMoreRecommended.value = recommendedPapers.value.length === limit.value;
      } catch (error) { console.error('Error loading recommended papers:', error); recommendedPapers.value = []; }
      finally { isLoadingRecommended.value = false; }
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
    
    // Load more recommended papers
    const loadMoreRecommended = async () => {
      try {
        isLoadingMoreRecommended.value = true;
        const moreRecommendedPapers = await api.getRecommendedPapers(limit.value, recommendedOffset.value);
        recommendedPapers.value = [...recommendedPapers.value, ...moreRecommendedPapers];
        recommendedOffset.value += moreRecommendedPapers.length;
        hasMoreRecommended.value = moreRecommendedPapers.length === limit.value;
      } catch (error) { console.error('Error loading more recommended papers:', error); }
      finally { isLoadingMoreRecommended.value = false; }
    };

    // --- Define Lifecycle Hooks and Watchers Last ---
    // Watch for route query parameter changes
    watch(
      () => route.query.q,
      (newQuery, oldQuery) => {
        const newQueryStr = typeof newQuery === 'string' ? newQuery : '';
        const oldQueryStr = typeof oldQuery === 'string' ? oldQuery : '';
        
        // Now performSearch is guaranteed to be initialized
        if (newQueryStr && newQueryStr !== oldQueryStr && newQueryStr !== searchQuery.value) {
          console.log('Route query changed, triggering search:', newQueryStr);
          searchQuery.value = newQueryStr;
          performSearch(true); // Call the already defined function
        } else if (!newQueryStr && searchResults.value.length > 0) {
          console.log('Route query removed, resetting search.');
          resetSearch(); // Call the already defined function
        }
      },
      { immediate: true } // Runs immediately, calling the defined performSearch/resetSearch
    );
    
    // Save/Restore scroll position (can stay here or move earlier)
    const saveScrollPosition = () => {
      const path = router.currentRoute.value.fullPath;
      sessionStorage.setItem(`scrollPos-${path}`, window.scrollY.toString());
    };
    const restoreScrollPosition = () => {
      const path = router.currentRoute.value.fullPath;
      const savedPosition = sessionStorage.getItem(`scrollPos-${path}`);
      
      if (savedPosition) {
        requestAnimationFrame(() => {
          window.scrollTo({
            top: parseInt(savedPosition, 10),
            behavior: 'instant'
          });
        });
      }
    };
    const onActivated = () => { restoreScrollPosition(); };
    const onDeactivated = () => { saveScrollPosition(); };

    onMounted(() => {
      // Check initial route query on mount - performSearch is now defined
      if (route.query.q && typeof route.query.q === 'string') {
        if (searchQuery.value !== route.query.q) {
           searchQuery.value = route.query.q;
           performSearch(true); 
        }
      } else {
        // Load initial data only if not searching
        loadPapers();
        loadRecommendedPapers();
      }
      // Restore scroll position on initial mount too, if needed
      // restoreScrollPosition(); 
    });
    
    // --- Return all refs and methods ---
    return {
      papers, paperCount, isLoading, 
      isLoadingMoreRecent, loadMoreRecent,
      isLoadingMoreRecommended, loadMoreRecommended,
      offset, limit, hasMorePapers,
      recommendedPapers, isLoadingRecommended, hasMoreRecommended,
      searchQuery, searchResults, isSearching, showSearchResults,
      performSearch, resetSearch,
      onActivated, onDeactivated
    };
  },
  
  // Component activation and deactivation hooks
  activated() {
    this.onActivated();
  },
  
  deactivated() {
    this.onDeactivated();
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

/* Search container styles */
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

.paper-count {
  font-size: 1rem;
  color: #666;
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
  display: flex;
  gap: 3rem;
  margin-bottom: 3rem;
  position: relative;
}

.papers-container::after {
  content: '';
  position: absolute;
  left: 50%;
  top: 0;
  bottom: 0;
  width: 1px;
  background-color: #eee;
  transform: translateX(-50%);
}

.recent-papers, .recommended-papers {
  flex: 1;
  margin-bottom: 2rem;
  min-width: 0;
  max-width: calc(50% - 1.5rem);
  padding-right: 0.5rem;
  padding-left: 0.5rem;
  box-sizing: border-box;
}

.recent-papers h2, .recommended-papers h2 {
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

/* Responsive layout adjustments */
@media (max-width: 960px) {
  .papers-container {
    flex-direction: column;
  }

  .papers-container::after {
    display: none;
  }
  
  .recent-papers, .recommended-papers {
    width: 100%;
    max-width: 100%;
    padding: 0;
  }
}

/* Search Results Styles */
.search-results-section {
  margin-bottom: 2rem;
}

.search-results-section h2 {
  margin-bottom: 1rem;
  color: #3f51b5;
}

.no-results {
  text-align: center;
  padding: 2rem;
  background-color: #f5f5f5;
  border-radius: 8px;
  margin-bottom: 2rem;
}

.no-results p {
  margin-bottom: 1rem;
  color: #666;
}

.search-actions {
  display: flex;
  justify-content: center;
  margin-top: 2rem;
}
</style> 