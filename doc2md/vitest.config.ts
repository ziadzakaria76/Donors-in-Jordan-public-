import { defineConfig } from 'vitest/config';

export default defineConfig({
  // pdf.js's default build needs DOM globals (DOMMatrix and friends) that Node
  // does not have; its legacy build runs in-process on a fake worker. The app
  // still ships the default build — the browser smoke test covers that path.
  resolve: {
    alias: { 'pdfjs-dist': 'pdfjs-dist/legacy/build/pdf.mjs' },
  },
  test: {
    environment: 'node',
    include: ['tests/**/*.test.ts'],
  },
});
