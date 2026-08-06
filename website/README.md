# جنرال شيرمان — General Sherman Housing

A bilingual (Arabic RTL / English LTR) marketing site for a Jordanian residential
developer: project showcases, a live unit inventory with filters, a per-building
availability grid, floor plans, payment plans with an instalment calculator, a
gallery, and lead capture through WhatsApp, phone and forms.

Plain HTML, CSS and JavaScript. **No build step, no framework, no runtime
dependencies.** Every file in this folder is the file that gets deployed.

---

## Run it locally

Any static file server works. The site must be served over HTTP — opening
`index.html` from the filesystem will break the fonts and the `fetch`-based
form submission.

```bash
cd website
python3 -m http.server 8080      # or: npm start
```

Then open <http://localhost:8080>. Try `?lang=en` on any page to load it in
English.

---

## Deploy it

The site is a folder of static files. Publish `website/` as the site root.

| Host | What to do |
| --- | --- |
| **Netlify** | Drag the `website/` folder onto the Netlify dashboard, or connect the repo and set **base directory** `website`, **publish directory** `website`, and leave the build command empty. `netlify.toml` already sets caching and the 404 page. |
| **Vercel** | Import the repo, set **root directory** to `website`, framework preset **Other**, no build command. `vercel.json` sets the caching headers. |
| **cPanel / any shared host** | Upload the contents of `website/` into `public_html/` over FTP. Nothing else to configure. |
| **GitHub Pages** | Push, then set Pages to serve from the branch and the `/website` folder. |

After deploying, replace `https://www.generalsherman.jo` with the real domain in:
`sitemap.xml`, `robots.txt`, and the `<link rel="canonical">` / `og:url` /
`hreflang` tags in each page's `<head>` (or in `tools/build-pages.mjs`, then
re-run `npm run pages`).

---

## What to replace before going live

Everything below is invented placeholder content. Search for `«REPLACE»` in
`assets/js/data.js` to find each one.

- **Company identity** — tagline, founding year, commercial registration. The
  name and logo are real; everything around them is not.
- **Founding year and registration** — `COMPANY.founded` is `null` and no page
  states a founding year, because the one here was invented. `registration` is
  likewise a placeholder and is not rendered anywhere yet.
- **Contact details** — the phone, WhatsApp number and email are real. The
  **office address is deliberately blank**: `COMPANY.address` and `mapQuery`
  are empty, so the footer's address line, the contact page's office row and
  the office map are all absent. Filling either field in is not enough on its
  own — the markup was removed too (see *Removed sections*).
- **Social links** — the four `href: "#"` entries.
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

Units are **not** listed one by one. Each project declares its floors and its
unit *lines* — the layout that repeats on every floor, which is how these
buildings are actually planned and priced:

```js
floors: 8,
pricePerM2: 1450,
floorPremium: 0.022,        // each floor up costs 2.2% more
lines: [
  { code: "A", beds: 4, baths: 4, area: 292, type: "apartment", plan: "plan-4br", … },
],
sold:     ["0-A", "1-A", "1-B"],   // "<floor>-<line>", floor 0 = ground floor
reserved: ["2-A"],
```

The site expands that into the full inventory at load time, and computes each
price as `area × pricePerM2 × (1 + floorPremium × floor)`, rounded to JOD 500.
So:

- **A unit sold?** Add its `"<floor>-<line>"` key to `sold`.
- **Price change?** Edit `pricePerM2` for the whole building, or `area` for one line.
- **New project?** Copy a whole project object and change the fields. Add a hero
  image named `project-<image>` (see *Images* below).

Ground floors become garden apartments when `groundFloorIsGarden` is set; top
floors become a duplex or penthouse with `topFloorIsDuplex` / `topFloorIsPenthouse`.

### Interface text

UI strings live in `assets/js/i18n.js` as `{ ar, en }` pairs keyed by
`data-i18n` attributes. The Arabic is written into the HTML as well — so it is
what search engines and no-JS visitors see — and repeated in `i18n.js` so that
switching back from English restores it. **If you change a string in the HTML,
change its twin in `i18n.js`.**

---

## Removed sections

Five things were cut rather than filled, because their content was invented and
the site now carries the real name and logo: the **stats band**, the
**testimonials**, the About page's **company story**, the **office address**,
and the **three projects** with their entire inventory. No page now claims a
track record, a founding year, a location beyond Amman, or a scheme that does
not exist.

### The projects

`PROJECTS` and `DISTRICTS` in `data.js` are empty, and the site adapts rather
than breaking. With no projects:

- the home page drops its featured-projects and featured-units sections, and
  the hero's quick search;
- the project index and the units page show a stated empty state with a link to
  contact, and the filter panel and status tabs are removed;
- `project.html` redirects to the index for any id;
- the calculator loses its unit picker but still works on a typed-in price;
- the contact form loses its project dropdown;
- the footer's projects column is gone.

Adding real projects back to the array restores all of it — the markup and the
renderers are untouched, and there is nothing else to switch on.

The About page runs hero → four commitments → process → CTA. To add a story
section back, write it into `i18n.js` and add a `split split--wide` section to
`about.html`; the four commitments section is the nearest pattern to copy.

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

There are no stock photos. Every image is generated from code as an
architectural study — massing renders, elevation studies, interiors in one-point
perspective, floor plans — and rasterised to WebP at four widths.

The rendered images are committed, so you do not need to run anything. To change
the artwork (palettes, massing, framing) edit `tools/generate-assets.mjs` and:

```bash
npm install        # installs sharp, the only dev dependency
npm run assets
```

To use **real photographs** instead, drop them into `assets/img/` named
`<name>-480.webp`, `<name>-800.webp`, `<name>-1280.webp`, `<name>-1920.webp` and
reference `<name>` from `data.js` (`image:` and `gallery:`). The markup builds
the `srcset` from those four widths automatically.

Floor plans are unlabelled SVG line drawings; the room numbers are explained by
`PLAN_LEGEND` in `data.js`, so the key translates with the rest of the site.

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
website/
├── index.html               Home — hero, quick search, projects, units, process, quotes
├── projects.html            Project index with status tabs
├── project.html             Project detail (?id=residence-76) — grid, plans, map, gallery
├── units.html               Full inventory with filters, sorting and shareable URLs
├── payment-plans.html       The three payment plans + instalment calculator
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
│       └── plans.js         Payment plans and the calculator
├── tools/                   Optional generators (images, page scaffolding)
├── netlify.toml, vercel.json, robots.txt, sitemap.xml
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
