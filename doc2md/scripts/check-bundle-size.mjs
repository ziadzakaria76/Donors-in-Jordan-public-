#!/usr/bin/env node
/**
 * Guards the "initial bundle under 300 KB" budget.
 *
 * Only what the browser must fetch to show the first screen counts: the HTML,
 * the CSS, and the JS modules reachable from the entry by *static* import. The
 * converters and their parsing libraries are dynamic imports, so they are
 * separate chunks that a visitor never downloads until they open a file of
 * that type — counting them would make the budget meaningless.
 */
import { readFileSync, statSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';

const DIST = join(dirname(fileURLToPath(import.meta.url)), '..', 'dist');
const BUDGET_BYTES = 300 * 1024;

const html = readFileSync(join(DIST, 'index.html'), 'utf8');

// Everything the entry HTML pulls in eagerly: <script src> and <link rel=
// stylesheet|modulepreload>. modulepreload is how Vite declares the static
// import graph of the entry chunk, so it is exactly the set we want.
const assets = new Set();
for (const match of html.matchAll(
  /(?:src|href)="\/?((?:assets\/)[^"]+\.(?:js|css))"/g,
)) {
  assets.add(match[1]);
}

let total = Buffer.byteLength(html);
const rows = [['index.html', total]];
for (const asset of [...assets].sort()) {
  const size = statSync(join(DIST, asset)).size;
  rows.push([asset, size]);
  total += size;
}

const kb = (n) => `${(n / 1024).toFixed(1)} KB`;
for (const [name, size] of rows) console.log(`  ${kb(size).padStart(9)}  ${name}`);
console.log(`  ${kb(total).padStart(9)}  TOTAL (budget ${kb(BUDGET_BYTES)})`);

if (total > BUDGET_BYTES) {
  console.error(
    `\nInitial bundle is ${kb(total)}, over the ${kb(BUDGET_BYTES)} budget. ` +
      `Move something behind a dynamic import.`,
  );
  process.exit(1);
}
