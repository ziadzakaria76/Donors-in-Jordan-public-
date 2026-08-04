# Doc2MD

Convert PDF, Word and Excel files into clean, token-efficient Markdown for
feeding to an LLM. Mobile-first, installable, and **entirely client-side** —
no backend, no upload, no analytics. Files never leave the device.

> **Status: phase 3 of 6.** The app shell, the spreadsheet pipeline
> (XLSX / XLSM / CSV) and the DOCX pipeline are built and tested. PDF is a stub
> that reports which phase implements it. See [Build status](#build-status).

## Quick start

```bash
cd doc2md
npm install
npm run dev      # http://localhost:5173
```

```bash
npm run build    # typecheck + production build into dist/
npm run preview  # serve dist/ (add --host to reach it from your phone)
npm test         # unit tests
```

`npm run build` is the quality gate: it regenerates the icons, typechecks the
app *and* the service worker with zero errors, then builds.

## Architecture

Everything runs in the browser tab. There is no server component, so the whole
thing deploys as static files.

```
src/
  main.ts                   entry: mounts the app, registers the SW
  sw.ts                     service worker: precache + Android share target
  core/
    types.ts                the contract every converter implements
    registry.ts             file-type dispatch, size/type validation
    gfm-table.ts            grid → GFM table, shared by every converter
    postprocess.ts          shared token-efficiency pass + front-matter
    share-target.ts         redeems files handed over by the Android share sheet
    share-target-constants.ts   shared between page and worker
  converters/
    spreadsheet.ts          XLSX / XLSM → SheetJS
    delimited.ts            CSV — an RFC 4180 reader, no spreadsheet engine
    docx.ts                 DOCX → mammoth → turndown
    pdf.ts                  PDF  → pdf.js with layout reconstruction
  ui/
    app.ts                  the whole UI (vanilla TS, no framework)
    markdown.ts             small GFM-subset renderer for the preview pane
```

**Lazy loading.** Each converter — and the parsing library behind it — is a
dynamic import, pulled in the first time you open a file of that type. Opening
a spreadsheet never downloads pdf.js. `npm run check:size` enforces the budget:

```
    1.6 KB  index.html
   31.6 KB  assets/index-*.css
   22.4 KB  assets/index-*.js
   55.6 KB  TOTAL (budget 300.0 KB)
```

**Vanilla TypeScript, not React.** The UI is one screen with a list on it.
A framework would have cost more than the ~600 lines it would have saved.

## Install on Android

1. Open the deployed URL in Chrome.
2. Menu (⋮) → **Add to Home screen** → Install.
3. Launch it from the home screen — it opens standalone, without browser
   chrome, and works with no connection after the first load.

Once installed, Doc2MD appears in the Android **share sheet**. From Files,
Drive, Gmail or anywhere else: **Share → Doc2MD**, and the file lands in the
queue ready to convert. This only works for the installed app, not a browser
tab, and only over HTTPS (or `localhost`).

Under the hood the share sheet POSTs the file to `/share-target`. There is no
server behind that URL — the service worker intercepts the POST, stashes the
bytes in the Cache API and redirects back into the app with a one-shot claim
ticket, which the page redeems and then deletes.

## Deploy

The build output in `dist/` is plain static files. **A PWA needs HTTPS** for
the service worker, installability and the share target; every option below
provides it.

### Cloudflare Pages (recommended)

Dashboard → **Workers & Pages** → **Create** → **Pages** → connect this repo,
then set:

| Setting | Value |
| --- | --- |
| Framework preset | None |
| Build command | `npm run build` |
| Build output directory | `dist` |
| Root directory | `doc2md` |
| Node version | `22` (env var `NODE_VERSION=22`) |

Nothing else is required — the site is served from the domain root, so the
default `base` of `/` is correct. Push to the production branch to redeploy.

Or from the CLI:

```bash
npm run build
npx wrangler pages deploy dist --project-name doc2md
```

### Vercel

Root directory `doc2md`, framework preset **Vite**, build command
`npm run build`, output directory `dist`. No other configuration.

### GitHub Pages

A project Pages site is served from `/<repo>/`, not the domain root, so the
asset base, manifest scope and share-target action all need that prefix. The
build reads it from `VITE_BASE`:

```bash
VITE_BASE=/Donors-in-Jordan-public-/ npm run build
```

The workflow at `.github/workflows/doc2md-pages.yml` does this for you. It is
**manual only** — publishing is a deliberate act, not a side effect of a merge:

1. Repo **Settings → Pages → Source: GitHub Actions** (one-time).
2. **Actions → doc2md-pages → Run workflow**.

## Spreadsheets

What the XLSX/CSV converter does beyond dumping cells:

- **Finds the real header row.** Files open with a title, a date stamp and a
  spacer row before the header. Taking row 1 on faith gives you a table headed
  "Q3 Budget Review". The header is scored on fill, how much it reads like
  labels rather than data, distinctness, and whether well-filled rows follow.
  Everything above it is kept, in order, as text ahead of the table.
- **Formula results, not formulas.** `=B2*C2` becomes `37.5`. Error cells show
  as `#DIV/0!` rather than silently blank — the author can see it is wrong and
  so should the reader.
- **Formats as displayed.** A date is `2026-01-15`, not serial `46037`; a
  percentage is `12.5%`, not `0.125`.
- **Merged cells are repeated** down their range, so every data row is
  self-describing instead of trailing off into blanks.
- **Trims fully-empty rows and columns**, but keeps leading indentation inside
  a cell — in a spreadsheet that indentation is often the outline nesting.
- **Truncates past 500 rows** to the first 100 plus
  `<!-- truncated: N rows total -->`, unless the *Full export* toggle is on.
- **CSV is parsed directly**, not through SheetJS: for a delimited file the
  text *is* the displayed value, so `007` stays `007` and `1.250,00` is not
  reinterpreted. The delimiter (`,` `;` tab `|`) is sniffed, and BOMs, quoted
  fields, doubled quotes and embedded newlines are handled.
- **Arabic and other RTL text** passes through in logical order, untouched.
  Rendered cells carry `dir="auto"` so the preview isolates each one; the
  raw-source view uses `unicode-bidi: plaintext`. A raw line that mixes an
  Arabic run with Latin text and digits can still *look* reordered — that is
  the browser's bidi layout of a plain-text line, not the data. The rendered
  preview shows the true column order.

## Word documents

DOCX goes through mammoth to semantic HTML, then turndown to Markdown. What is
worth knowing:

- **Headings come from Word styles, never font size.** A 14pt bold paragraph is
  not a heading, and a document whose Heading 3 is styled smaller than its body
  text still has a Heading 3 in it. Beyond mammoth's defaults the map covers
  Title, Quote / Intense Quote / Block Text, and inline code styles.
- **Images are never embedded.** The image bytes are not even read — reading
  them is what produces a base64 data URI, and a 2 MB screenshot inlined into
  Markdown is the exact thing this tool exists to avoid. Each becomes
  `![image: image-1.png]`, with a `## Images` footer listing name, MIME type
  and alt text.
- **Footnotes** become inline `[^1]` markers with `[^1]: …` definitions at the
  end. The "↑" back-links are navigation, not content, and are dropped.
- **Tables** are rendered by the same code as spreadsheets, so both look alike
  downstream. `colspan` and `rowspan` are expanded into a plain grid with the
  merged value repeated across every cell it covers — GFM has no notion of a
  span, and a row trailing off into blanks is worse than one that repeats a
  label. This replaces turndown-plugin-gfm's table support, which cannot do it.
- **Lists** keep their nesting, at `- item` and two-space indents rather than
  turndown's `-   item` and four. Same structure, fewer tokens on every line.
- **Headers and footers** stay out of the body, so "Confidential draft" does
  not appear once per page.
- Document order is never changed; the images footer is the only thing appended.

## Testing

```bash
npm test         # unit tests (vitest)
npm run smoke    # end-to-end browser check against a built app
```

The smoke test drives a real Chromium at a Pixel-sized viewport and asserts the
things that only break on a device: every control clears the 48px touch target,
the page never scrolls horizontally, the service worker installs, the shell
still loads with the network cut, and the Android share-target POST
round-trips through the worker into the queue.

```bash
npm run build
npx vite preview --port 4173 &
npm run smoke
```

## Build status

| Phase | Scope | State |
| --- | --- | --- |
| 1 | Scaffold, PWA, share target, UI shell, batch queue, zip export | **done** |
| 2 | XLSX / XLSM / CSV pipeline | **done** |
| 3 | DOCX pipeline (style mapping + turndown) | **done** |
| 4 | PDF pipeline (layout reconstruction) | stub |
| 5 | Token-efficiency post-processor + YAML front-matter | passthrough |
| 6 | Share-target polish, offline caching, UI polish | partly done |
| 7 | Fixture-based snapshot tests per format | pending |

Until a converter is built, opening a file of that type produces a per-file
error naming the phase — the batch keeps running and other files still convert.

## Notes

- **`xlsx` version.** SheetJS stopped publishing to npm at 0.18.5 and moved to
  its own CDN, which this environment cannot reach, so the pinned version
  carries two open advisories. The prototype-pollution one is reachable through
  `sheet_to_json`, which builds objects keyed by cell values; the converter
  never calls it, walking the cell grid directly instead (it needs the exact
  origin for merge alignment anyway). If you can reach `cdn.sheetjs.com`,
  installing `xlsx` from there is still strictly better.
- **No runtime network calls.** The service worker precaches everything at
  install; after that the app makes no requests at all. There is no telemetry
  and no login.
