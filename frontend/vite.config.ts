import { defineConfig } from 'vite';
import vue from '@vitejs/plugin-vue';
import basicSsl from '@vitejs/plugin-basic-ssl';
import path from 'node:path';

export default defineConfig({
  plugins: [vue(), basicSsl()],
  resolve: {
    alias: {
      '@avatar-sdk': path.resolve(__dirname, 'src/libs/avatar-sdk-web_3.2.3.1002/esm/index.js'),
    },
  },
  optimizeDeps: {
    exclude: ['@avatar-sdk'],
  },
  server: {
    port: 5173,
    host: '0.0.0.0',
    https: true,
    proxy: {
      '/api': { target: 'http://localhost:8000', changeOrigin: true, ws: true },
      // 视频需透传 Range，否则会出现能出首帧但点播放无响应
      '/static': {
        target: 'http://localhost:8000',
        changeOrigin: true,
        configure: (proxy) => {
          proxy.on('proxyReq', (proxyReq, req) => {
            const range = req.headers.range;
            if (range) proxyReq.setHeader('Range', range);
          });
        },
      },
    },
  },
});
