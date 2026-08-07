# Donors in Jordan

Two unrelated projects share this repository. They have no code in common, and
neither one builds, imports or deploys the other — both are documented in full
below.

| Project | What it is | Where it lives |
| --- | --- | --- |
| **General Sherman Housing** | A bilingual (Arabic/English) marketing site for a Jordanian residential developer | the repository root — `index.html`, `assets/`, `tools/` |
| **[Jordan Tender Intelligence Monitor](#jordan-tender-intelligence-monitor)** | A Python system that watches 13 donor and IFI procurement portals for Jordan-related consulting work | [`jordan_tender_monitor/`](jordan_tender_monitor/) |

The site lives at the repository root because the root **is** the site root: it
deploys as-is, with no build step and no subdirectory for a host to point at.
The monitor is self-contained in its own package, is never served, and is the
only thing CI runs.

---

# جنرال شيرمان — General Sherman Housing

A bilingual (Arabic RTL / English LTR) marketing site for a Jordanian residential
developer: project showcases, a live unit inventory with filters, a per-building
availability grid, floor plans, a gallery, and lead capture through WhatsApp,
phone and forms.

Plain HTML, CSS and JavaScript. **No build step, no framework, no runtime
dependencies.** Every file in this folder is the file that gets deployed.

---

## Run it locally

Any static file server works. The site must be served over HTTP — opening
`index.html` from the filesystem will break the fonts and the `fetch`-based
form submission.

```bash
python3 -m http.server 8080      # or: npm start
```

Then open <http://localhost:8080>. Try `?lang=en` on any page to load it in
English.

---

## Deploy it

The site is a folder of static files. The repo root is the site root.

| Host | What to do |
| --- | --- |
| **Netlify** | Drag the repo folder onto the Netlify dashboard, or connect the repo and set **publish directory** `.`, and leave the build command empty. `netlify.toml` already sets caching and the 404 page. |
| **Vercel** | Import the repo, framework preset **Other**, no build command, no root-directory override. `vercel.json` sets the caching headers. |
| **cPanel / any shared host** | Upload the contents of the repo into `public_html/` over FTP. Nothing else to configure. |
| **GitHub Pages** | Serve from the branch root (`/`). Note the caveat below before turning this on. |

**This copy is not the deployed site.** `generalshermanhousing.com` is served
from the `website/` folder on the `claude/real-estate-developer-site-efetxa`
branch, through Cloudflare Pages. The copy here is a root-layout variant and
the two have diverged.

That is why this repository no longer publishes to GitHub Pages: it was putting
a second, competing copy of the same site on the public internet, with a
`CNAME` claiming the live domain. The deploy workflow and the `CNAME` file are
both gone. Turning Pages back on would recreate that conflict — reconcile the
two copies first.

The canonical domain is still `https://generalshermanhousing.com`, and it
appears here in `sitemap.xml`, `robots.txt`, and the `<link rel="canonical">` /
`og:url` / `hreflang` tags in each page's `<head>`. To change it, edit `SITE`
in `tools/build-pages.mjs` and re-run `npm run pages`, then update
`sitemap.xml`, `robots.txt` and `COMPANY.domain` in `assets/js/data.js` to
match.

---

## What to replace before going live

Two things are still unfinished. Neither is false — the invented content has
been removed rather than left in place — so nothing here is published as a
claim the company has not made. Search for `«REPLACE»` in `assets/js/data.js`.

- **Founding year** — `COMPANY.founded` is `null` and no page states a year,
  because the one that was here was invented. Set it and the About page can
  state it.
- **Form endpoint** — `COMPANY.formEndpoint` is empty, so enquiries go to
  WhatsApp with an email fallback. See *Where the form submissions go* below.

The **commercial registration is gone**, not blank: an invented registration
number is a claim about a real company's legal standing, so it was deleted
rather than left for someone to render by accident. Add the real one to
`COMPANY` and write it into the footer deliberately.

- **Company identity** — the name and logo are real, and are no longer marked.
- **Contact details** — the phone, WhatsApp number and email are real. The
  **office address is deliberately blank**: `COMPANY.address` and `mapQuery`
  are empty, so the footer's address line, the contact page's office row and
  the office map are all absent. Filling either field in is not enough on its
  own — the markup was removed too (see *Removed sections*).
- **Domain** — `COMPANY.domain` plus the SEO tags noted above.
- **Projects and units** — see below.
- **Logo** — `assets/img/logo-mark.png` (house mark) and `assets/img/logo.png`
  (full stacked lockup) were extracted from the supplied artwork and keyed to
  transparency. The favicon and iOS tile are generated from the mark by
  `npm run assets`. **Supply the original vector (AI/EPS/SVG) when you have it**
  — these are lifted from a raster screenshot, which is fine on screen at the
  sizes used but will not hold up in print or at very large sizes.

### Where the form submissions go

Out of the box there is no backend: submitting a form opens WhatsApp with the
enquiry pre-written, and offers an email fallback. To collect submissions
server-side instead, paste a form endpoint into `COMPANY.formEndpoint` in
`assets/js/data.js`:

```js
formEndpoint: "https://formspree.io/f/xxxxxxx",   // or Web3Forms, Basin, …
```

Every form then POSTs there, with the WhatsApp/email path kept as the fallback
if the request fails. A hidden `_gotcha` honeypot field is already included and
is respected by those services.

---

## Editing the content

`assets/js/data.js` is the only file you need for content changes. Every piece
of text is a `{ ar, en }` pair.

### Projects and units

Each project carries its own schedule of units, stated one by one, exactly as
the sales brochure publishes them:

```js
units: [
  { code: "1", floor: 0, floorLabel: { ar: "الطابق الأرضي", en: "Ground floor" },
    orientation: "west", area: 154, outdoor: 50, beds: 3, baths: 3,
    type: "apartment", plan: "plan-b", price: 105000, status: "available" },
  { code: "2", floor: 0, …, status: "sold" },     // sold units carry no price
]
```

**Prices are stated, not calculated.** An earlier version derived them from a
rate per m² and a per-floor premium, which real schedules do not follow: in
General Sherman 2 the same 152 m² layout is 88,000 on the first floor and
88,000 again on the third, while a 190 m² lower-ground unit is 117,000. A unit
with no `price` is treated as unavailable and shows its status instead of a
figure — the brochure does not publish prices for sold units, so neither does
the site.

- **A unit sold?** Set its `status` to `"sold"` and drop its `price`.
- **Price change?** Edit that unit's `price`.
- **New project?** Copy a project object. `units: []` is fine — a project with
  no schedule still gets a page, showing its description and gallery without an
  availability grid, unit list or floor plans.

`floor` is a number used for sorting and filtering (`-1` for a lower ground
floor, `0` for ground); `floorLabel` is what the page displays.

### Interface text

UI strings live in `assets/js/i18n.js` as `{ ar, en }` pairs keyed by
`data-i18n` attributes. The Arabic is written into the HTML as well — so it is
what search engines and no-JS visitors see — and repeated in `i18n.js` so that
switching back from English restores it. **If you change a string in the HTML,
change its twin in `i18n.js`.**

---

## Removed sections

Six things were cut rather than filled, because they were invented or do not
exist: the **stats band**, the **testimonials**, the About page's **company
story**, the **office address**, the **social links**, and the **payment
plans**. No page claims a track record, a founding year, a location beyond
Amman, an account the company does not have, or terms on which it will sell.

The payment plans went furthest and were removed most thoroughly. The whole
`payment-plans.html` page, its instalment calculator and `assets/js/plans.js`
are gone, along with the `PAYMENT_PLANS` data, the per-project plans section,
the navigation entry on every page, the sitemap entry, and the home page's
"from 10% down, with interest-free instalments" band. Nothing states a
discount, an instalment count or an interest rate. Restoring it means writing
the real terms first — the page was not left behind as a shell to fill in,
because a half-restored financing page is the failure mode that matters here.

The site is built to tolerate absent data generally — a project with no unit
schedule, a unit with no price, a scheme with no map — so sections remove
themselves rather than rendering empty.

The About page runs hero → four commitments → process → CTA. To add a story
section back, write it into `i18n.js` and add a `split split--wide` section to
`about.html`; the four commitments section is the nearest pattern to copy.

### Restoring the social links

`COMPANY.social` is empty and the footer's icon row is gone, because the company
has no accounts yet. To bring it back, add entries and restore the markup in the
footer of `index.html`, then run `npm run pages`:

```html
<ul class="socials">
  <li><a href="https://…" aria-label="Instagram" rel="noopener"><span data-icon="instagram"></span></a></li>
</ul>
```

Icons available: `instagram`, `facebook`, `linkedin`, `youtube`.

### Restoring the office address

Set `COMPANY.address` and `COMPANY.mapQuery` in `data.js`, re-add a
`"footer.address"` key to `i18n.js`, then restore the markup:

```html
<!-- footer, in the .footer__contact list on every page -->
<li><span data-icon="pin"></span><span data-i18n="footer.address">…</span></li>

<!-- contact.html, in the "تواصل مباشر" card -->
<li><span data-icon="pin"></span><span><strong data-i18n="contact.office">مكتب المبيعات</strong><br>
  <span data-i18n="footer.address">…</span></span></li>

<!-- contact.html, after that card -->
<div class="map-frame" id="contact-map" style="margin-block-start:1.5rem"></div>
```

The map renderer removes `#contact-map` whenever `mapQuery` is empty, so the
map can never show a location the company has not given.

### Restoring the stats and testimonials

`COMPANY.stats` and `TESTIMONIALS` in `data.js` are now empty arrays, and the
markup is gone from `index.html` and `about.html`.

To bring either back, add the data **and** restore its section. The renderers
in `pages.js` delete their own section when the array is empty, so data alone
is not enough — but it does mean a half-finished restore fails safe rather than
rendering a heading over nothing.

```html
<!-- stats band: index.html after the hero, about.html after the page hero -->
<section class="section section--ink section--tight">
  <div class="wrap"><div class="stat-row" id="home-stats"></div></div>
</section>

<!-- testimonials -->
<section class="section section--stone">
  <div class="wrap">
    <div class="section-head">
      <p class="eyebrow" data-i18n="home.quotesEyebrow">آراء الملّاك</p>
      <h2 data-i18n="home.quotesTitle">ما يقوله من سكن معنا</h2>
    </div>
    <div class="quote-grid" id="home-quotes"></div>
  </div>
</section>
```

The `home.quotes*` keys are still in `i18n.js`, and `.stat-row` / `.quote-grid`
are still in the stylesheet, so nothing else needs changing.

---

## Images

Every photograph on the site is the company's own, lifted out of the General
Sherman 2 sales brochure (PDF) along with the nine unit floor plans, and
converted to WebP at several widths. `sherman1-*`, `sherman2-*` and `sherman3-*`
are photographs and 3D studies of the three schemes; `plan-a` … `plan-i` are the
architect's drawings for each unit model.

To add more, drop files into `assets/img/` named `<name>-480.webp`,
`<name>-800.webp`, `<name>-1280.webp`, `<name>-1920.webp` and reference `<name>`
from `data.js` (`image:` and `gallery:`). The markup builds the `srcset` from
those widths automatically. Floor plans need only `-800` and `-1280`.

`tools/generate-assets.mjs` still generates the Open Graph card and the favicon
from the logo, and can render abstract architectural artwork if a project has no
photography yet:

```bash
npm install        # installs sharp, the only dev dependency
npm run assets
```

---

## Shared page chrome

Every page is a finished, editable HTML file. The header, footer, WhatsApp
button, dialogs and script tags are identical across them, so there is a
scaffolder that lifts that chrome out of `index.html` and stamps it into the
others:

```bash
npm run pages
```

Run it after editing the header or footer **in `index.html`**. If you are only
editing the body of one page, edit that page directly and ignore the scaffolder.
`tools/build-pages.mjs` also holds each page's `<title>`, meta description and
SEO tags.

---

## File map

```
.
├── index.html               Home — hero, quick search, projects, units, process, quotes
├── projects.html            Project index with status tabs
├── project.html             Project detail (?id=sherman-1) — grid, plans, map, gallery
├── units.html               Full inventory with filters, sorting and shareable URLs
├── gallery.html             Filterable gallery with lightbox
├── about.html               Company story, commitments, process, testimonials
├── contact.html             Contact form, direct channels, map, FAQ
├── 404.html
├── assets/
│   ├── css/main.css         Design system; CSS logical properties throughout, so
│   │                        one stylesheet serves both RTL and LTR
│   ├── css/fonts.css        Self-hosted IBM Plex Sans Arabic (no external requests)
│   ├── fonts/               woff2 subsets
│   ├── img/                 Generated scenes (.svg sources + .webp renders) and plans
│   └── js/
│       ├── data.js          ← all content lives here
│       ├── i18n.js          ← all interface strings live here
│       ├── app.js           Header, language switch, modals, lightbox, forms, cards
│       ├── pages.js         Home, project index, gallery, contact page modules
│       ├── units.js         Inventory filtering, sorting, URL state
│       ├── project.js       Project detail page
├── tools/                   Optional generators (images, page scaffolding)
├── netlify.toml, vercel.json, robots.txt, sitemap.xml
│
├── jordan_tender_monitor/   The other project in this repo — not part of the
│                            site, never served. See its section below.
├── .github/workflows/       CI for the monitor, and its scheduled run
└── LICENSE
```

---

## Notes on how it is built

- **RTL and LTR from one stylesheet.** No `main-rtl.css`. Layout uses logical
  properties (`margin-inline-start`, `inset-inline-end`, `padding-block`), so
  switching `dir` mirrors the whole site.
- **Arabic-first.** The HTML ships Arabic; English is applied over it by
  `i18n.js`. The language is remembered in `localStorage` and can be forced with
  `?lang=en` — which makes English pages linkable and shareable.
- **Prices and numbers** use Western digits, as Jordanian property sites do, and
  are bidi-isolated so figures like `480+` and `+962 6 552 0176` do not reverse
  inside Arabic text.
- **No external requests at runtime.** Fonts are self-hosted; the only
  third-party embed is the Google Maps iframe on the contact and project pages.
- **Accessibility.** Semantic landmarks, one `h1` per page, a skip link, labelled
  form controls, visible focus rings, a focus-trapped dialog, keyboard-navigable
  lightbox, and `prefers-reduced-motion` support.
- **Performance.** ~380 KB of fonts across 15 subsets (browsers fetch only the
  ones they need), WebP images at four widths with `srcset`, lazy loading below
  the fold, and no JavaScript framework.

---

# Jordan Tender Intelligence Monitor

Automated multi-agent system that monitors 13 donor and international financial
institution procurement portals for Jordan-related consulting opportunities,
scores them for relevance, and writes a Word bid-review pack and an Excel
working file to disk.

Full documentation: **[`jordan_tender_monitor/README.md`](jordan_tender_monitor/README.md)**

## What it does

| Agent | Responsibility |
|---|---|
| Scrapers | Fetch notices from each portal, normalise to one record schema |
| Filter & scorer | Filter, score 0–100, deduplicate across portals |
| Reporter | Build the Word bid-review pack and the Excel working file |
| Writer | Save them to `output/`, with the run's health in the filename |

**Portals:** World Bank, EU TED, SAM.gov and UK Find a Tender (REST APIs); UNGM
— covering UNDP, UNICEF, WFP, UNOPS, UNHCR and UNRWA — plus EBRD, EIB, GIZ, KfW
(via Germany Trade & Invest) and IsDB (HTML); Saudi Fund, ADFD and JICA
(announcements only).

A failing portal is skipped with a diagnosed reason and reported as unavailable
with the URL to check by hand. It never aborts the run, and a broken run never
looks like a quiet one — portal health is in the output filename, and an
optional short **ACTION NEEDED** email fires when a run cannot read its sources
at all.

## Status — first live run completed 3 August 2026

| Portal | Live result |
|---|---|
| **EBRD** | **Working.** 4,004 notices scanned, 119 Jordan |
| **World Bank** | **Working** after a fix — the API ignores its own country filter |
| UK Find a Tender | Working. 500 read, no Jordan notices currently open |
| IsDB | Working. 144 read, no Jordan notices currently open |
| GIZ | Reachable, but only 23 rows read — extraction needs checking |
| **UNGM** | **Broken.** 3 rows read; the POST search is not returning a listing |
| EU TED | Broken. HTTP 400 — the v3 query grammar is wrong |
| KfW (via GTAI) | Blocked. HTTP 403 bot wall from a data-centre IP |
| EIB | Blocked. Cloudflare bot wall |
| Saudi Fund | Unreachable. Connection timeout |
| ADFD | Reachable, no listing found — needs `--capture` |
| JICA | HTTP 404 — the URL has moved |
| SAM.gov | Awaiting an API key |

**Still unverified:** the CSS selectors for the portals that have not yet
returned a clean listing. Run `python run.py --capture PORTAL` against those.

## Quick start

```bash
pip install -r jordan_tender_monitor/requirements.txt
cp jordan_tender_monitor/.env.example jordan_tender_monitor/.env   # then fill it in
cd jordan_tender_monitor

python run.py --check-portals   # can this machine reach the portals?
python run.py --dry-run         # scrape and print, change no state
python run.py --run             # the real run: write the files into output/
```

Everything is configured in
[`config.py`](jordan_tender_monitor/config.py), with each setting labelled by
the interview question it answers.

## Surviving site redesigns

The HTML scrapers do not depend on CSS class names alone. Each page runs through
a six-layer cascade — RSS feed, embedded JSON, CSS selectors, header-aware
tables, structural inference, anchor URL patterns — and the first layer whose
rows score as a genuine notice listing wins. Three of those layers use no class
names at all.

The quality gate matters more than the layers. Selectors run first, so an
over-broad guess like bare `article` would otherwise match a navigation menu and
short-circuit the layer that works. Rows are scored for listing-likeness, with
carrying a date weighted most heavily and gated outright.

## Running it from your phone

No install and no server: a GitHub Actions workflow gives you a **Run workflow**
button that works in a mobile browser, plus a weekday schedule. Results render
on the run page — a tappable table of opportunities and every portal's status —
with the Word and Excel files attached as artifacts.

**[`jordan_tender_monitor/RUN-FROM-YOUR-PHONE.md`](jordan_tender_monitor/RUN-FROM-YOUR-PHONE.md)**

A total portal outage makes the run exit non-zero, so GitHub marks it failed and
notifies you. That is the failure alert, with no mail credentials involved.

## Deploying

Step-by-step setup for a Windows Server, including Azure app registration and
Task Scheduler:
**[`jordan_tender_monitor/DEPLOYMENT-WINDOWS.md`](jordan_tender_monitor/DEPLOYMENT-WINDOWS.md)**

Note that nothing runs until it is deployed — this repository is source code,
not a running service.

## Tests

```bash
python jordan_tender_monitor/tests/run_all.py    # 853 checks, no network, no credentials
```

CI runs the suite and `pyflakes` on Python 3.11 and 3.12, on pushes to `main`
and on pull requests.

## Security

Email is off by default, so no mail credentials are required — nothing to leak
or rotate. `.env` is never committed and holds only the optional SAM.gov API
key. If you later switch delivery back on, read the `Mail.Send` scoping warning
in the [full README](jordan_tender_monitor/README.md#security) first: as an
Azure *application* permission it is tenant-wide.

---

## License

[MIT](LICENSE)
