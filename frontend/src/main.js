import { createApp } from 'vue'
import { createPinia } from 'pinia'
import App from './App.vue'
import router from './router'

// Import Font Awesome core
import { library } from '@fortawesome/fontawesome-svg-core'
// Import Font Awesome icons
import { faSearch, faCog, faTimes } from '@fortawesome/free-solid-svg-icons'
// Import Font Awesome component
import { FontAwesomeIcon } from '@fortawesome/vue-fontawesome'

// Add icons to the library
library.add(faSearch, faCog, faTimes)

// Create Vue application
const app = createApp(App)

// Register global components
app.component('font-awesome-icon', FontAwesomeIcon)

// Use Pinia for state management
app.use(createPinia())

// Use Vue Router for navigation
app.use(router)

// Mount app
app.mount('#app') 