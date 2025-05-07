<template>
  <div class="search">
    <div class="search-container">
      <h1>Search Papers</h1>
      
      <div class="search-form">
        <input 
          v-model="searchQuery" 
          @keyup.enter="performSearch"
          class="search-input" 
          placeholder="Search papers..." 
          aria-label="Search papers"
        />
        <button 
          @click="performSearch" 
          :disabled="isLoading || !searchQuery.trim()"
          class="search-button"
        >
          <font-awesome-icon v-if="!isLoading" icon="search" />
          <span v-else>Searching...</span>
        </button>
      </div>
      
      <!-- Loading indicator -->
      <div v-if="isLoading" class="loading">
        <p>Searching papers...</p>
      </div>
      
      <!-- No results message -->
      <div v-else-if="hasSearched && results.length === 0" class="no-results">
        <p>No results found for "{{ searchQuery }}"</p>
      </div>
      
      <!-- Results list -->
      <div v-else-if="hasSearched && results.length > 0" class="search-results">
        <h2>Search Results</h2>
        <div class="results-list">
          <div 
            v-for="(paper, index) in results" 
            :key="paper.paper_id || index" 
            class="paper-card"
          >
            <h3 class="paper-title">
              <a v-if="paper.paper_id" :href="`https://arxiv.org/abs/${paper.paper_id}`" target="_blank" rel="noopener noreferrer">
                {{ paper.title }}
              </a>
              <span v-else>{{ paper.title }}</span>
            </h3>
            <div class="paper-meta">
              <p class="paper-authors">{{ paper.authors.join(', ') }}</p>
              <p class="paper-date">{{ paper.year }}</p>
            </div>
            <div class="paper-categories">
              <span v-for="(category, idx) in (paper.categories || [])" :key="idx" class="category-tag">
                {{ category }}
              </span>
            </div>
            <p class="paper-abstract">{{ paper.abstract.substring(0, 200) }}...</p>
            <div class="paper-links">
              <a v-if="paper.pdf_url" :href="paper.pdf_url" target="_blank" rel="noopener noreferrer" class="paper-button">
                View PDF
              </a>
              <router-link v-if="paper.paper_id" :to="{ name: 'paper-detail', params: { id: paper.paper_id }}" class="paper-button">
                Details
              </router-link>
            </div>
          </div>
        </div>
      </div>
      
      <!-- Initial instructions -->
      <div v-else class="search-instructions">
        <p>Enter a search query to find relevant deep learning papers.</p>
        <p>The search uses vector embeddings to find semantically similar papers to your query.</p>
      </div>
    </div>
  </div>
</template>

<script>
import api from '../services/api'

