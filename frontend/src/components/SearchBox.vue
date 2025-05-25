<template>
  <div class="search-container">
    <div class="search-form">
      <input 
        v-model="localSearchQuery" 
        class="search-input" 
        :placeholder="placeholder" 
        @keyup.enter="handleSearch"
        aria-label="Search papers"
      />
      <button 
        @click="handleSearch" 
        class="search-button" 
        :disabled="isLoading || !localSearchQuery.trim()"
      >
        <font-awesome-icon v-if="!isLoading" icon="search" />
        <span v-else>Searching...</span>
      </button>
    </div>
  </div>
</template>

<script>
export default {
  name: 'SearchBox',
  props: {
    modelValue: {
      type: String,
      default: ''
    },
    isLoading: {
      type: Boolean,
      default: false
    },
    placeholder: {
      type: String,
      default: 'Search papers...'
    }
  },
  emits: ['update:modelValue', 'search'],
  computed: {
    localSearchQuery: {
      get() {
        return this.modelValue;
      },
      set(value) {
        this.$emit('update:modelValue', value);
      }
    }
  },
  methods: {
    handleSearch() {
      if (this.localSearchQuery.trim()) {
        this.$emit('search', this.localSearchQuery.trim());
      }
    }
  }
}
</script>

<style scoped>
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
</style> 