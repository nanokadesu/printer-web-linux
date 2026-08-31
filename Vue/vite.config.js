import { defineConfig, loadEnv } from 'vite'
import vue from '@vitejs/plugin-vue'

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), '')
  const backendPort = env.VITE_API_PORT || '5181'
  const frontendPort = Number(env.VITE_FRONTEND_PORT || 5173)
  return {
    base: '/',
    plugins: [vue()],
    server: {
      host: '0.0.0.0',
      port: frontendPort,
      strictPort: true,
      // Vite reflects the requesting Origin. Flask independently validates
      // the configured ip_list for direct backend requests.
      cors: { origin: true },
      proxy: { '/api': { target: `http://127.0.0.1:${backendPort}`, changeOrigin: true } },
    },
  }
})
