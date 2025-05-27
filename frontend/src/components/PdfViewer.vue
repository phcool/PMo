<template>
  <div class="pdf-viewer-container">
    <div v-if="loading" class="loading">
      <div class="loading-spinner"></div>
      <p>Loading PDF...</p>
    </div>
    
    <!-- Error message -->
    <div v-if="error" class="error">
      <p>{{ error }}</p>
      <div class="pdf-actions">
        <button @click="reloadPdf" class="action-button">Retry</button>
        <a :href="pdfUrl" target="_blank" class="action-button primary">Open in new window</a>
      </div>
    </div>
    
    <!--embed PDF -->
    <object 
      v-show="!loading"
      ref="pdfObject"
      :data="pdfUrl" 
      type="application/pdf"
      class="pdf-object"
    >
      <div class="pdf-fallback">
        <p>Your browser cannot display PDF files directly.</p>
      </div>
    </object>
  </div>
</template>

<script>
export default {
  name: 'PdfViewer',
  props: {
    pdfUrl: {
      type: String,
      required: true
    }
  },
  data() {
    return {
      loading: true,
      error: null
    }
  },
  mounted() {
    this.setupPdfObject();
  },
  watch: {
    pdfUrl() {
      this.loading = true;
      this.error = null;
      this.$nextTick(() => {
        this.setupPdfObject();
      });
    }
  },
  methods: {
    setupPdfObject() {
      this.loading = true;
      this.error = null;
      
      setTimeout(() => {
        const pdfObject = this.$refs.pdfObject;
        
        if (pdfObject) {
          // Listen for load complete event
          pdfObject.onload = () => {
            console.log('PDF loading complete');
            this.loading = false;
          };
          
          // Set 30 second timeout
          setTimeout(() => {
            if (this.loading) {
              // If still loading, it might be stuck
              if (pdfObject.contentDocument && 
                  pdfObject.contentDocument.body && 
                  pdfObject.contentDocument.body.childElementCount === 0) {
                this.error = "PDF loading timed out, please try opening in a new window";
                this.loading = false;
              } else {
                // Loaded successfully but onload wasn't triggered
                this.loading = false;
              }
            }
          }, 10000);
        }
      }, 500);
    },
    
    reloadPdf() {
      this.setupPdfObject();
    }
  }
}
</script>

<style scoped>
.pdf-viewer-container {
  width: 100%;
  height: 80vh;
  border: 1px solid #ddd;
  border-radius: 4px;
  overflow: hidden;
  background: #f5f5f5;
  display: flex;
  flex-direction: column;
  position: relative;
}

.pdf-object {
  width: 100%;
  height: 100%;
  flex: 1;
}

.pdf-fallback {
  padding: 20px;
  text-align: center;
  background-color: #f8f8f8;
  height: 100%;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
}

.pdf-fallback a {
  color: #3f51b5;
  text-decoration: none;
}

.pdf-fallback a:hover {
  text-decoration: underline;
}

.loading, .error {
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  background: rgba(255, 255, 255, 0.9);
  z-index: 10;
}

.loading-spinner {
  width: 40px;
  height: 40px;
  border: 4px solid #f3f3f3;
  border-top: 4px solid #3f51b5;
  border-radius: 50%;
  animation: spin 1s linear infinite;
  margin-bottom: 10px;
}

@keyframes spin {
  0% { transform: rotate(0deg); }
  100% { transform: rotate(360deg); }
}

.pdf-actions {
  display: flex;
  margin-top: 1rem;
  gap: 1rem;
}

.action-button {
  padding: 0.5rem 1rem;
  border: none;
  border-radius: 4px;
  cursor: pointer;
  font-size: 14px;
  background-color: #f0f0f0;
  color: #333;
  text-decoration: none;
}

.action-button.primary {
  background-color: #3f51b5;
  color: white;
}

.action-button:hover {
  opacity: 0.9;
}
</style> 