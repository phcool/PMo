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

// Import styles

// Import Toast
import Toast from 'vue-toastification'
import 'vue-toastification/dist/index.css'

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

// Toast configuration
const toastOptions = {
  position: 'top-right',
  timeout: 3000,
  closeOnClick: true,
  pauseOnFocusLoss: true,
  pauseOnHover: true,
  draggable: true,
  draggablePercent: 0.6,
  hideProgressBar: false,
  closeButton: 'button',
  icon: true,
  rtl: false,
  transition: 'Vue-Toastification__bounce',
  maxToasts: 3
}

app.use(Toast, toastOptions)

// Mount app
app.mount('#app') 