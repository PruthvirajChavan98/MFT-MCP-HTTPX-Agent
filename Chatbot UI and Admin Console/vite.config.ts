import { defineConfig, loadEnv } from 'vite'
import path from 'path'
import tailwindcss from '@tailwindcss/vite'
import react from '@vitejs/plugin-react'

function hasVendorPackage(id: string, packages: string[]): boolean {
  const normalizedId = id.replace(/\\/g, '/')
  return packages.some((pkg) => (
    normalizedId.includes(`/node_modules/${pkg}/`) ||
    normalizedId.endsWith(`/node_modules/${pkg}`)
  ))
}

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), 'VITE_')
  const apiTarget = env.VITE_API_PROXY_TARGET || 'http://localhost:8000'
  const crmTarget = env.VITE_CRM_PROXY_TARGET || 'http://localhost:8080'

  return {
    plugins: [react(), tailwindcss()],
    resolve: {
      alias: {
        '@':           path.resolve(__dirname, './src'),
        '@features':   path.resolve(__dirname, './src/features'),
        '@shared':     path.resolve(__dirname, './src/shared'),
        '@components': path.resolve(__dirname, './src/components'),
        '@styles':     path.resolve(__dirname, './src/styles'),
      },
    },
    assetsInclude: ['**/*.svg', '**/*.csv'],
    build: {
      rolldownOptions: {
        output: {
          codeSplitting: {
            groups: [
              {
                name: 'router-vendor',
                priority: 60,
                test: (id) => hasVendorPackage(id, ['react-router']),
              },
              {
                name: 'query-vendor',
                priority: 50,
                test: (id) => hasVendorPackage(id, [
                  '@tanstack/react-query',
                  '@tanstack/react-query-devtools',
                ]),
              },
              {
                name: 'charts-vendor',
                priority: 40,
                test: (id) => hasVendorPackage(id, ['recharts']),
              },
              {
                name: 'mui-vendor',
                priority: 30,
                test: (id) => hasVendorPackage(id, [
                  '@emotion/react',
                  '@emotion/styled',
                  '@mui/icons-material',
                  '@mui/material',
                ]),
              },
              {
                name: 'admin-vendor',
                priority: 20,
                test: (id) => hasVendorPackage(id, ['react-resizable-panels']),
              },
              {
                name: 'radix-vendor',
                priority: 10,
                test: (id) => hasVendorPackage(id, [
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
                ]),
              },
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
        '/crm-api': {
          target: crmTarget,
          changeOrigin: true,
          secure: false,
          rewrite: (p) => p.replace(/^\/crm-api/, ''),
        },
      },
    },
  }
})
