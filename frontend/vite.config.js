import { fileURLToPath, URL } from 'node:url'

import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import vueDevTools from 'vite-plugin-vue-devtools'

// https://vite.dev/config/
export default defineConfig({
  // Preserve module worker URLs in DICOM loader during development.
  optimizeDeps: { exclude: ['@cornerstonejs/dicom-image-loader'], include: [
    'dicom-parser', 'jpeg-lossless-decoder-js',
    '@cornerstonejs/codec-libjpeg-turbo-8bit/decodewasmjs',
    '@cornerstonejs/codec-openjpeg/decodewasmjs',
    '@cornerstonejs/codec-openjph/wasmjs',
    '@cornerstonejs/codec-charls/decodewasmjs',
  ] },
  worker: { format: 'es' },
  assetsInclude: ['**/*.wasm'],
  plugins: [
    vue(),
    vueDevTools(),
  ],
  resolve: {
    alias: {
      // vtk.js XML reader uses EventEmitter; Vite does not polyfill Node builtins.
      events: fileURLToPath(new URL('./node_modules/events/events.js', import.meta.url)),
      '@': fileURLToPath(new URL('./src', import.meta.url)),
    },
  },
})
