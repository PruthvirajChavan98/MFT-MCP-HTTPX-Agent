// vite.config.ts
import { defineConfig } from 'vite';
import solidPlugin from 'vite-plugin-solid';
import tailwindcss from '@tailwindcss/vite';

export default defineConfig({
  plugins: [tailwindcss(), solidPlugin()],
  server: {
    port: 3000,
    host: '0.0.0.0',
    proxy: {
      '/agent': {
        target: 'https://agent.pruthvirajchavan.codes',
        changeOrigin: true,
        secure: true,
      },
      '/graphql': {
        target: 'https://agent.pruthvirajchavan.codes',
        changeOrigin: true,
        secure: true,
      },
      // ✅ NEW
      '/eval': {
        target: 'https://agent.pruthvirajchavan.codes',
        changeOrigin: true,
        secure: true,
      },
    },
  },
  build: {
    target: 'esnext',
  },
});
