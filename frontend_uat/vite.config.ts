// import { defineConfig } from 'vite'
// import solid from 'vite-plugin-solid'
// import tailwindcss from '@tailwindcss/vite'

// const apiTarget = process.env.VITE_API_PROXY_TARGET ?? 'http://localhost:8000'

// export default defineConfig({
//   plugins: [tailwindcss(), solid()],
//   server: {
//     host: '0.0.0.0',
//     port: 5173,
//     proxy: {
//       '/api': {
//         target: apiTarget,
//         changeOrigin: true,
//         secure: false,
//         rewrite: (path) => path.replace(/^\/api/, ''),
//       },
//     },
//   },
//   preview: {
//     host: '0.0.0.0',
//     port: 5173,
//     proxy: {
//       '/api': {
//         target: apiTarget,
//         changeOrigin: true,
//         secure: false,
//         rewrite: (path) => path.replace(/^\/api/, ''),
//       },
//     },
//   },
// })



import { defineConfig } from 'vite'
import solid from 'vite-plugin-solid'
import tailwindcss from '@tailwindcss/vite'

const apiTarget = process.env.VITE_API_PROXY_TARGET ?? 'http://localhost:8000'

export default defineConfig({
  plugins: [tailwindcss(), solid()],
  server: {
    host: '0.0.0.0',
    port: 5173,
    // Add this line to allow any ngrok URL
    allowedHosts: true,
    proxy: {
      '/api': {
        target: apiTarget,
        changeOrigin: true,
        secure: false,
        rewrite: (path) => path.replace(/^\/api/, ''),
      },
    },
  },
  preview: {
    host: '0.0.0.0',
    port: 5173,
    // Add this here too if you ever run 'npm run preview'
    allowedHosts: true,
    proxy: {
      '/api': {
        target: apiTarget,
        changeOrigin: true,
        secure: false,
        rewrite: (path) => path.replace(/^\/api/, ''),
      },
    },
  },
})
