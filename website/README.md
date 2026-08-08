# جنرال شيرمان — General Sherman Housing

A bilingual (Arabic RTL / English LTR) marketing site for a Jordanian residential
developer: project showcases, a live unit inventory with filters, a per-building
availability grid, floor plans, a gallery, and lead
capture through WhatsApp, phone and forms.

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
| **Cloudflare Pages** | The domain is already at Cloudflare, so this is the shortest path — see below. |
| **Netlify** | Drag the `website/` folder onto the Netlify dashboard, or connect the repo and set **base directory** `website`, **publish directory** `website`, and leave the build command empty. `netlify.toml` already sets caching and the 404 page. |
| **Vercel** | Import the repo, set **root directory** to `website`, framework preset **Other**, no build command. `vercel.json` sets the caching headers. |
| **cPanel / any shared host** | Upload the contents of `website/` into `public_html/` over FTP. Nothing else to configure. |
| **GitHub Pages** | Push, then set Pages to serve from the branch and the `/website` folder. |

### Cloudflare Pages

**Workers & Pages → Create → Pages → Connect to Git**, pick the repo, then:

| Setting | Value |
| --- | --- |
| **Production branch** | `main` |
| Framework preset | **None** |
| Build command | *(empty)* |
| Build output directory | `website` |
| Root directory | `/` (default) |

**Save and Deploy.** Every push to `main` redeploys.

**The production branch must be `main`.** The site lived on a feature branch
while it was being built, and for a while a second copy of it lived at the
repository root as well. Both are gone: `main` holds the one copy, in
`website/`. Pointing production at anything else re-creates the problem this
layout exists to prevent — two copies of one site, diverging quietly.

Consider setting **preview deployments to None** (Settings → Builds &
deployments). Otherwise every branch is built and published at a public preview
URL, including work in progress and branches with no `website/` directory at
all.

A Direct Upload project cannot be converted to a Git-connected one. If the
project was created by dragging a folder in, make a new project connected to
Git, check it on its `*.pages.dev` URL, then move the custom domain across and
delete the old project.

Then **Custom domains → Set up a custom domain**, add `general-sherman-housing.com`
and `www.general-sherman-housing.com`. Cloudflare writes the DNS itself, since it
is also the registrar, and issues the certificate.

### Caching, and why images are not cached forever

`_headers` sets three different policies deliberately, and `netlify.toml` and
`vercel.json` mirror them:

| What | Policy | Why |
| --- | --- | --- |
| `assets/fonts/*` | 1 year, `immutable` | a woff2 subset is never re-cut under the same name |
| `assets/img/*` | 1 week, revalidated | filenames carry no content hash, and images **do** get re-rendered in place |
| `*.html` | `max-age=0, must-revalidate` | the shells the content is rendered into |
| `assets/js/*`, `assets/css/*` | `max-age=0, must-revalidate` | **the prices live here**, not in the HTML |

The JS rule is the one that is easy to get wrong, and this file got it wrong
until it was caught. It used to leave CSS and JS "on the default (revalidate
every time)" and protect only the HTML, reasoning that the pages carry the
prices. They do not: every price, unit and phone number is in
`assets/js/data.js`, and the pages are shells it fills in. Leaving that file to
whatever a host happens to default to is leaving the price list to a platform
default — so it is stated, not assumed.

The image rule is the one that looks wrong and is not. `immutable` would be
correct if filenames were content-hashed; they are not —
`sherman2-lobby-1-480.webp` is a stable name for whatever that photograph
currently is. Twenty-six images were once re-cut in a single commit to crop a
camera watermark out of them. Under a year-long `immutable` cache, every
returning visitor would have kept the watermarked version, and there would have
been no way to reach them.

`_headers` in this folder carries the cache and security headers — it is the
Pages equivalent of `netlify.toml` and `vercel.json`, and Pages reads it with no
configuration. Pages serves `404.html` for unmatched paths on its own.

**The `www` redirect is not in this repo and cannot be.** Pages serves both
hostnames identically, which splits ranking between two addresses, and a
`_redirects` file cannot match on hostname. Do it in the dashboard:
**Rules → Redirect Rules → Create rule** — when `Hostname equals
www.general-sherman-housing.com`, redirect to
`concat("https://general-sherman-housing.com", http.request.uri.path)`, status
**301**, preserve query string.

### The domain

`https://general-sherman-housing.com` — registered with Cloudflare. It is already
written into `COMPANY.domain`, `sitemap.xml`, `robots.txt`, `SITE` in
`tools/build-pages.mjs`, and the `<link rel="canonical">` / `og:url` /
`hreflang` tags in every page's `<head>`.

The site uses the **apex** (no `www`). Point `www` at the apex with a 301 so
search engines see one address: on Cloudflare that is a Redirect Rule, on
Netlify and Vercel it is the default once the apex is set as primary.

If the domain ever changes, edit `SITE` in `tools/build-pages.mjs`, run
`npm run pages`, then update `COMPANY.domain`, `sitemap.xml` and `robots.txt`
by hand — the scaffolder does not touch those three.

