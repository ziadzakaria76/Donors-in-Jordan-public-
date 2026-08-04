import { defineConfig } from 'vite';
import tailwindcss from '@tailwindcss/vite';
import { VitePWA } from 'vite-plugin-pwa';

// Deploying under a sub-path (GitHub Pages project sites) needs a matching
// base. Cloudflare Pages / Vercel serve from the root, so default to '/'.
const base = process.env.VITE_BASE ?? '/';

export default defineConfig({
  base,
  build: {
    target: 'es2022',
    // The converters are lazy-loaded; keep the report honest about the
    // initial bundle rather than hiding a 2 MB pdf.js chunk behind a warning.
    chunkSizeWarningLimit: 300,
  },
  worker: { format: 'es' },
  plugins: [
    tailwindcss(),
    VitePWA({
      strategies: 'injectManifest',
      srcDir: 'src',
      filename: 'sw.ts',
      registerType: 'autoUpdate',
      injectRegister: 'auto',
      injectManifest: {
        globPatterns: ['**/*.{js,css,html,svg,png,ico,wasm}'],
        // pdf.js ships a worker well past workbox's 2 MB default.
        maximumFileSizeToCacheInBytes: 8 * 1024 * 1024,
      },
      devOptions: { enabled: true, type: 'module', navigateFallback: 'index.html' },
      manifest: {
        name: 'Doc2MD — file to Markdown',
        short_name: 'Doc2MD',
        description:
          'Convert PDF, DOCX and XLSX files to clean, token-efficient Markdown. Runs entirely on your device.',
        id: base,
        start_url: base,
        scope: base,
        display: 'standalone',
        orientation: 'portrait',
        background_color: '#0b1020',
        theme_color: '#0b1020',
        categories: ['productivity', 'utilities'],
        icons: [
          { src: 'icons/icon-192.png', sizes: '192x192', type: 'image/png', purpose: 'any' },
          { src: 'icons/icon-512.png', sizes: '512x512', type: 'image/png', purpose: 'any' },
          { src: 'icons/maskable-512.png', sizes: '512x512', type: 'image/png', purpose: 'maskable' },
        ],
        // Android "Share → Doc2MD". The POST is intercepted by the service
        // worker; there is no server route behind it.
        share_target: {
          action: `${base}share-target`,
          method: 'POST',
          enctype: 'multipart/form-data',
          params: {
            files: [
              {
                name: 'files',
                accept: [
                  'application/pdf',
                  '.pdf',
                  'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
                  '.docx',
                  'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
                  '.xlsx',
                  'application/vnd.ms-excel.sheet.macroEnabled.12',
                  '.xlsm',
                  'text/csv',
                  '.csv',
                ],
              },
            ],
          },
        },
        file_handlers: [
          {
            action: base,
            accept: {
              'application/pdf': ['.pdf'],
              'application/vnd.openxmlformats-officedocument.wordprocessingml.document': ['.docx'],
              'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet': ['.xlsx'],
              'application/vnd.ms-excel.sheet.macroEnabled.12': ['.xlsm'],
              'text/csv': ['.csv'],
            },
          },
        ],
      },
    }),
  ],
});
