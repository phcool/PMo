<template>
  <div class="user-preferences">
    <h3>User Preferences</h3>
    
    <div v-if="loading" class="loading">
      <p>Loading...</p>
    </div>
    
    <div v-else-if="error" class="error">
      <p>{{ error }}</p>
      <button @click="loadPreferences">Retry</button>
    </div>
    
    <div v-else class="preferences-form">
      <!-- Theme Settings -->
      <div class="preference-item">
        <label for="theme">Theme:</label>
        <select id="theme" v-model="preferences.theme">
          <option value="light">Light</option>
          <option value="dark">Dark</option>
          <option value="system">System</option>
        </select>
      </div>
      
      <!-- Papers Per Page -->
      <div class="preference-item">
        <label for="pageSize">Papers per page:</label>
        <select id="pageSize" v-model="preferences.pageSize">
          <option value="10">10</option>
          <option value="20">20</option>
          <option value="50">50</option>
        </select>
      </div>
      
      <!-- Default Sort -->
      <div class="preference-item">
        <label for="defaultSort">Default sort:</label>
        <select id="defaultSort" v-model="preferences.defaultSort">
          <option value="date">Publication date</option>
          <option value="relevance">Relevance</option>
          <option value="title">Title</option>
        </select>
      </div>
      
      <!-- Save Button -->
      <div class="action-buttons">
        <button @click="savePreferences" :disabled="isSaving">
          {{ isSaving ? 'Saving...' : 'Save Settings' }}
        </button>
      </div>
      
      <!-- Save Success Message -->
      <div v-if="saveSuccess" class="save-success">
        Settings saved!
      </div>
    </div>
  </div>
</template>

<script>
import { defineComponent, ref, reactive, onMounted } from 'vue';
import api from '../services/api';

export default defineComponent({
  name: 'UserPreferences',
  
  setup() {
    const loading = ref(true);
    const error = ref(null);
    const isSaving = ref(false);
    const saveSuccess = ref(false);
    
    // Default preferences
    const defaultPreferences = {
      theme: 'light',
      pageSize: '10',
      defaultSort: 'date'
    };
    
    // User preferences
    const preferences = reactive({...defaultPreferences});
    
    // Load user preferences
    const loadPreferences = async () => {
      loading.value = true;
      error.value = null;
      
      try {
        const response = await api.getUserPreferences();
        
        // Merge returned preferences with defaults
        Object.assign(preferences, defaultPreferences, response.preferences);
        
        loading.value = false;
      } catch (err) {
        console.error('Failed to load preferences:', err);
        error.value = 'Failed to load preferences.';
        loading.value = false;
      }
    };
    
    // Save user preferences
    const savePreferences = async () => {
      isSaving.value = true;
      saveSuccess.value = false;
      
      try {
        await api.saveUserPreferences({...preferences});
        
        isSaving.value = false;
        saveSuccess.value = true;
        
        // Hide success message after 3 seconds
        setTimeout(() => {
          saveSuccess.value = false;
        }, 3000);
      } catch (err) {
        console.error('Failed to save preferences:', err);
        error.value = 'Failed to save preferences.';
        isSaving.value = false;
      }
    };
    
    // Load preferences when component is mounted
    onMounted(() => {
      loadPreferences();
    });
    
    return {
      loading,
      error,
      preferences,
      isSaving,
      saveSuccess,
      loadPreferences,
      savePreferences
    };
  }
});
</script>

<style scoped>
.user-preferences {
  background-color: #fff;
  border-radius: 8px;
  padding: 20px;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
  max-width: 500px;
  margin: 0 auto;
}

.user-preferences h3 {
  margin-top: 0;
  color: #333;
  border-bottom: 1px solid #eee;
  padding-bottom: 10px;
}

.loading, .error {
  text-align: center;
  padding: 20px 0;
}

.error {
  color: #d32f2f;
}

.preference-item {
  margin-bottom: 15px;
  display: flex;
  align-items: center;
}

.preference-item label {
  min-width: 150px;
  display: block;
  margin-right: 10px;
}

.preference-item select {
  padding: 8px 12px;
  border: 1px solid #ddd;
  border-radius: 4px;
  background-color: #fff;
  flex: 1;
}

.action-buttons {
  margin-top: 20px;
  display: flex;
  justify-content: flex-end;
}

.action-buttons button {
  padding: 8px 16px;
  background-color: #3f51b5;
  color: white;
  border: none;
  border-radius: 4px;
  cursor: pointer;
  transition: background-color 0.2s;
}

.action-buttons button:hover {
  background-color: #303f9f;
}

.action-buttons button:disabled {
  background-color: #9fa8da;
  cursor: not-allowed;
}

.save-success {
  margin-top: 15px;
  color: #4caf50;
  text-align: center;
  font-weight: bold;
}
</style> 