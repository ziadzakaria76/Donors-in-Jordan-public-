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
| **Cloudflare Pages** | What the site actually uses. Deployed from CI, not the dashboard — see below. |
| **Netlify** | Drag the `website/` folder onto the Netlify dashboard, or connect the repo and set **base directory** `website`, **publish directory** `website`, and leave the build command empty. `netlify.toml` already sets caching and the 404 page. |
| **Vercel** | Import the repo, set **root directory** to `website`, framework preset **Other**, no build command. `vercel.json` sets the caching headers. |
| **cPanel / any shared host** | Upload the contents of `website/` into `public_html/` over FTP. Nothing else to configure. |
| **GitHub Pages** | Push, then set Pages to serve from the branch and the `/website` folder. |

### Cloudflare Pages

Deployment is driven by
[`.github/workflows/deploy-website.yml`](../.github/workflows/deploy-website.yml),
not by the dashboard's Git integration. It publishes `website/` on every push to
`main` that touches it, and has a **Run workflow** button for redeploying on
demand.

That is deliberate. A Git connection is a setting inside someone's account: you
cannot see it from the repository, you cannot review a change to it, and when it
is off, nothing says so — `main` simply stops reaching the site. That is not
hypothetical here. The General Sherman 3 schedule sat merged on `main` while the
live page still advertised it as a coming project with no units, and the only
clue was a screenshot. A workflow is in the diff, leaves a log per commit, and
fails loudly.

It needs three values under **Settings → Secrets and variables → Actions**:

| Name | Kind | Where it comes from |
| --- | --- | --- |
| `CLOUDFLARE_API_TOKEN` | secret | My Profile → API Tokens → Create Token → **Cloudflare Pages: Edit** |
| `CLOUDFLARE_ACCOUNT_ID` | secret | Cloudflare sidebar, or the hex string in the dashboard URL |
| `CLOUDFLARE_PAGES_PROJECT` | **variable** | the Pages project name, spelled exactly as in Workers & Pages |

The workflow checks all three are present and names any that are missing before
it spends a deploy finding out. It also runs `npm run check` first, so a content
file that fails its own tests never reaches the site.

`CLOUDFLARE_PAGES_PROJECT` is a variable rather than a secret on purpose: a
wrong project name does not fail, it silently creates a *second* Pages project
that no domain points at, and you would rather be able to read it back.

**If you also connect the project to Git in the dashboard, every push deploys
twice.** Pick one.

<details>
<summary>Setting the project up in the dashboard by hand</summary>

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

If you connect the project to Git, set **preview deployments to None**
(Settings → Builds & deployments). That setting is about Cloudflare building
*every* branch by itself — work in progress, and branches with no `website/`
directory at all. It is not the same thing as the previews described above,
which are published deliberately by a workflow, only for pull requests that
touch the site, and only under a `pr-` branch.

A Direct Upload project cannot be converted to a Git-connected one. That is a
reason to prefer the workflow above: `wrangler pages deploy` publishes to a
project of either kind, so a project created by dragging a folder in does not
have to be rebuilt.

Then **Custom domains → Set up a custom domain**, add `general-sherman-housing.com`
and `www.general-sherman-housing.com`. Cloudflare writes the DNS itself, since it
is also the registrar, and issues the certificate.

</details>

### Preview deployments

Every pull request that touches `website/` is published to its own URL by
[`.github/workflows/preview-website.yml`](../.github/workflows/preview-website.yml),
and the link is posted as a comment on the pull request — one comment, edited
in place on each push.

It exists because until now the only way to look at a change was to merge it.
CI checks a great deal, but "does this read right in Arabic, on a phone" is not
a question a checker answers, and this site puts live prices in front of buyers.

The preview is the same build production gets: the same content checks, the
same content-hashed asset URLs, the same Functions. Three things differ, all
deliberate:

- **It refuses to be indexed.** `robots.txt` disallows everything and `_headers`
  carries `X-Robots-Tag: noindex, nofollow`. A preview is a complete copy of a
  real estate site with real prices on a public URL; left alone it competes with
  the site it previews, and a buyer arriving from a search would be reading a
  build nobody approved.
