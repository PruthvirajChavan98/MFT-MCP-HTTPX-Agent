import { defineConfig, loadEnv } from 'vite'
import path from 'path'
import tailwindcss from '@tailwindcss/vite'
import react from '@vitejs/plugin-react'

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), 'VITE_')
  const apiTarget = env.VITE_API_PROXY_TARGET || 'http://localhost:8000'

  return {
    plugins: [react(), tailwindcss()],
    resolve: {
      alias: {
        '@': path.resolve(__dirname, './src'),
      },
    },
    assetsInclude: ['**/*.svg', '**/*.csv'],
    build: {
      rollupOptions: {
        output: {
          manualChunks: {
            'router-vendor': ['react-router'],
            'react-vendor': ['react', 'react-dom'],
            'query-vendor': ['@tanstack/react-query', '@tanstack/react-query-devtools'],
            'charts-vendor': ['recharts'],
            'mui-vendor': ['@emotion/react', '@emotion/styled', '@mui/icons-material', '@mui/material'],
            'admin-vendor': ['react-dnd', 'react-dnd-html5-backend', 'react-resizable-panels'],
            'radix-vendor': [
              '@radix-ui/react-accordion',
              '@radix-ui/react-alert-dialog',
              '@radix-ui/react-aspect-ratio',
              '@radix-ui/react-avatar',
              '@radix-ui/react-checkbox',
              '@radix-ui/react-collapsible',
              '@radix-ui/react-context-menu',
              '@radix-ui/react-dialog',
              '@radix-ui/react-dropdown-menu',
              '@radix-ui/react-hover-card',
              '@radix-ui/react-label',
              '@radix-ui/react-menubar',
              '@radix-ui/react-navigation-menu',
              '@radix-ui/react-popover',
              '@radix-ui/react-progress',
              '@radix-ui/react-radio-group',
              '@radix-ui/react-scroll-area',
              '@radix-ui/react-select',
              '@radix-ui/react-separator',
              '@radix-ui/react-slider',
              '@radix-ui/react-slot',
              '@radix-ui/react-switch',
              '@radix-ui/react-tabs',
              '@radix-ui/react-toggle',
              '@radix-ui/react-toggle-group',
              '@radix-ui/react-tooltip',
            ],
          },
        },
      },
    },
    server: {
      allowedHosts: ['mft-agent.pruthvirajchavan.codes'],
      proxy: {
        '/api': {
          target: apiTarget,
          changeOrigin: true,
          secure: false,
          rewrite: (p) => p.replace(/^\/api/, ''),
        },
      },
    },
  }
})
