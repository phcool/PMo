<template>
  <div class="paper-card">
    <h3 class="paper-title">
      <a :href="`https://arxiv.org/abs/${paper.paper_id}`" target="_blank" rel="noopener" @click="recordView">
        {{ paper.title }}
      </a>
    </h3>
    
    <div class="paper-meta">
      <span class="paper-authors">{{ authorText }}</span>
      <span class="paper-date">{{ formattedDate }}</span>
    </div>
    
    <div class="paper-categories">
      <span 
        v-for="category in paper.categories" 
        :key="category" 
        class="category-tag"
      >
        {{ getCategoryLabel(category) }}
      </span>
    </div>
    
    <p class="paper-abstract">{{ truncatedAbstract }}</p>
    
    <div class="paper-actions">
      <a :href="paper.pdf_url" target="_blank" rel="noopener" class="action-button" @click="recordView">
        View PDF
      </a>
      <router-link :to="{ name: 'paper-detail', params: { id: paper.paper_id } }" class="action-button">
        Details
      </router-link>
    </div>
  </div>
</template>

<script>
import { defineComponent, computed } from 'vue'
import { getCategoryLabel } from '../types/paper'
import api from '../services/api'

export default defineComponent({
  name: 'PaperCard',
  
  props: {
    paper: {
      type: Object,
      required: true
    }
  },
  
  setup(props) {
    // Format the authors list (show first 3 names, then "et al" if more)
    const authorText = computed(() => {
      const authors = props.paper.authors;
      if (!authors || authors.length === 0) return 'Unknown authors';
      
      if (authors.length <= 3) {
        return authors.join(', ');
      } else {
        return `${authors.slice(0, 3).join(', ')} et al.`;
      }
    });
    
    // Format the date
    const formattedDate = computed(() => {
      try {
        const date = new Date(props.paper.published_date);
        return date.toLocaleDateString('en-US', {
          year: 'numeric',
          month: 'short',
          day: 'numeric'
        });
      } catch (e) {
        return props.paper.published_date;
      }
    });
    
    // Truncate abstract to reasonable length
    const truncatedAbstract = computed(() => {
      const abstract = props.paper.abstract;
      if (abstract.length <= 250) return abstract;
      
      return abstract.substring(0, 250) + '...';
    });
    
    // Record paper view
    const recordView = () => {
      // Use async function and catch errors without blocking user interaction
      setTimeout(async () => {
        try {
          await api.recordPaperView(props.paper.paper_id);
          console.log('Paper view recorded');
        } catch (error) {
          console.error('Failed to record paper view:', error);
        }
      }, 0);
    };
    
    return {
      authorText,
      formattedDate,
      truncatedAbstract,
      getCategoryLabel,
      recordView
    };
  }
})
</script>

<style scoped>
.paper-card {
  background-color: white;
  border-radius: 8px;
  padding: 1.5rem;
  margin-bottom: 0.5rem;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
  transition: box-shadow 0.3s ease;
  display: flex;
  flex-direction: column;
  height: calc(100% - 0.5rem); /* Subtract bottom margin */
  overflow: hidden; /* Prevent content overflow */
  width: 100%; /* Ensure width doesn't exceed container */
  max-width: 100%; /* Ensure max width doesn't exceed container */
  box-sizing: border-box; /* Ensure padding doesn't increase element total width */
}

.paper-card:hover {
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);
}

.paper-title {
  margin-top: 0;
  margin-bottom: 0.75rem;
  font-size: 1.25rem;
  line-height: 1.4;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
  height: 2.8em; /* Approximately two lines height */
  width: 100%; /* Ensure width doesn't exceed container */
}

.paper-title a {
  color: #3f51b5;
  text-decoration: none;
  display: inline-block;
  max-width: 100%; /* Ensure links don't exceed container */
  overflow: hidden;
  text-overflow: ellipsis;
}

.paper-title a:hover {
  text-decoration: underline;
}

.paper-meta {
  display: flex;
  justify-content: space-between;
  font-size: 0.9rem;
  margin-bottom: 0.75rem;
  color: #666;
}

.paper-authors {
  font-style: italic;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  max-width: 70%;
}

.paper-categories {
  display: flex;
  flex-wrap: wrap;
  gap: 0.5rem;
  margin-bottom: 1rem;
  min-height: 1.8rem; /* Ensure categories area has minimum height */
}

.category-tag {
  background-color: #e3f2fd;
  color: #1976d2;
  padding: 0.2rem 0.5rem;
  border-radius: 4px;
  font-size: 0.8rem;
}

.paper-abstract {
  color: #333;
  margin-bottom: 1rem;
  line-height: 1.5;
  display: -webkit-box;
  -webkit-line-clamp: 3;
  -webkit-box-orient: vertical;
  overflow: hidden;
  flex-grow: 1;
  height: 4.5em; /* Approximately three lines height */
}

.paper-actions {
  display: flex;
  gap: 0.75rem;
  margin-top: auto; /* Push action buttons to the bottom */
}

.action-button {
  padding: 0.5rem 1rem;
  background-color: #f0f0f0;
  color: #333;
  border-radius: 4px;
  text-decoration: none;
  font-size: 0.9rem;
  transition: background-color 0.2s;
}

.action-button:hover {
  background-color: #e0e0e0;
}
</style> 