- **It never runs for a fork.** The job holds the Cloudflare deploy token.
- **It deploys under a `pr-<number>` branch,** never the production branch, and
  refuses to run if the two are ever equal. That is what keeps a pull request
  off the live domain — `wrangler pages deploy --branch` is the only thing
  separating a preview from production.

`npm run check` asserts all three, plus that the deploy step runs from
`website/` — the same footgun that once shipped a site with no API.

The admin panel on a preview will not work, and that is correct: the Access
policy is bound to the custom domain, so a preview request carries no
assertion and `/api/*` answers 401. It fails closed rather than exposing a
write endpoint on a URL nobody is guarding. If you ever set `GITHUB_TOKEN` for
the Preview environment in Cloudflare as well as Production, that stays true —
the Function verifies the assertion rather than trusting a header.

Previews are not cleaned up automatically. Cloudflare keeps them; delete old
ones from the dashboard if the list gets long.

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

### Versioned asset URLs

`must-revalidate` asks politely, and asking was not enough: the General Sherman
3 schedule went live and the site kept showing "coming soon" with no units,
because a browser was still using a `data.js` it had kept from before.

So the deploy runs [`tools/stamp-assets.mjs`](tools/stamp-assets.mjs), which
rewrites every CSS and JS reference with a hash of that file's contents:

```html
<script src="assets/js/data.js?v=f164527e"></script>
```

`data.js?v=f164527e` is simply a different URL from `data.js?v=1b7e0d33`, so no
cache anywhere can answer one with the other. The HTML naming them is never
cached hard, so a new hash reaches visitors on their next page load.

**It runs in CI, not in the repository.** A committed stamp goes stale the
moment someone edits `data.js` and forgets to re-run it — the same bug with an
extra step. The deploy workflow stamps its own disposable checkout, so the files
here keep plain URLs and stay openable. `npm run stamp` does it locally if you
want to see the output; it is idempotent, and `git checkout -- '*.html'` undoes
it.

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

One thing is still unfinished. It is not false — the invented content has been
removed rather than left in place — so nothing here is published as a claim the
company has not made. Search for `«REPLACE»` in `assets/js/data.js`, or run
`npm run check`, which lists what is left.

- **Founding year** — `COMPANY.founded` is `null` and no page states a year,
  because the one that was here was invented. Set it and the About page can
  state it.

Enquiry capture is done: `COMPANY.formFields.access_key` holds a Web3Forms key,
so every submission opens WhatsApp **and** is emailed. See *Where the form
submissions go* below, including how to change which inbox receives them.

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

A copy is **also** kept, through **Web3Forms**. Each submission opens WhatsApp
*and* is POSTed there: WhatsApp is the delivery, the endpoint is the record.
It is configured in `assets/js/data.js`:

```js
formEndpoint: "https://api.web3forms.com/submit",
formFields: { access_key: "a61a7c6f-…" },
```

**To change which inbox receives them,** do it in the Web3Forms dashboard, not
here — the key identifies the form, not the address, so the recipient can move
without a deploy. They currently go to the account that created the form.

**Emptying the key switches capture off, it does not break it.** A blank key
would otherwise still POST to a real URL, be rejected for the missing key, and
log the rejection where nobody would look — indistinguishable from working. So
`captureReady()` skips the POST until every field in `formFields` has a value,
and the forms behave exactly as they do with no endpoint at all. That is also
what makes the key safe to remove in a hurry.

The key is public by design — Web3Forms says so on the page that issues it: it
names an inbox, it does not open one. That is why it lives in this file. A
static host has no secret store to read from, and anything the browser must send
is visible to anyone who looks; pretending otherwise would be theatre.

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

`content.json` is the file you edit. Every piece of text in it is a
`{ ar, en }` pair.

```bash
npm run data     # content.json → assets/js/data.js
npm run check
```

Then commit both files.

### Editing it in a browser

