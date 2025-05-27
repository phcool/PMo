import { reactive } from 'vue'

interface SearchState {
  query: string
  results: any[]
  isLoading: boolean
  hasSearched: boolean
}

const searchState = reactive<SearchState>({
  query: '',
  results: [],
  isLoading: false,
  hasSearched: false
})

export const searchStore = {
  // Getters
  getQuery: () => searchState.query,
  getResults: () => searchState.results,
  getIsLoading: () => searchState.isLoading,
  getHasSearched: () => searchState.hasSearched,
  
  // Actions
  setQuery: (query: string) => {
    searchState.query = query
  },
  
  setResults: (results: any[]) => {
    searchState.results = results
    searchState.hasSearched = true
  },
  
  setLoading: (loading: boolean) => {
    searchState.isLoading = loading
  },
  
  clearSearch: () => {
    searchState.query = ''
    searchState.results = []
    searchState.hasSearched = false
    searchState.isLoading = false
  },
  
  // Check if we have cached results for a query
  hasCachedResults: (query: string) => {
    return searchState.hasSearched && 
           searchState.query === query && 
           searchState.results.length > 0
  }
} 