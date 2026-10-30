import path from 'node:path'
import { fileURLToPath } from 'node:url'
import tailwindcss from '@tailwindcss/vite'
import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

const root = path.dirname(fileURLToPath(import.meta.url))

export default defineConfig({
  plugins: [react(), tailwindcss()],
  resolve: {
    alias: {
      '@': path.resolve(root, 'src'),
    },
  },
  server: {
    host: '127.0.0.1',
    port: 5173,
    proxy: {
      '/jobs': 'http://127.0.0.1:8765',
      '/batches': 'http://127.0.0.1:8765',
      '/models': 'http://127.0.0.1:8765',
      '/openrouter-key': 'http://127.0.0.1:8765',
      '/audio': 'http://127.0.0.1:8765',
    },
  },
  preview: {
    host: '127.0.0.1',
    port: 5173,
    proxy: {
      '/jobs': 'http://127.0.0.1:8765',
      '/batches': 'http://127.0.0.1:8765',
      '/models': 'http://127.0.0.1:8765',
      '/openrouter-key': 'http://127.0.0.1:8765',
      '/audio': 'http://127.0.0.1:8765',
    },
  },
})
