/**
 * Browser smoke test for the built app: verifies the shell renders on a phone
 * viewport, the service worker installs, the app survives going offline, and
 * the Android share-target POST round-trips through the worker.
 *
 *   npm run build
 *   npx vite preview --port 4173 &
 *   node scripts/smoke.mjs
 */
import { chromium } from 'playwright';

const BASE = process.env.BASE ?? 'http://127.0.0.1:4173';
const CHROME = process.env.CHROME ?? '/opt/pw-browsers/chromium-1194/chrome-linux/chrome';

const browser = await chromium.launch({ executablePath: CHROME });
const context = await browser.newContext({
  viewport: { width: 412, height: 915 },
  deviceScaleFactor: 2,
  isMobile: true,
  hasTouch: true,
  userAgent:
    'Mozilla/5.0 (Linux; Android 14; Pixel 8) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130 Mobile Safari/537.36',
});
const page = await context.newPage();
const errors = [];
page.on('pageerror', (e) => errors.push(`pageerror: ${e.message}`));
page.on('console', (m) => {
  if (m.type() === 'error') errors.push(`console: ${m.text()}`);
});

const check = (label, actual, expected) => {
  const ok = JSON.stringify(actual) === JSON.stringify(expected);
  console.log(`${ok ? 'PASS' : 'FAIL'}  ${label}: ${JSON.stringify(actual)}`);
  if (!ok) process.exitCode = 1;
};

await page.goto(BASE, { waitUntil: 'networkidle' });

check('title', await page.title(), 'Doc2MD — file to Markdown');
check('dark by default', await page.evaluate(() => document.documentElement.classList.contains('dark')), true);
check('manifest linked', await page.evaluate(() => !!document.querySelector('link[rel=manifest]')), true);

// --- file intake -----------------------------------------------------------
await page.setInputFiles('#file-input', [
  {
    name: 'budget.xlsx',
    mimeType: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
    buffer: Buffer.from('PK fake'),
  },
  { name: 'legacy.doc', mimeType: 'application/msword', buffer: Buffer.from('legacy') },
]);
await page.waitForTimeout(600);
check('two cards queued', await page.locator('[data-item]').count(), 2);
check(
  'legacy .doc explained, no retry offered',
  await page.locator('[data-item]:has-text("legacy.doc") [data-action="retry"]').count(),
  0,
);

// --- touch targets ---------------------------------------------------------
const small = await page.evaluate(() =>
  [...document.querySelectorAll('button, label.tappable')]
    .map((el) => ({
      t: el.textContent.trim().slice(0, 20),
      h: Math.round(el.getBoundingClientRect().height),
    }))
    .filter((x) => x.h > 0 && x.h < 48),
);
check('controls under 48px', small, []);

// --- theme toggle ----------------------------------------------------------
await page.click('[data-action="theme"]');
check(
  'toggles to light',
  await page.evaluate(() => document.documentElement.classList.contains('dark')),
  false,
);
await page.click('[data-action="theme"]');

// --- layout ----------------------------------------------------------------
check(
  'no horizontal overflow',
  await page.evaluate(
    () => document.documentElement.scrollWidth <= document.documentElement.clientWidth,
  ),
  true,
);

// --- service worker + offline ---------------------------------------------
await page.evaluate(() => navigator.serviceWorker.ready);
check(
  'service worker active',
  await page.evaluate(async () => !!(await navigator.serviceWorker.getRegistration())?.active),
  true,
);

await page.screenshot({ path: process.env.SHOT ?? '/tmp/doc2md-phase1.png', fullPage: true });

await context.setOffline(true);
await page.reload({ waitUntil: 'domcontentloaded' });
await page.waitForTimeout(400);
check('shell loads offline', await page.locator('h1').innerText(), 'Doc2MD');
check(
  'styles cached offline',
  await page.evaluate(() => getComputedStyle(document.body).backgroundColor),
  'rgb(11, 16, 32)',
);
await context.setOffline(false);

// --- Android share target --------------------------------------------------
// Reproduces what the share sheet does: a multipart POST to /share-target,
// which the worker must stash and redirect back into the app.
await page.evaluate(() => {
  const form = document.createElement('form');
  form.method = 'POST';
  form.action = 'share-target';
  form.enctype = 'multipart/form-data';
  form.id = 'share-probe';
  const input = document.createElement('input');
  input.type = 'file';
  input.name = 'files';
  input.id = 'share-probe-input';
  form.append(input);
  document.body.append(form);
});
await page.setInputFiles('#share-probe-input', {
  name: 'shared-report.csv',
  mimeType: 'text/csv',
  buffer: Buffer.from('a,b\n1,2\n'),
});
await Promise.all([
  page.waitForNavigation({ waitUntil: 'networkidle' }),
  page.evaluate(() => document.getElementById('share-probe').submit()),
]);
await page.waitForTimeout(600);
check(
  'shared file lands in the queue',
  await page.locator('[data-item]:has-text("shared-report.csv")').count(),
  1,
);
check('claim ticket stripped from the URL', new URL(page.url()).search, '');

console.log(
  errors.length ? `FAIL  console errors: ${errors.join(' | ')}` : 'PASS  no console errors',
);
if (errors.length) process.exitCode = 1;

await browser.close();