`/admin/` edits `content.json` from a browser, so a price change does not need
a text editor and a git client. It is described in full under
[The admin panel](#the-admin-panel) below.

### Why there are two files

`assets/js/data.js` is what the browser loads, and it is also the site's
documentation: its comments record why the founding year is `null`, why the
testimonials array is empty, why a sold unit carries no price, and why the
commercial registration is absent rather than invented. Those comments are the
reason nobody has quietly re-added the content that was removed.

An admin panel writing to that file directly would delete every one of them —
rewriting a commented source file from a web form is how comments die. So the
two jobs are split:

| | |
|---|---|
| `content.json` | what a person or the panel edits — projects, units, prices, FAQs, testimonials, captions, the company's own details |
| `tools/build-data.mjs` | the prose, the enumerations, and the code around them |
| `assets/js/data.js` | generated from both, never edited by hand |

The enumerations stay in the generator on purpose. Districts, amenities,
orientations, unit types and project statuses are not content — they are the
vocabulary the content is checked *against*, and a panel able to invent a new
orientation would defeat the check that catches a mistyped one.

Project provenance notes live in `content.json` alongside the project they
describe, under `notes`, keyed by field name. "The brochure marks none as sold"
and "no status, because the brochure does not say" are the record of why the
data looks the way it does; losing them is how a gap in a brochure turns into a
guess on a page.

`npm run check` renders `content.json` and compares the result to the committed
`data.js`, so an edit made in the wrong file fails while it is still a diff.
The deploy deliberately does *not* regenerate `data.js` — if it did, a
correction typed into the generated file would ship once and then vanish, which
is the worst kind of failure, because the price was right when you checked it.

### Checking an edit

```bash
npm run check
```

Reads `data.js` and asserts what the rest of the site assumes about it: that it
matches `content.json`, that
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

## The admin panel

`/admin/` is a small editing tool for the content: projects, the unit schedules
and their prices, construction progress, FAQs and testimonials. It has no
database. It saves by committing `content.json` and the rendered `data.js` to
this repository as one commit, which means every edit is a diff with an author
and a date, CI runs on it, the deploy is the ordinary deploy, and undoing a
mistake is `git revert` rather than a support request.

```
browser  ->  /api/content (PUT)  ->  validate  ->  render data.js
                                        |
                           one commit on main, both files
                                        |
                      CI: npm run check -> wrangler pages deploy
```

### One definition of what is valid

`tools/validate-content.mjs` holds the rules that need nothing but the content
-- unit ids unique, every orientation and amenity resolving to a label, an
available unit carrying a price, both languages filled in together. It runs in
four places from one file:

| where | when |
|---|---|
| the panel, in your browser | as you type |
| the Pages Function | before it commits anything |
| `npm run check` | before you push |
| CI | before anything deploys |

`tools/render-data.mjs` also holds the five enumerations -- districts,
amenities, unit types, orientations, project statuses -- and this is the whole
point of the split. They are the vocabulary the content is checked *against*. A
panel that could add an orientation would be a panel where a typo passes
validation, so the panel offers them as a closed list and adding a real one is
a code change, reviewed as a diff.

Both files import nothing at all. They have to run in a Workers runtime and in
a browser as well as in Node, so a single `import ... from "node:fs"` in either
would break the deploy and the panel at once. `npm run check` asserts they stay
clean.

### What it cannot do

- **Add an image.** Photographs are re-cut to several widths by
  `npm run assets`, which needs the original file. The panel edits captions and
  the order images appear in; adding one is still a commit.
- **Invent vocabulary.** See above.
- **Show leads.** Decided, not deferred — see below.

### Leads: the site keeps none

Every form hands the enquiry to WhatsApp first, synchronously, so delivery
survives even if the rest fails. It then posts a copy to Web3Forms, which
emails it to the sales inbox. WhatsApp is the channel a buyer in Amman actually
replies on; the email is the record.

The panel shows no lead list, and that is the arrangement rather than a gap.
Reading submissions back needs the Web3Forms Submissions API, which is a paid
feature. The alternative was a Cloudflare database of our own — which would
mean this site holds buyers' names and phone numbers. It does not, and a panel
that listed leads would be a panel with a copy of every enquiry in it. Holding
one is a different commitment from passing one along.

**The operational catch:** Web3Forms keeps submissions for 30 days on the free
plan. After that the copy in their dashboard is gone, so the inbox is the
durable archive and the dashboard is a recent view. Do not delete an enquiry
email expecting to find it again later.

Revisit this if enquiries ever need to be searched, exported or reported on.
Not before.

### Setting it up

The panel needs Cloudflare Access in front of it and a GitHub token to commit
with. Neither lives in this repository.

**1. Put Access in front of it.** Cloudflare Zero Trust -> Access ->
Applications -> Add an application -> Self-hosted. Free for up to 50 users.

- Cover **both** paths: `your-domain.com/admin` *and* `your-domain.com/api`.
  An Access policy on `/admin` alone would leave the write API facing the
  internet. The panel refuses to work in that case rather than trusting it, but
  the point is not to be in that position.
- Policy: *Emails* -> your address. Session duration is up to you; a week is
  reasonable for one person.
- Copy the **Application Audience (AUD) tag** from the application overview.

**2. Set the variables.** Cloudflare dashboard -> Workers & Pages -> the
project -> Settings -> Variables and Secrets:

| name | kind | value |
|---|---|---|
| `ACCESS_TEAM_DOMAIN` | plaintext | `yourteam.cloudflareaccess.com` |
| `ACCESS_AUD` | plaintext | the AUD tag from step 1 |
| `GITHUB_REPO` | plaintext | `owner/repository` |
| `GITHUB_BRANCH` | plaintext | `main` (optional) |
| `GITHUB_TOKEN` | **encrypted** | see below |

`GITHUB_TOKEN` is a fine-grained personal access token (GitHub -> Settings ->
Developer settings -> Personal access tokens -> Fine-grained tokens) scoped to
**this repository only**, with **Contents: read and write**. Nothing else. It
must be stored **encrypted** -- a plaintext variable is readable by anyone who
can open the dashboard.

If any of these is missing, the panel names the missing one at load rather than
failing at the end of a long edit.

### Why the assertion is verified rather than trusted

The Function verifies the Access JWT signature itself instead of trusting the
`Cf-Access-Authenticated-User-Email` header. "Access is in front of it" is a
claim about a setting in someone's dashboard -- the same class of claim as the
Git connection that was silently absent while `main` stopped reaching the site
for twelve hours. If the policy is ever removed or scoped to the wrong path,
verifying turns that into a 401 instead of a stranger with commit access.

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
`sherman3-*` are photographs and 3D studies of the three schemes — note that
General Sherman 3 is now **both**: `sherman3-1` … `sherman3-4` are 3D studies of
the elevations, `sherman3-lobby-*` are photographs of the entrance as built, and
the gallery note and the project description both say so rather than describing
all of them as renders. `plan-a` …
`plan-i` are the architect's drawings for each General Sherman 2 unit model, and
`plan-3a` … `plan-3j` for General Sherman 3. Each `plan-3*` drawing is cropped
straight from its brochure page, so it carries the model's room-dimension
schedule underneath the plan, as published.

To add more, drop files into `assets/img/` named `<name>-480.webp`,
`<name>-800.webp`, `<name>-1280.webp`, `<name>-1920.webp`, reference `<name>`
from `data.js` (`image:` and `gallery:`), give it a caption in
`IMAGE_CAPTIONS` — which is what the site gallery builds itself from, and what
a project page uses to caption its images instead of numbering them — then run:

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
├── content.json           ← all content lives here; assets/js/data.js is built from it
├── admin/                   The editing panel (behind Cloudflare Access)
├── functions/api/           Pages Functions: the panel's read and write API
├── assets/
│   ├── css/main.css         Design system; CSS logical properties throughout, so
│   │                        one stylesheet serves both RTL and LTR
│   ├── css/fonts.css        Self-hosted IBM Plex Sans Arabic (no external requests)
│   ├── fonts/               woff2 subsets
│   ├── img/                 Photographs (.webp at several widths) and floor plans
│   └── js/
│       ├── img-manifest.js   Generated — which widths exist per image
│       ├── data.js          Generated from ../../content.json — do not edit
│       ├── i18n.js          ← all interface strings live here
│       ├── app.js           Header, language switch, modals, lightbox, forms, cards
│       ├── pages.js         Home, project index, gallery, contact page modules
│       ├── units.js         Inventory filtering, sorting, URL state
│       ├── project.js       Project detail page
├── tools/                   render-data.mjs (pure: content.json → data.js) and
│                           validate-content.mjs (pure: the publishable rules) — both
│                           also run in the Worker and in the panel, so neither may
│                           import node:*. Plus build-data.mjs, check-content.mjs and
│                           the optional image and page-scaffolding generators.
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
