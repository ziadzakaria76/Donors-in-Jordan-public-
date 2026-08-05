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

// The README claims the app makes no external network calls at runtime. Record
// every request so that claim is checked rather than asserted.
const foreignRequests = [];
const origin = new URL(BASE).origin;
page.on('request', (request) => {
  const url = request.url();
  if (!url.startsWith(origin) && !url.startsWith('data:') && !url.startsWith('blob:')) {
    foreignRequests.push(url);
  }
});

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

// --- a real conversion, end to end -----------------------------------------
/**
 * The app opens the output automatically when a file is the only one in the
 * queue, so clicking unconditionally would close it again.
 */
const openOutput = async (card) => {
  const toggle = card.locator('[data-action="toggle-open"]');
  await toggle.waitFor({ timeout: 15_000 });
  if ((await toggle.innerText()).trim() === 'Show output') await toggle.click();
};

// The share-target file above is a CSV, so it has already converted by now.
const shared = page.locator('[data-item]:has-text("shared-report.csv")');
await openOutput(shared);
check(
  'CSV converted and previews as a real table',
  await shared.locator('.md-preview table td').count(),
  2,
);
check(
  'token estimate shown',
  /~\d+ tokens/.test(await shared.innerText()),
  true,
);

// A real workbook exercises the lazy SheetJS chunk, merges and truncation.
const XLSX = await import('xlsx');
const sheet = XLSX.utils.aoa_to_sheet([
  ['Annual Report 2026', null, null],
  [null, null, null],
  ['Donor', 'Sector', 'Value'],
  ['World Bank', 'Water', 250000],
  ['البنك الإسلامي', 'التعليم', 130000],
]);
sheet['!merges'] = [{ s: { r: 3, c: 0 }, e: { r: 4, c: 0 } }];
const workbook = XLSX.utils.book_new();
XLSX.utils.book_append_sheet(workbook, sheet, 'Donors');

await page.setInputFiles('#file-input', {
  name: 'donors.xlsx',
  mimeType: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
  buffer: Buffer.from(XLSX.write(workbook, { type: 'buffer', bookType: 'xlsx' })),
});
const workbookCard = page.locator('[data-item]:has-text("donors.xlsx")');
await openOutput(workbookCard);

check(
  'workbook converted, header row found under the title',
  (await workbookCard.locator('.md-preview th').allInnerTexts()).join(','),
  'Donor,Sector,Value',
);
// The mixed LTR/RTL row is where a converter most easily scrambles columns.
// Assert the whole row in order, not just that the Arabic is present somewhere.
check(
  'RTL row keeps its column order',
  await workbookCard
    .locator('.md-preview tbody tr')
    .nth(1)
    .locator('td')
    .allInnerTexts(),
  ['World Bank', 'التعليم', '130000'],
);
check(
  'rendered cells are bidi-isolated',
  await workbookCard.locator('.md-preview td[dir="auto"]').count(),
  6,
);
await workbookCard.locator('[data-action="view-raw"]').click();
const raw = await workbookCard.locator('pre').innerText();
check('raw view shows a GFM table', raw.includes('| Donor | Sector | Value |'), true);
check('title kept above the table', raw.includes('Annual Report 2026'), true);
check('merged cell repeated down its range', raw.split('World Bank').length - 1, 2);

// A .docx exercises mammoth's *browser* build. The unit tests run its Node
// entry point, so this is the only place the shipped unzip path is proven.
const {
  Document,
  HeadingLevel,
  Packer,
  Paragraph,
  Table,
  TableCell,
  TableRow,
  TextRun,
} = await import('docx');
const doc = new Document({
  sections: [
    {
      children: [
        new Paragraph({ text: 'Field Report', heading: HeadingLevel.HEADING_1 }),
        new Paragraph({
          children: [new TextRun('Signed off by the '), new TextRun({ text: 'ministry', bold: true })],
        }),
        new Table({
          rows: [
            new TableRow({
              children: [
                new TableCell({ children: [new Paragraph('Site')] }),
                new TableCell({ children: [new Paragraph('Cost')] }),
              ],
            }),
            new TableRow({
              children: [
                new TableCell({ rowSpan: 2, children: [new Paragraph('Irbid')] }),
                new TableCell({ children: [new Paragraph('4000')] }),
              ],
            }),
            new TableRow({
              children: [new TableCell({ children: [new Paragraph('6000')] })],
            }),
          ],
        }),
      ],
    },
  ],
});
await page.setInputFiles('#file-input', {
  name: 'field-report.docx',
  mimeType: 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
  buffer: Buffer.from(await Packer.toBuffer(doc)),
});
const docxCard = page.locator('[data-item]:has-text("field-report.docx")');
await openOutput(docxCard);
await docxCard.locator('[data-action="view-raw"]').click();
const docxRaw = await docxCard.locator('pre').innerText();
check('DOCX heading mapped from its Word style', docxRaw.includes('# Field Report'), true);
check(
  'front matter describes the source document',
  /^---\nsource: field-report\.docx\ntype: docx\nconverted: \d{4}-\d{2}-\d{2}\nwords: \d+\n---\n/.test(docxRaw),
  true,
);
check('DOCX bold preserved', docxRaw.includes('**ministry**'), true);
check(
  'DOCX merged cell repeated',
  docxRaw.includes('| Irbid | 4000 |') && docxRaw.includes('| Irbid | 6000 |'),
  true,
);

