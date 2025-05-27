import { reactive } from 'vue'

interface SearchState {
  query: string
  results: any[]
  hasSearched: boolean
  sortBy: string
}

const searchState = reactive<SearchState>({
  query: '',
  results: [],
  hasSearched: false,
  sortBy: 'relevance'
})

export const searchStore = {
  // Getters
  getQuery: () => searchState.query,
  getResults: () => searchState.results,
  getHasSearched: () => searchState.hasSearched,
  getSortBy: () => searchState.sortBy,

  setSortBy: (sortBy: string) => {
    searchState.sortBy = sortBy
  },
  
  // Actions
  setQuery: (query: string) => {
    searchState.query = query
  },
  
  setResults: (results: any[]) => {
    searchState.results = results
    searchState.hasSearched = true
  },
  
  clearSearch: () => {
    searchState.query = ''
    searchState.results = []
    searchState.hasSearched = false
  },
  
  // Check if we have cached results for a query
  hasCachedResults: (query: string) => {
    return searchState.hasSearched && 
           searchState.query === query && 
           searchState.results.length > 0
  }
} 