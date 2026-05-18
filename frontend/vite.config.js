import { defineConfig, loadEnv } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig(({ mode }) => {
  const rootEnv = loadEnv(mode, '..', 'VITE_')
  const localEnv = loadEnv(mode, '.', 'VITE_')

  return {
    plugins: [react()],
    envDir: '..',
    define: {
      'import.meta.env.VITE_GOOGLE_CLIENT_ID': JSON.stringify(
        localEnv.VITE_GOOGLE_CLIENT_ID || rootEnv.VITE_GOOGLE_CLIENT_ID || ''
      ),
    },
    server: {
      port: 5173,
      proxy: {
        '/api': {
          target: 'http://127.0.0.1:8000',
          changeOrigin: true,
        },
        '/health': {
          target: 'http://127.0.0.1:8000',
          changeOrigin: true,
        },
      },
    },
  }
})
