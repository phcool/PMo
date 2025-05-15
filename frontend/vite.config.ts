import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import path from 'path'

// 定义环境变量，以处理不同的部署路径
const BASE_URL = process.env.BASE_URL || '/'

// https://vitejs.dev/config/
export default defineConfig({
  plugins: [vue()],
  base: BASE_URL, // 使用环境变量设置基础路径
  resolve: {
    alias: {
      '@': path.resolve(__dirname, 'src')
    }
  },
  server: {
    proxy: {
      '/api': {
        target: 'http://localhost:8000',
        changeOrigin: true
      }
    }
  },
  build: {
    outDir: 'dist',
    assetsDir: 'assets',
    // 确保生成的资产使用绝对路径
    assetsInlineLimit: 4096,
    cssCodeSplit: true,
    sourcemap: false,
    // 使用更简单的哈希生成方式，使文件更易于后端识别
    rollupOptions: {
      output: {
        manualChunks: {
          'vendor': ['vue', 'vue-router', 'axios'],
          'ui': ['marked', 'dompurify', 'vue-toastification']
        },
        // 使用更可预测的文件名格式
        entryFileNames: 'assets/[name].[hash].js',
        chunkFileNames: 'assets/[name].[hash].js',
        assetFileNames: 'assets/[name].[hash].[ext]'
      }
    }
  }
}) 