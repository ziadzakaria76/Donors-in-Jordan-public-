# Why each portal is configured the way it is

The portal list is data: [`portals.json`](portals.json). This file is the prose
that goes with it — what was tried, what failed, and what a value is doing
there. JSON cannot hold a comment, and every one of these notes was written
because someone had already got it wrong once.

Read [`README.md`](README.md) first for the extraction cascade and the quality
gate; this file assumes both.

---

## How an entry is read

**A portal with no `module` is data alone.** Its URLs go through the six-layer
cascade — feed, embedded JSON, CSS selectors, header-aware tables, structural
inference, anchor pattern — and the first layer whose rows score as a genuine
listing wins. Eight of the thirteen are like this, and so is every portal added
from the phone app.

**A portal with a `module` has bespoke fetch logic** in
`portals/<module>.py`: a POST search endpoint or a REST API, not a page. Its
`code_owned` fields are set in that module, next to the evidence for them, and
setting one in `portals.json` is *rejected* rather than ignored — a value that
is read, accepted and then overridden looks applied and is not.

**A malformed entry names itself and is skipped**, and the run reports it as
`unavailable` with the reason. It never raises. One bad entry must not cost the
other twelve portals their run, and a portal that quietly disappeared from the
report would be the worst outcome of the three.

### What a URL alone can and cannot do

The cascade reads many listings from nothing but an address, and the quality
score and row count from the first run say whether it worked. That is
best-effort, not a promise. Four portals here prove the limits:

| | Why a URL was not enough |
|---|---|
| UNGM | The listing is built client-side. The rows come from a JSON search endpoint the page posts to, with the country as a numeric id read out of the page's own dropdown |
| EU TED | A REST API with an expert-query grammar; the country is `JOR`, not `JO`, and the page limit is 100. Both were silent 400s |
| JICA | Publishes no Jordan procurement page at all |
| ADFD | Publishes no machine-readable listing at all, rendered or not |

Adding one of those by URL would have produced a portal that reports
`unavailable` forever while looking like an honest failure.

---

## Tier 1 — REST APIs

### World Bank — `module: worldbank`

**Never trust a source's own country filter.** The API accepts
`countryshortname=Jordan` and ignores it, returning worldwide notices. This
module was the only one skipping `jordan_only()`, on the strength of a comment
justifying the omission, and the first report led with a Caribbean education
project.

**Defence in depth is not depth when both layers read the same field.**
`qterm=Jordan` is a full-text search, and this module stored the searched body
as the record description — so the client-side text filter could not reject
anything the API returned. It kept 500 of 500, and the report carried
water-supply consultancies in Blantyre, Malawi. The country *field* now
decides; text matching is kept only for notices with no country field, where it
is the only signal available.

**`500 read` was the row cap, not the result size.** Asking for 500 and getting
exactly 500 is what a truncated read looks like from outside. It now pages by
offset until a page comes back short, and says so in the log when the page cap
truncates — with both numbers.

**The API returns no URL field.** The link is built from the notice id
(`OP00190487`), and only from a notice id: project ids (`P175447`) sit in the
same response and render into a page that 404s. A dead link is worse than none,
because a dead link reads as checked.

### EU TED — `module: ted`

Two defects made every run a 400, and neither was visible in the status line
until 4xx bodies started being reported: the page limit was 250 against a
documented maximum of 100, and the country was the two-letter `JO` where the
API wants `JOR`.

`place-of-performance` was dropped from the query because its expert-search
spelling could not be confirmed, and an unknown field name is itself a 400. It
is still requested as a *response* field, where being absent costs nothing.

TED is EU-wide, so a full-text hit on "Jordan" is not evidence of a Jordan
tender. The country field decides; where TED gives none, its own title prefix
("Austria – …") is used to **reject**, never to admit.

### SAM.gov — `module: samgov`