---

## What to replace before going live

Two things are still unfinished. Neither is false — the invented content has
been removed rather than left in place — so nothing here is published as a
claim the company has not made. Search for `«REPLACE»` in `assets/js/data.js`.

- **Founding year** — `COMPANY.founded` is `null` and no page states a year,
  because the one that was here was invented. Set it and the About page can
  state it.
- **Web3Forms access key** — `COMPANY.formFields.access_key` is empty, so no
  copy of each enquiry is recorded yet. Every form still delivers to WhatsApp
  with an email fallback in the meantime. See *Where the form submissions go*
  below.

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
- **Projects and units** — see below.
- **Logo** — `assets/img/logo-mark.png` (house mark) and `assets/img/logo.png`
  (full stacked lockup) were extracted from the supplied artwork and keyed to
  transparency. The favicon and iOS tile are generated from the mark by
  `npm run assets`. **Supply the original vector (AI/EPS/SVG) when you have it**
  — these are lifted from a raster screenshot, which is fine on screen at the
  sizes used but will not hold up in print or at very large sizes.

### Where the form submissions go

**Every enquiry goes to WhatsApp.** Submitting a form opens WhatsApp with the
details pre-written, and offers an email link as a backup. That needs no
backend and puts the lead on the phone immediately.

To *also* keep a server-side record, the site is pointed at **Web3Forms**. One
thing is missing: the access key that says which inbox to deliver to. Get one at
<https://web3forms.com> — enter the address, and the key is emailed back — then
put it in `assets/js/data.js`:

```js
formEndpoint: "https://api.web3forms.com/submit",
formFields: { access_key: "xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx" },
```

That is the whole change. Each submission then opens WhatsApp **and** is POSTed
to Web3Forms. WhatsApp is the delivery; the endpoint is the record.

**While the key is blank, capture counts as switched off, not broken.** A blank
key would still POST to a real URL, be rejected for the missing key, and log the
rejection where nobody would look — indistinguishable from working. `submitForm`
therefore skips the POST until every field in `formFields` has a value, and
forms behave exactly as they do with no endpoint at all.

The key is public by design: it names an inbox, it does not open one. That is
why it lives in this file — a static host has no secret store to read from, and
anything the browser must send is visible to anyone who looks.

**Using Formspree instead?** Its id goes in the URL and it needs nothing in the
body, so `formEndpoint: "https://formspree.io/f/xxxxxxx"` with
`formFields: {}`. Both services are already handled; see `subject` below.

### What the endpoint receives

The visible fields are not enough on their own. Both forms ask the same four
questions, so a captured unit enquiry would otherwise be indistinguishable from
a general one — no unit, no price, no sign which of twenty-seven was meant.
`enquiryPayload` adds what the page already knows:

| Field | Value |
| --- | --- |
| `name`, `phone`, `email`, `message`, `consent` | what the visitor typed |
| `unit` | the unit's title and summary, on the unit dialog only |
| `project` | the chosen project, on the contact form only |
| `subject`, `_subject` | the enquiry's heading — the same string under both names, because Web3Forms reads `subject` and Formspree reads `_subject` |
| `page` | the full URL the enquiry came from |
| `language` | `ar` or `en` — which language they were reading |
| `_gotcha` | the honeypot, left in deliberately: both services use it to drop bots |

Two details in `submitForm` matter if you edit it:

- **WhatsApp is opened before the POST is awaited.** `window.open` only works
  inside the user gesture that submitted the form. Awaiting `fetch` first
  spends that gesture, and the browser blocks the WhatsApp tab as a pop-up.
- **A failed POST is logged, not shown.** By the time it runs, the enquiry has
  already been delivered — a failure loses the copy, not the lead. Telling
  someone their message failed when it did not is how you lose a real enquiry.
  A *blocked WhatsApp tab* is shown, because that one did cost them something.

---

## Editing the content

`assets/js/data.js` is the only file you need for content changes. Every piece
of text is a `{ ar, en }` pair.

### Checking an edit

```bash
npm run check
```

Reads `data.js` and asserts what the rest of the site assumes about it: that
every image and floor plan it names exists at the widths the manifest promises,
that unit ids are unique, that every orientation, type, district, amenity and
status resolves to a label, that an available unit carries a price, that a plan
shared by several units describes units of one size, that both languages are
filled in together, and that `COMPANY.domain`, `build-pages.mjs`, `sitemap.xml`
and `robots.txt` all name the same site.

None of those throw on their own. A mistyped orientation renders a blank where
the aspect goes; an available unit with no price shows as unsellable; a plan
name with a typo fetches a drawing nobody made. The site degrades politely and
says nothing, which is the worst way for a price list to be wrong.

It also prints whatever is still marked `«REPLACE»`, so the go-live list is
something you run rather than something you remember. CI runs it on every pull
request.

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
Amman, an account the company does not have, or payment terms nobody has
stated.

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

### The payment plans and the calculator are gone

