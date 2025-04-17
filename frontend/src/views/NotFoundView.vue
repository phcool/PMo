<template>
  <div class="not-found">
    <div class="not-found-container">
      <h1>404</h1>
      <h2>Page Not Found</h2>
      <p>The page you are looking for does not exist or has been moved.</p>
      <router-link to="/" class="home-link">Go to Home</router-link>
    </div>
  </div>
</template>

<script>
import { defineComponent } from 'vue'

export default defineComponent({
  name: 'NotFoundView'
})
</script>

<style scoped>
.not-found {
  display: flex;
  justify-content: center;
  align-items: center;
  min-height: 60vh;
}

.not-found-container {
  text-align: center;
  padding: 3rem;
  background-color: white;
  border-radius: 8px;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
  max-width: 500px;
}

h1 {
  font-size: 6rem;
  margin: 0;
  color: #3f51b5;
  line-height: 1;
}

h2 {
  font-size: 1.8rem;
  margin-bottom: 1rem;
  color: #333;
}

p {
  font-size: 1.1rem;
  color: #666;
  margin-bottom: 2rem;
}

.home-link {
  display: inline-block;
  padding: 0.75rem 1.5rem;
  background-color: #3f51b5;
  color: white;
  text-decoration: none;
  border-radius: 4px;
  font-size: 1rem;
  transition: background-color 0.2s;
}

.home-link:hover {
  background-color: #303f9f;
}
</style>