Needs a free API key whose approval takes **one to four weeks**. Until
`SAM_API_KEY` is set the portal reports *not configured*, which is deliberately
distinct from *unavailable*: a paperwork delay is not a broken scraper, and
conflating them would cry wolf for a month.

### UK Find a Tender — `module: fcdo`

An OCDS API over the whole UK corpus, which is why country matching is on word
boundaries. Plain substring matching puts Jordanstown (County Antrim) and
Ammanford (Wales) in the report, and this is where it would happen.

---

## Tier 2 — HTML

### UNGM — `module: ungm`

The single richest Jordan source: UNDP, UNICEF, WFP, UNOPS, UNHCR and UNRWA all
publish here. `GET /Public/Notice` returns 141 KB of pure navigation — the rows
are not in the initial HTML — so the module posts to the site's own JSON search
filter, with `Countries` set to UNGM's numeric id for Jordan (`2395`, read out
of the page's `selNoticeCountry` dropdown), and pages it to the end. 69 notices
in about 12 seconds, no browser.

That replaced a headless browser scrolling a *worldwide* listing: forty scroll
passes read 615 rows and were still growing, to keep the three that were
Jordan.

Its `selectors`, `field_selectors` and `filter_to_jordan` are `code_owned`, and
the module says why for each. Two are worth repeating here:

- `table tbody tr` is deliberately **not** a selector. It matched six rows on
  the live page — the Su/Mo/Tu/We/Th/Fr/Sa cells of the date-picker widget.
- The publication-date selector is anchored to `.remainingDaysToDeadline`,
  which every row has, not to `.remainingDays`, which only browser-rendered
  rows have. Pinning it to the optional sibling worked until the search
  endpoint replaced the scroll loop, at which point every publication date
  silently became `None`.

`filter_to_jordan` is false because the module filters differently: a majority
of Jordan notices print "Multiple destinations" in the country cell rather than
a country name, and the generic text filter was dropping 51 of 70 of them.

### EBRD — `ebrd`

Two sources: the notices page on ebrd.com, and ECEPP, where the tender
documents and many of the consultancy assignments actually live. Either failing
is tolerated as long as the other works. Verified live: 4,012 notices scanned,
119 Jordan.

### EIB — `eib`

Corporate procurement and notices for EIB-financed projects in one listing;
Jordan appears mainly under the latter. Returns a bot wall from a data-centre
IP, so the selectors remain unverified.

### GIZ — `giz`

**The English page was removed after `--capture` showed it carries no listing
at all.** Its repeated blocks were `main-menu__container` (74) and
`main-menu__item` (33) — pure navigation. `ausschreibungen.giz.de` is the real
source and reads cleanly through the header-aware table layer.

**A high quality score is not a correct result.** That table won at quality
1.00, with six cells found and the header mapped correctly onto
posted / closing / title — and every deadline on the portal was garbage,
because one unclosed `<td>` nested the rest of each row inside the deadline
cell. Scores measure whether something *looks like* a listing; they cannot see
a single column being wrong. This is why `--capture` prints the
header-to-cell mapping and sample rows even when nothing wins.

German formatting is why `utils.money` handles dot-as-thousands and
`utils.dates` handles "15. Januar 2027": EUR 1.500.000 read as 1.5 would put a
real contract below the minimum value and delete it.

### KfW — `kfw`, read from GTAI

**KfW does not publish tender notices on kfw.de.** Germany Trade & Invest is
entrusted with publishing them, so the source is `gtai.de/en/trade/tenders`.
Pointing a scraper at kfw.de makes the portal report "unavailable" forever
while looking like an honest failure — which is worse than not having the
portal, because it is invisible. A test pins this.

### IsDB — `isdb`

Jordan is a member country, so IsDB-financed procurement appears regularly.
Some calls are restricted to member-country firms; those are flagged by the
eligibility detector and penalised, never dropped — a JV with a local partner
is a real and winnable route. Read cleanly live: 144 notices, none open for
Jordan that day.

---

## Tier 3 — announcements only

### Saudi Fund for Development — `sfd`

