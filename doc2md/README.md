# Doc2MD

Convert PDF, Word and Excel files into clean, token-efficient Markdown for
feeding to an LLM. Mobile-first, installable, and **entirely client-side** —
no backend, no upload, no analytics. Files never leave the device.

> **Status: complete.** All six phases are built and tested — three converters,
> the shared output pass, and the PWA around them. See
> [Build status](#build-status).

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
    postprocess.ts          shared token-efficiency pass + front matter
    share-target.ts         redeems files handed over by the Android share sheet
    share-target-constants.ts   shared between page and worker
  converters/
    spreadsheet.ts          XLSX / XLSM → SheetJS
    delimited.ts            CSV — an RFC 4180 reader, no spreadsheet engine
    docx.ts                 DOCX → mammoth → turndown
    pdf.ts                  PDF  → pdf.js driver
    pdf-layout.ts           lines, headings, paragraphs, tables, furniture
  ui/
    app.ts                  the whole UI (vanilla TS, no framework)
    markdown.ts             small GFM-subset renderer for the preview pane
```

**Lazy loading.** Each converter — and the parsing library behind it — is a
dynamic import, pulled in the first time you open a file of that type. Opening
a spreadsheet never downloads pdf.js. `npm run check:size` enforces the budget:

```
    1.6 KB  index.html
   32.9 KB  assets/index-*.css
   27.4 KB  assets/index-*.js
   61.9 KB  TOTAL (budget 300.0 KB)
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

## PDFs

A PDF has no paragraphs, headings or tables — only glyphs at coordinates.
Everything structural is inferred, in `pdf-layout.ts`, which is kept free of
pdf.js so the geometry can be tested on its own.

- **Lines** are runs sharing a baseline. A column gap arrives from pdf.js as a
  single space whose *width* spans the gap, so the width is what separates a
  table row from a sentence — not the character.
- **Headings** come from font size *ranked*, not from fixed ratios. Distinct
  sizes above the body are sorted and become h1, h2, h3 in turn, so a document
  with 13/12/11pt headings over 10pt body gets a clean hierarchy instead of
  three h3s. Running heads are excluded when working out what the body size is,
  or 8pt furniture on every page can outvote the actual text.
- **Paragraphs** rejoin wrapped lines. A line continues the one above it when
  the leading is normal, it starts at or left of it, and the line above either
  reached the right margin or did not finish its sentence. A line that both
  stops short *and* ends a sentence is one the author meant to end. A first-line
  indent starts a new paragraph.
- **Tables** need three rows, two columns, consistent segment counts and every
  segment landing in a distinct column. Anything less stays plain text — losing
  a table's formatting is recoverable, inventing one is not.
- **Running heads and feet** go when their shape — digits normalised, so
  "Page 3 of 10" matches "Page 7 of 10" — repeats in the top or bottom margin of
  at least 60% of pages. Bare page numbers go regardless.
- **Pages with no text layer** become
  `<!-- page N: no text layer, OCR needed -->` and a warning. A scan is exactly
  the case where silently dropping a page would go unnoticed.
- **Arabic and other RTL text** comes out in logical order. A PDF stores an RTL
  run in visual order; pdf.js reverses each run back to logical on extraction,
  and the line assembler orders the runs right-to-left to match. No string is
  ever reversed.

**Offline note.** pdf.js's worker is a 2 MB `.mjs`, so the service worker
precaches about 3.5 MB in total. That download happens in the background after
the page is already interactive, and it is what makes every format convert with
no connection — the smoke test converts a PDF with the network cut.

## The shared output pass

Every converter's Markdown goes through the same last step before you see it.

**Token efficiency.** At most one blank line anywhere; trailing whitespace
gone; empty headings and all-empty table rows dropped; smart quotes, en and em
dashes, ellipses and exotic spaces folded to ASCII. Fenced code blocks are left
exactly as they are — their whitespace and punctuation are content — and inline
code spans keep their punctuation too, so a `--flag` survives.

**Invisible characters** are stripped: zero-width space, soft hyphen, stray
BOMs, and C0/C1 controls other than newline and tab. Two zero-width characters
are deliberately kept: **U+200C** and **U+200D**, the non-joiner and joiner.
They are invisible, but they change how Arabic, Persian and many Indic scripts
render and in some words what they say, so stripping every zero-width character
alike would quietly corrupt them.

**Front matter** is prepended as YAML:

```yaml
---
source: donor-review.pdf
type: pdf
pages: 3
converted: 2026-08-05
words: 116
---
```

`sheets: [Orders, المانحون]` replaces `pages` for a workbook, and `images: 2`
appears when a document had any. Values are quoted only when YAML would
otherwise misread them — decided by a denylist of the characters YAML treats as
syntax rather than an allowlist of safe ones, because an allowlist has to
enumerate every script a sheet name might use and quietly quotes Arabic when it
does not.

**Token count.** The card shows a live `~N tokens` estimate at chars ÷ 4.

## Working with a batch

- **Every file is independent.** One that fails shows why on its own card and
  the rest keep converting. A file we could never read (`.doc`, `.xls`) says
  what to do about it instead of offering a pointless retry.
- **Conversions can be stopped.** A 50 MB PDF on a phone is a long wait with no
  way out otherwise; the queued files behind it carry on afterwards.
- **The truncation warning is actionable.** It used to name a toggle at the top
  of the page and leave you to find it — a long scroll on a phone with several
  files queued. Now the warning carries a *Convert this in full* button that
  ticks the toggle and re-runs the files it would change.
- **Batch progress** shows position and filename while several files are in
  flight. Screen readers are told only about completions: progress fires
  several times a second and announcing each tick makes the page unusable.

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
| 4 | PDF pipeline (layout reconstruction) | **done** |
| 5 | Token-efficiency post-processor + YAML front-matter | **done** |
| 6 | Cancellation, batch progress, actionable warnings, quality gates | **done** |
| 7 | Fixture-based snapshot tests per format | **done** |

Each converter has fixtures built in code and a Markdown snapshot: three
workbooks plus two CSVs, three Word documents, four PDFs. Between them they
cover headings, nested lists, tables with merged cells, and Arabic.

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
