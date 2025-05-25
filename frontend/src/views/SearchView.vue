<template>
  <div class="search">
    <div class="hero-section">
      <h1>Search Papers</h1>
      
      <SearchBox
        v-model="searchQuery"
        :is-loading="isLoading"
        @search="performSearch"
      />
    </div>
    
    <!-- Search Results Section -->
    <div class="papers-container">
      <div class="recent-papers">
        <h2>Search Results</h2>
        
        <div v-if="isLoading" class="loading">
          <p>Searching papers...</p>
        </div>
        
        <div v-else-if="results.length === 0" class="no-results">
          <p>No results found for "{{ searchQuery }}"</p>
        </div>
        
        <div v-else-if="results.length > 0" class="papers-list">
          <PaperCard v-for="paper in results" :key="paper.paper_id" :paper="paper" />
        </div>
        
        <!-- Initial instructions -->
        <div v-else class="search-instructions">
          <p>Enter a search query to find relevant papers.</p>
        </div>
      </div>
    </div>
  </div>
</template>

<script>
import api from '../services/api'
import SearchBox from '../components/SearchBox.vue'
import PaperCard from '../components/PaperCard.vue'

export default {
  name: 'SearchView',
  components: {
    SearchBox,
    PaperCard
  },
  data() {
    return {
      searchQuery: '',
      results: [],
      isLoading: false
    }
  },
  watch: {
    '$route.query.q': {
      immediate: true,
      handler(newQuery) {
        if (newQuery) {
          this.searchQuery = newQuery;
          this.performSearch();
        }
      }
    }
  },
  methods: {
    async performSearch() {
      if (!this.searchQuery.trim()) return;
      
      this.isLoading = true;
      this.results = [];
      
      try {
        const data = await api.searchPapers({
          query: this.searchQuery.trim(),
          limit: 30
        });
        
        if (data && Array.isArray(data.results)) {
          this.results = data.results.map(paper => ({
            ...paper,
            authors: Array.isArray(paper.authors) ? paper.authors : 
                     (typeof paper.authors === 'string' ? [paper.authors] : []),
            abstract: paper.abstract || 'No abstract available',
            year: paper.year || '',
            venue: paper.venue || 'Unknown venue',
            categories: Array.isArray(paper.categories) ? paper.categories : 
                       (paper.categories ? [paper.categories] : [])
          }));
        } else {
          console.error('Invalid search results format', data);
          this.results = [];
        }
        
        this.$router.replace({ 
          query: { q: this.searchQuery.trim() } 
        });
      } catch (error) {
        console.error('Error searching papers:', error);
        this.results = [];
      } finally {
        this.isLoading = false;
      }
    }
  }
}
</script>

<style scoped>
.search {
  max-width: 1000px;
  margin: 0 auto;
}

.hero-section {
  text-align: center;
  padding: 2rem 0;
  margin-bottom: 2rem;
}

.hero-section h1 {
  margin-top: 0;
  margin-bottom: 1.5rem;
  color: #3f51b5;
  text-align: center;
  font-size: 2rem;
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

.loading, .no-results, .search-instructions {
  text-align: center;
  padding: 2rem;
  color: #666;
  background-color: white;
  border-radius: 8px;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
  margin: 1rem 0;
}

@media (max-width: 768px) {
  .papers-list {
    grid-template-columns: 1fr;
  }
}
</style> 