Publishes in Arabic and English, and many calls are restricted to Saudi firms
or Saudi-led joint ventures. Flagged, not excluded. Arabic content is kept in
the original and flagged for manual review. Times out from a data-centre IP.

### ADFD — `adfd`, `no_listing_reason`

**ADFD publishes no machine-readable tender listing.** The conclusion is
negative rather than pending, and it cost four URLs and two fetch strategies to
reach:

| URL | Result |
|---|---|
| `/english/Eservices/Tender/Pages/Procurementtenders.aspx` | legacy; 200, nothing but chrome |
| `/english/MediaCenter/News/Pages/default.aspx` | legacy; the same |
| `/en/what-we-do/tenders` | the current page. 28 KB, all mega-menu, zero rows from every layer |
| `/en/media-centre/news` | the same |

A headless browser was then tried, on the UNGM analogy, **and it did not
help**. The render plainly worked — the page grew to 34 KB and
`section.aos-animate` appeared, a class that only exists once Animate-On-Scroll
initialises in a real browser — and every layer still found zero rows. So the
listing is not hidden by JavaScript; it is not there. Playwright was removed
again rather than left in place looking useful.

The module used to *assert* that ADFD had no procurement database. That was
wrong, and wrong in the way that costs most: a confident comment explaining
away an empty result. It pointed at the news page instead, which reported
"layout change" on every run — a wrong URL wearing the costume of a scraper
bug. The tenders page is now primary and the news page is kept second, because
tenders for ADFD-financed projects are genuinely often issued by the
beneficiary government and announced as news.

`anchor_hint` is deliberately **absent**. It used to be `/News/`, which
silently excluded every tender link from the anchor layer. And the earlier
selector hints assumed `.aspx` meant SharePoint web parts; `--capture` showed a
Bootstrap rebuild, so `dfwp-item` and `ms-listviewtable` could never have
matched.

What cannot be distinguished from outside is "no open tenders today" from "the
listing needs an interaction to appear", so `no_listing_reason` says so rather
than implying certainty.

### JICA — `jica`, `no_listing_reason`

**JICA's Jordan office publishes no procurement page.** Chased down properly
rather than guessed at:

- The original URL 404s. JICA did restructure, moving country pages from
  `/<country>/english/office/others/` to `/english/overseas/<country>/others/`.
- Bangladesh and Indonesia answer on **both** schemes, so the new spelling is
  right and the old one still works where a page exists.
- Jordan 404s on **both**. Repeated searches surface procurement pages for
  Bangladesh, Indonesia, Côte d'Ivoire and the Balkan office, and never one for
  Jordan.

So this is not a broken scraper and no URL will fix it. Both spellings are kept
as sources: if JICA Jordan ever publishes a procurement page it will be at one
of them, and the portal starts working with no change at all.

**The office index was tried as a source and removed.** It exists and returns
200, which made it look like the sensible fallback, and it put two phantom
tenders straight into the report:

```
[22.5] Message from the Chief Representative   JICA | Unclassified
[22.5] Related Information                     JICA | Unclassified
```

Those are the page's own section headings. A clean, honest 404 became a listing
of navigation dressed as opportunities — strictly worse than the failure it
replaced. **An index page is not a listing**, and a test pins every JICA source
to a procurement page.

---

## `no_listing_reason`, and why it is not just a failure

A source with nothing to read is not a scraper that has stopped working.
Reporting it as one puts a permanent red line in every report, and that is how
a reader learns to ignore the status table — which is the alarm.

An entry with `no_listing_reason` set reports **`no listing`** instead of
**`unavailable`** when every source comes back empty, and `no listing` does not
count towards the ACTION NEEDED threshold. The underlying diagnosis is kept in
the reason after `Detail:`, so a genuine change — a bot wall, a transport error
— is still visible and still distinguishable from "there is nothing here".

Do not set it to quieten a portal that is merely broken. It is a claim about
the source, and both claims here took several runs and a browser to establish.