/**
 * A two-page PDF: a large-font title, two body lines that wrap, and a second
 * page with no content stream at all. Written inline rather than imported from
 * tests/pdf-writer.ts because this script is plain JavaScript, and the smoke
 * test only needs Helvetica at fixed coordinates.
 */
function buildProbePdf() {
  const pageOne = [
    ['Quarterly Brief', 60, 760, 20],
    ['This is one paragraph that wraps across two lines here and keeps', 60, 720, 10],
    ['going to the margin before it finally stops.', 60, 704, 10],
  ]
    .map(
      ([text, x, y, size]) =>
        `BT /F1 ${size} Tf 1 0 0 1 ${x} ${y} Tm (${text.replace(/([\\()])/g, '\\$1')}) Tj ET`,
    )
    .join('\n');

  const objects = [
    '<< /Type /Catalog /Pages 2 0 R >>',
    '<< /Type /Pages /Kids [3 0 R 5 0 R] /Count 2 >>',
    '<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] /Resources << /Font << /F1 7 0 R >> >> /Contents 4 0 R >>',
    `<< /Length ${Buffer.byteLength(pageOne)} >>\nstream\n${pageOne}\nendstream`,
    '<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] /Resources << /Font << /F1 7 0 R >> >> /Contents 6 0 R >>',
    '<< /Length 0 >>\nstream\n\nendstream',
    '<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica /Encoding /WinAnsiEncoding >>',
  ];

  let out = '%PDF-1.7\n';
  const offsets = [];
  objects.forEach((body, i) => {
    offsets.push(Buffer.byteLength(out));
    out += `${i + 1} 0 obj\n${body}\nendobj\n`;
  });
  const xref = Buffer.byteLength(out);
  out += `xref\n0 ${objects.length + 1}\n0000000000 65535 f \n`;
  for (const offset of offsets) out += `${String(offset).padStart(10, '0')} 00000 n \n`;
  out += `trailer\n<< /Size ${objects.length + 1} /Root 1 0 R >>\nstartxref\n${xref}\n%%EOF\n`;
  return Buffer.from(out, 'latin1');
}

// A PDF exercises pdf.js's *default* build and its real web worker. The unit
// tests run the legacy build in-process, so this is the only place the shipped
// worker path runs at all.
await page.setInputFiles('#file-input', {
  name: 'brief.pdf',
  mimeType: 'application/pdf',
  buffer: Buffer.from(buildProbePdf()),
});
const pdfCard = page.locator('[data-item]:has-text("brief.pdf")');
await openOutput(pdfCard);
await pdfCard.locator('[data-action="view-raw"]').click();
const pdfRaw = await pdfCard.locator('pre').innerText();
check('PDF heading inferred from font size', pdfRaw.includes('# Quarterly Brief'), true);
check('PDF wrapped lines rejoined', pdfRaw.includes('one paragraph that wraps across two lines here'), true);
check('PDF page without text flagged for OCR', pdfRaw.includes('no text layer, OCR needed'), true);
check('front matter records the page count', /\npages: 2\n/.test(pdfRaw), true);
check(
  'front matter renders as a block in the preview, not a rule',
  await pdfCard.locator('.md-preview hr').count(),
  0,
);

// Four finished files should offer the batch zip.
check(
  'batch bar appears with results',
  await page.locator('#batch-bar:not(.hidden)').count(),
  1,
);

