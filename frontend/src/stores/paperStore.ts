import { reactive } from 'vue'
import type { Paper } from '../types/paper'

const paperStore = reactive({
  currentPaper: null as Paper | null,
  
  setCurrentPaper(paper: Paper) {
    this.currentPaper = paper
  },
  
  getCurrentPaper(): Paper | null {
    return this.currentPaper
  },
  
  clearCurrentPaper() {
    this.currentPaper = null
  }
})

export { paperStore } 