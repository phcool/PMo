<template>
  <div class="paper-card">
    <h3 class="paper-title">
      <a :href="`https://arxiv.org/abs/${paper.paper_id}`" target="_blank" rel="noopener">
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
      <a :href="paper.pdf_url" target="_blank" rel="noopener" class="action-button">
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
    
    return {
      authorText,
      formattedDate,
      truncatedAbstract,
      getCategoryLabel
    };
  }
})
</script>

<style scoped>
.paper-card {
  background-color: white;
  border-radius: 8px;
  padding: 1.5rem;
  margin-bottom: 1.5rem;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
  transition: box-shadow 0.3s ease;
}

.paper-card:hover {
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);
}

.paper-title {
  margin-top: 0;
  margin-bottom: 0.75rem;
  font-size: 1.25rem;
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
  font-size: 0.9rem;
  margin-bottom: 0.75rem;
  color: #666;
}

.paper-authors {
  font-style: italic;
}

.paper-categories {
  display: flex;
  flex-wrap: wrap;
  gap: 0.5rem;
  margin-bottom: 1rem;
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
}

.paper-actions {
  display: flex;
  gap: 0.75rem;
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