import { defineConfig } from 'vite'

export default defineConfig({
  base: '/',
  server: { proxy: { '/api': 'http://127.0.0.1:8765', '/events': 'http://127.0.0.1:8765' } }
})