Both were removed, not blanked. Nothing in the brochure states payment terms,
and the three plans that were here — deposit percentages, instalment
schedules, a grace period, a no-early-settlement-fee promise — were demo
content written before the company was named.

Emptying `PAYMENT_PLANS` took only the cards. It left the calculator, which
priced financing from a default interest rate and term that nobody had agreed,
and a home page band advertising it. On a site carrying the real name, logo and
phone number, that is a financing claim a visitor can act on, so the page went
with the data: `payment-plans.html`, `assets/js/plans.js`, the `PAYMENT_PLANS`
array, the per-project section, the navigation entry, the sitemap entry, the
home page band, and the page definition in `tools/build-pages.mjs`.

Restoring it means writing the real terms first and rebuilding the page around
them. It was deliberately not left as a shell to fill in: a half-restored
financing page is the failure mode that matters here.

### Project status badges

`status` is optional on a project. General Sherman 2 has none, because the
brochure does not say whether the building is delivered or still under
construction — so its card and hero show no badge at all rather than a guess.
Add `status: "selling" | "delivered" | "upcoming"` to a project to show one; a
`"selling"` project whose every unit is sold flips to `"soldout"` on its own.

---

## Images

Every photograph on the site is the company's own, lifted out of the General
Sherman 2 and General Sherman 3 sales brochures (PDF) along with the unit floor
plans, and converted to WebP at several widths. `sherman1-*`, `sherman2-*` and
`sherman3-*` are photographs and 3D studies of the three schemes; `plan-a` …
`plan-i` are the architect's drawings for each General Sherman 2 unit model, and
`plan-3a` … `plan-3j` for General Sherman 3. Each `plan-3*` drawing is cropped
straight from its brochure page, so it carries the model's room-dimension
schedule underneath the plan, as published.

To add more, drop files into `assets/img/` named `<name>-480.webp`,
`<name>-800.webp`, `<name>-1280.webp`, `<name>-1920.webp`, reference `<name>`
from `data.js` (`image:` and `gallery:`), then run:

```bash
npm run manifest
```

That rewrites `assets/js/img-manifest.js`, which records **which widths actually
exist for each image**, so `picture()` offers the browser a `srcset` it can
fetch. Not every photograph has all four: most of the brochure interiors are
480 px at source, and before the manifest existed the pages asked for
`sherman2-interior-1-1280.webp` and got a 404 — twenty-eight of them, on exactly
the wide viewports where the browser reaches for the largest file. **Re-run
`npm run manifest` whenever you add or re-render an image.** A name missing from
the manifest still renders; it just falls back to offering all four widths.

Fifteen of the photographs carried a burned-in `Galaxy S24 Ultra` camera stamp
with the date and time. Each was cropped just above the stamp — between 7% and
15% off the bottom, all of it floor — and re-rendered at every width.

The generated artwork that stood in before the brochure arrived — `gallery-*`,
`hero-*`, `project-*` and the old `plan-2br`-style drawings, 2.3 MB in all — is
deleted. It depicted buildings that do not exist, and on a live domain those
files stay publicly fetchable whether or not a page links to them.

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
website/
├── index.html               Home — hero, quick search, projects, units, process, CTA
├── projects.html            Project index
├── project.html             Project detail (?id=sherman-2) — grid, plans, map, gallery
├── units.html               Full inventory with filters, sorting and shareable URLs
├── gallery.html             Filterable gallery with lightbox
├── about.html               Commitments and process
├── contact.html             Contact form, direct channels, map, FAQ
├── 404.html
├── assets/
│   ├── css/main.css         Design system; CSS logical properties throughout, so
│   │                        one stylesheet serves both RTL and LTR
│   ├── css/fonts.css        Self-hosted IBM Plex Sans Arabic (no external requests)
│   ├── fonts/               woff2 subsets
│   ├── img/                 Photographs (.webp at several widths) and floor plans
│   └── js/
│       ├── img-manifest.js   Generated — which widths exist per image
│       ├── data.js          ← all content lives here
│       ├── i18n.js          ← all interface strings live here
│       ├── app.js           Header, language switch, modals, lightbox, forms, cards
│       ├── pages.js         Home, project index, gallery, contact page modules
│       ├── units.js         Inventory filtering, sorting, URL state
│       ├── project.js       Project detail page
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
- **Unit deep links.** A card on the units page links to
  `project.html?id=<project>#unit-<project>-<code>`. The project page shows only
  its first nine units, so it pulls the requested one to the front if the list
  would otherwise cut it, then scrolls to it and marks it `.card--targeted` —
  the browser cannot do that itself, because it resolves the fragment while
  parsing, long before the cards are rendered.
- **Accessibility.** Semantic landmarks, one `h1` per page, a skip link, labelled
  form controls, visible focus rings, a focus-trapped dialog, keyboard-navigable
  lightbox, and `prefers-reduced-motion` support.
- **Performance.** ~380 KB of fonts across 15 subsets (browsers fetch only the
  ones they need), WebP images at four widths with `srcset`, lazy loading below
  the fold, and no JavaScript framework.
