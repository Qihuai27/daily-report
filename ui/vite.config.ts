import { defineConfig, loadEnv } from 'vite'
import react from '@vitejs/plugin-react'

// https://vitejs.dev/config/
export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), '')
  const apiTarget = env.VITE_API_PROXY || 'http://127.0.0.1:8000'

  return {
    plugins: [react()],
    server: {
      port: 3000,
      proxy: {
        '/api': apiTarget
      }
    }
  }
})
