import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// Dev: Vite on :5173 proxies /api to Flask on :5050 (same-origin, so cookies just work).
export default defineConfig({
  plugins: [react()],
  // changeOrigin: false keeps Host = localhost:5173 so the API's same-origin check passes
  // (Vite's string shorthand would rewrite it to :5050 and every write would get "Bad origin").
  server: { proxy: { '/api': { target: 'http://localhost:5050', changeOrigin: false } } },
})