export default {
  name: 'SearchView',
  data() {
    return {
      searchQuery: '',
      results: [],
      isLoading: false,
      hasSearched: false
    }
  },
  mounted() {
    // If there's a query parameter, perform search automatically
    const query = this.$route.query.q
    if (query) {
      this.searchQuery = query
      this.performSearch()
    }
  },
  activated() {
    // Restore scroll position from sessionStorage
    const path = this.$route.fullPath;
    const savedPosition = sessionStorage.getItem(`scrollPos-${path}`);
    
    if (savedPosition) {
      requestAnimationFrame(() => {
        window.scrollTo({
          top: parseInt(savedPosition, 10),
          behavior: 'instant'
        });
      });
    }
  },
  deactivated() {
    // Save scroll position to sessionStorage
    const path = this.$route.fullPath;
    sessionStorage.setItem(`scrollPos-${path}`, window.scrollY.toString());
  },
  methods: {
    async performSearch() {
      if (!this.searchQuery.trim()) return
      
      this.isLoading = true
      this.hasSearched = true  // Set to true immediately so loading shows
      this.results = []  // Clear previous results
      
      try {
        // Save search history
        api.saveSearchHistory(this.searchQuery.trim())
        
        // Use the API service with POST method
        const data = await api.searchPapers({
          query: this.searchQuery.trim(),
          limit: 30
        })
        
        // Process and validate results before assigning
        if (data && Array.isArray(data.results)) {
          this.results = data.results.map(paper => {
            // Ensure paper has all required properties
            return {
              ...paper,
              // Ensure authors is an array
              authors: Array.isArray(paper.authors) ? paper.authors : 
                       (typeof paper.authors === 'string' ? [paper.authors] : []),
              // Ensure abstract exists
              abstract: paper.abstract || 'No abstract available',
              // Ensure year exists
              year: paper.year || '',
              // Ensure venue exists
              venue: paper.venue || 'Unknown venue',
              // Process categories
              categories: Array.isArray(paper.categories) ? paper.categories : 
                         (paper.categories ? [paper.categories] : [])
            }
          })
        } else {
          console.error('Invalid search results format', data)
          this.results = []
        }
        
        // Update URL with search query
        this.$router.replace({ 
          query: { q: this.searchQuery.trim() } 
        })
      } catch (error) {
        console.error('Error searching papers:', error)
        this.results = []
      } finally {
        this.isLoading = false
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

.search-container {
  background-color: white;
  border-radius: 8px;
  padding: 1.5rem;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
  margin: 0 auto;
}

.search-container h1 {
  margin-top: 0;
  margin-bottom: 1.5rem;
  color: #3f51b5;
  text-align: center;
  font-size: 2rem;
}

.search-form {
  display: flex;
  margin-bottom: 1.5rem;
  max-width: 600px;
  margin-left: auto;
  margin-right: auto;
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

.search-results {
  margin-top: 2rem;
}

.search-results h2 {
  margin-bottom: 1.5rem;
  color: #333;
  border-bottom: 1px solid #eee;
  padding-bottom: 0.75rem;
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

.results-list {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(350px, 1fr));
  gap: 24px;
}

@media (max-width: 768px) {
  .results-list {
    grid-template-columns: 1fr;
  }
}

.paper-card {
  background: white;
  border: 1px solid #eee;
  border-radius: 8px;
  padding: 20px;
  box-shadow: 0 2px 4px rgba(0, 0, 0, 0.05);
  transition: transform 0.2s, box-shadow 0.2s;
  display: flex;
  flex-direction: column;
  height: 100%;
}

.paper-card:hover {
  transform: translateY(-3px);
  box-shadow: 0 4px 8px rgba(0, 0, 0, 0.1);
}

.paper-title {
  font-size: 18px;
  margin-top: 0;
  margin-bottom: 12px;
  line-height: 1.4;
}

.paper-title a {
  color: #3f51b5;
  text-decoration: none;
}

.paper-title a:hover {
  text-decoration: underline;
}

.paper-meta {
  display: flex;
  justify-content: space-between;
  margin-bottom: 12px;
}

.paper-authors {
  color: #555;
  font-size: 14px;
  margin: 0;
  flex: 1;
}

.paper-date {
  color: #777;
  font-size: 14px;
  margin: 0;
  text-align: right;
}

.paper-categories {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-bottom: 12px;
}

.category-tag {
  background-color: #f0f5ff;
  color: #3f51b5;
  font-size: 12px;
  padding: 4px 8px;
  border-radius: 4px;
}

.paper-abstract {
  color: #333;
  font-size: 14px;
  line-height: 1.5;
  margin-bottom: 16px;
  flex-grow: 1;
}

.paper-links {
  display: flex;
  gap: 12px;
}

.paper-button {
  display: inline-block;
  background-color: #f0f5ff;
  color: #3f51b5;
  border: 1px solid #d0dcff;
  padding: 8px 16px;
  border-radius: 4px;
  text-decoration: none;
  font-weight: 500;
  font-size: 14px;
  transition: all 0.2s;
}

.paper-button:hover {
  background-color: #d0dcff;
  text-decoration: none;
}

.pdf-link {
  color: #e91e63 !important;
}
</style> 