await page.screenshot({ path: process.env.SHOT2 ?? '/tmp/doc2md-phase2.png', fullPage: true });

// --- offline conversion ----------------------------------------------------
// The real test of the precache: pdf.js's worker is a 2 MB .mjs, and a glob
// that misses it leaves PDF conversion working right up until the network
// goes away.
await context.setOffline(true);
await page.reload({ waitUntil: 'domcontentloaded' });
await page.waitForTimeout(500);
await page.setInputFiles('#file-input', {
  name: 'offline.pdf',
  mimeType: 'application/pdf',
  buffer: Buffer.from(buildProbePdf()),
});
const offlineCard = page.locator('[data-item]:has-text("offline.pdf")');
await openOutput(offlineCard);
await offlineCard.locator('[data-action="view-raw"]').click();
check(
  'PDF converts with the network cut',
  (await offlineCard.locator('pre').innerText()).includes('# Quarterly Brief'),
  true,
);
await context.setOffline(false);

// --- full export re-converts what it would change ---------------------------
// A truncation warning that names a toggle is only useful if flipping the
// toggle acts on the file the warning is attached to.
const big = XLSX.utils.book_new();
XLSX.utils.book_append_sheet(
  big,
  XLSX.utils.aoa_to_sheet([
    ['Ref', 'Value'],
    ...Array.from({ length: 620 }, (_, i) => [`REF-${i + 1}`, (i + 1) * 10]),
  ]),
  'Notices',
);
await page.setInputFiles('#file-input', {
  name: 'notices.xlsx',
  mimeType: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
  buffer: Buffer.from(XLSX.write(big, { type: 'buffer', bookType: 'xlsx' })),
});
const bigCard = page.locator('[data-item]:has-text("notices.xlsx")');
await openOutput(bigCard);
await bigCard.locator('[data-action="view-raw"]').click();
check(
  'a long sheet is truncated and says so',
  (await bigCard.locator('pre').innerText()).includes('truncated: 620 rows total'),
  true,
);

check(
  'the truncation warning carries its own action',
  await bigCard.locator('[data-action="convert-in-full"]').count(),
  1,
);
await bigCard.locator('[data-action="convert-in-full"]').click();
await page.waitForTimeout(1800);
check(
  'and it ticks the global toggle so later files match',
  await page.locator('[data-action="full-export"]').isChecked(),
  true,
);
await openOutput(bigCard);
await bigCard.locator('[data-action="view-raw"]').click();
const fullText = await bigCard.locator('pre').innerText();
check('turning full export on re-converts the truncated file', fullText.includes('REF-620'), true);
check('and the truncation note is gone', fullText.includes('truncated:'), false);

// --- quality gates ---------------------------------------------------------
// Headless Chrome never fires `beforeinstallprompt`, so installability is
// checked against the criteria Chrome documents rather than by waiting for an
// event that cannot arrive here. Chrome's own manifest parser is still used —
// getAppManifest reports anything it could not read.
const cdp = await page.context().newCDPSession(page);
const appManifest = await cdp.send('Page.getAppManifest');
check("Chrome's manifest parser reports no errors", appManifest.errors, []);

const manifest = await page.evaluate(async () => {
  const link = document.querySelector('link[rel=manifest]');
  return (await fetch(link.href)).json();
});
const iconAtLeast = (size) =>
  (manifest.icons ?? []).some((icon) =>
    String(icon.sizes ?? '')
      .split(/\s+/)
      .some((pair) => Number(pair.split('x')[0]) >= size),
  );
check('manifest names the app', Boolean(manifest.name && manifest.short_name), true);
check('manifest has a 192px and a 512px icon', iconAtLeast(192) && iconAtLeast(512), true);
check('manifest has a start_url', Boolean(manifest.start_url), true);
check(
  'manifest requests a standalone display',
  ['standalone', 'fullscreen', 'minimal-ui'].includes(manifest.display),
  true,
);
check('manifest declares a maskable icon', (manifest.icons ?? []).some((i) => i.purpose === 'maskable'), true);
// The remaining criterion is a service worker with a fetch handler, which the
// offline reload above already proved by serving the shell from cache.

check('no requests to any external origin', foreignRequests, []);

console.log(
  errors.length ? `FAIL  console errors: ${errors.join(' | ')}` : 'PASS  no console errors',
);
if (errors.length) process.exitCode = 1;

await browser.close();
