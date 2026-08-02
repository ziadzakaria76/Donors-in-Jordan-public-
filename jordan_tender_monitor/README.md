# Jordan Tender Intelligence Monitor

Automated multi-agent system that monitors 13 donor and IFI procurement portals
for Jordan-related consulting opportunities, scores them for relevance, and
delivers a structured report by email.

Four agents run in sequence:

| Agent | Module | Responsibility |
|---|---|---|
| 1. Scrapers | `portals/*.py` | Fetch notices from each portal, normalise to one schema |
| 2. Filter & scorer | `agents/filter.py` | Filter, score 0–100, deduplicate across portals |
| 3. Reporter | `agents/reporter.py` | Build the email body and the Excel/JSON/CSV/HTML files |
| 4. Emailer | `agents/emailer.py` | Send via Microsoft Graph, falling back to SMTP, then to disk |

---

## Current configuration

Set during the build interview; all of it lives in `config.py` and can be
changed without touching any other file.

| Setting | Value |
|---|---|
| Sectors | All — no sector filter (sector is inferred for labelling only) |
| Keywords | No keyword filter; a ranking lexicon is used for scoring only |
| Minimum value | USD 100,000 — tenders with no published value are kept |
| Notice types | All |
| Lookback | All currently open (no posted-date cutoff) |
| Expired tenders | Excluded; notices with no published deadline are kept and flagged |
| New-only mode | **On** — each run reports only tenders not seen before |
| Language | Arabic and English both included; Arabic flagged for manual review |
| Eligibility | National-only tenders flagged and penalised 25 points, not excluded |
| Portals | All 13 |
| Email | Microsoft Graph → Office 365 SMTP → save-to-disk |
| Report format | Full details per tender |
| Outputs | Excel (colour-coded), JSON, CSV, HTML |
| Schedule | Daily at 07:00 |

### Two deliberate deviations from a literal reading of the brief

1. **Scoring weights are renormalised.** The brief specifies keyword 40 /
   sector 30 / value 15 / urgency 15. With "all sectors" selected, every tender
   scores identically on the sector component, so it carries no information —
   it is dropped and the rest renormalise to keyword 57.1 / value 21.4 /
   urgency 21.4. Set `TARGET_SECTORS` in `config.py` to bring it back.
2. **A ranking lexicon replaces the keyword filter.** You chose no keyword
   filter, which would flatten the 40-point keyword component and leave
   ranking driven only by value and deadline. `RANKING_LEXICON` in `config.py`
   is therefore used to *score* consulting-shaped language — it never removes a
   tender. It includes Arabic terms so Arabic notices are not systematically
   ranked last.

---

## 1. Prerequisites

- Python 3.11 or newer
- pip
- Optional: `playwright install chromium` — only needed for JavaScript-rendered
  pages (UNGM, EBRD's ECEPP). Without it those scrapers fall back to static
  HTML and may return fewer results.
- Outbound HTTPS access to the portal domains (see Troubleshooting).

## 2. Setup

```bash
git clone <this-repo>
cd jordan_tender_monitor

python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate

pip install -r requirements.txt
playwright install chromium        # optional

cp .env.example .env               # then fill in the values you have
```

`.env` is git-ignored. Every variable in it is optional — anything left blank
just disables the feature that needs it, and the run continues.

## 3. SAM.gov API key

Free, but approval typically takes **1–4 weeks**.

1. Go to <https://sam.gov> and select **Sign In**.
2. Create a **login.gov** account and complete the individual registration.
3. Sign in to SAM.gov, open **Account Details**.
4. Select **Request Public API Key** and complete the request.
5. When the key arrives, add it to `.env`:
   ```
   SAM_API_KEY=your-key-here
   ```

Until then the run prints the registration instructions, skips SAM.gov, and
reports it as unavailable. Nothing else is affected.

## 4. Azure app registration for Microsoft Graph email

Needs an Azure AD / Entra ID administrator.

1. **Azure Portal → Microsoft Entra ID → App registrations → New registration**
   - Name: `Jordan Tender Monitor`
   - Supported account types: single tenant
2. From the app's Overview page, copy:
   - **Directory (tenant) ID** → `AZURE_TENANT_ID`
   - **Application (client) ID** → `AZURE_CLIENT_ID`
3. **Certificates & secrets → New client secret.** Copy the secret **Value**
   (not the Secret ID) → `AZURE_CLIENT_SECRET`. It is shown only once.
4. **API permissions → Add a permission → Microsoft Graph → Application
   permissions → `Mail.Send` → Add**, then **Grant admin consent**.
5. Set `SENDER_EMAIL` to the mailbox the report is sent from, and
   `EMAIL_RECIPIENTS` to who should receive it.
6. **Ask IT to apply an ApplicationAccessPolicy** restricting the app to that
   one mailbox. `Mail.Send` as an application permission is otherwise
   tenant-wide — it would let the app send as anyone in the tenant. Least privilege
   matters here and security review will ask about it.

   ```powershell
   New-ApplicationAccessPolicy -AppId <client-id> `
     -PolicyScopeGroupId reports@example.com `
     -AccessRight RestrictAccess `
     -Description "Jordan Tender Monitor - single mailbox"
   ```

If Graph is not configured the emailer falls back to Office 365 SMTP
(`SMTP_USER` + app password), and if that is also unavailable it saves the
report to `output/` and prints the path. The run never fails because email is
unavailable.

## 5. Run once

```bash
python run.py --dry-run      # scrape and print, write nothing, send nothing
python run.py --save-only    # build and save files, send no email
python run.py --send         # build, save, and email
python run.py                # build, save, then prompt: send / save / cancel
```

Other flags:

| Flag | Effect |
|---|---|
| `--check-portals` | Reachability probe only; parses nothing |
| `--capture PORTAL` | Fetch a portal's live pages, save them as fixtures, and report which extraction layer and selectors actually work |
| `--self-test` | Runs the full pipeline against built-in fixtures, no network |
| `--portals worldbank,ungm` | Restrict the run to specific portals |
| `--new-only` | Force new-only mode on for this run |
| `--reset-db` | Clear the seen-tender database |
| `--cron` | Print cron / Task Scheduler / `schedule` setup |
| `-v` | Debug logging |

### Testing offline

```bash
python tests/run_all.py             # 164 checks, no network, no credentials
```

| Suite | Covers |
|---|---|
| `test_extraction.py` (84) | Getting tenders *out of a page* — every extraction layer, the quality gate, failure diagnosis, pagination, multilingual dates and values, real notice-URL patterns |
| `test_pipeline.py` (54) | What happens *afterwards* — filters, scoring, eligibility penalty, deduplication, report rendering, Excel/CSV/JSON writers, email fallback, the seen-tender tracker |
| `test_capture.py` (26) | `--capture` itself — every HTML portal captures each source, reports all six layers, names the winner and suggests selectors taken from the page; plus unreachable sources, bot walls, and API portals being refused |

`tests/fixtures/` holds pages in the CMS shapes the donor portals actually use —
Drupal views, Bootstrap cards, header tables, Next.js `__NEXT_DATA__`, JSON-LD,
RSS, RTL Arabic, German date and value formats — plus a Cloudflare wall, a
JavaScript shell, and a page where an over-broad selector matches navigation
instead of the real listing.

The pipeline suite is deliberately adversarial: empty input, a tender with every
optional field `None`, zero keyword matches, the deadline boundary, duplicate
collapse across portals, the email overflow path, and delivery with no
credentials. It redirects the database and output directory to a temp folder, so
running it never disturbs `data/seen_tenders.db` or `output/`.

Run it after touching anything in `portals/` or `agents/`.

CI runs the same suites on every push and pull request
(`.github/workflows/tests.yml`) across Python 3.11 and 3.12, plus a pyflakes
lint, an end-to-end `--self-test` run, and a guard that fails the build if
`.env` is ever committed. Because the suites are offline by design, CI needs no
network access and no credentials.

When a portal does break, the fastest repair loop is to save its live page into
`tests/fixtures/`, point a test at it, and work until the cascade extracts the
rows. That converts a one-off fix into a permanent regression test.

## 6. Recurring schedule

`python run.py --cron` prints all three options filled in with real paths. The
configured schedule is daily at 07:00.

**Python, no OS setup** — keeps a process running:
```bash
python run.py --schedule
```

**Linux / macOS cron** — `crontab -e`:
```
0 7 * * *  cd /path/to/jordan_tender_monitor && /path/to/python run.py --send >> cron.log 2>&1
```

**Windows Task Scheduler**:
```
schtasks /Create /TN "JordanTenderMonitor" /TR "\"C:\path\to\python.exe\" \"C:\path\to\run.py\" --send" /SC DAILY /ST 07:00
```

To change the frequency, edit `SCHEDULE_MODE` in `config.py`
(`once` / `daily` / `weekly` / `mon_thu`) and re-run `--cron`.

## 7. Reset the seen-tenders database

New-only mode is **on**, so each run reports only tenders it has not reported
before. The first run after a reset (or on a fresh machine) reports everything,
because the database starts empty; from the second run onward you get only what
changed.

To make the next run re-report everything:

```bash
python run.py --reset-db
```

Or delete the file directly — it is recreated automatically:

```bash
rm data/seen_tenders.db
```

`data/seen_tenders.db` is git-ignored, so it is per-machine. Moving the monitor
to a new host resets the history and the first run there will be a full listing.

To go back to full listings on every run, set `NEW_ONLY_MODE = False` in
`config.py`. A single run can override the config either way with `--new-only`.

`--self-test` never reads or writes this database: it runs on fixtures, and
letting fixture IDs in would suppress real tenders later.

## 8. Troubleshooting

**All portals report "unreachable".**
Outbound HTTPS is being blocked — a corporate proxy, a VPN, or a sandbox egress
policy. Confirm with `python run.py --check-portals`. If you are behind a
corporate proxy, set `HTTPS_PROXY` before running. This system needs direct
outbound access to the 13 portal domains; it cannot work from a network that
blocks them.

**One portal reports "unavailable — check manually".**
Expected and by design — but read *which* reason it gives, because they need
different fixes:

| Message | Meaning | Fix |
|---|---|---|
| `blocked by bot protection` | Cloudflare/Incapsula is refusing automated access | Install Playwright, or run from a different network |
| `requires JavaScript` / `JavaScript shell` | Page has no server-rendered content | `playwright install chromium` |
| `no extraction layer … could parse a notice row` | Genuine layout change | Update that module's `SELECTORS` / `HREF_PATTERN` |
| `Transport errors: …` | Network/DNS/proxy problem | Check egress to that domain |

When a page loads but yields no parseable rows, the scraper raises rather than
silently reporting zero Jordan tenders. The portal gets a cross in the report
and the run continues.

**No results at all, but portals are green.**
Check the filters. The most common cause is `MIN_VALUE_USD` combined with
`KEEP_UNKNOWN_VALUE = False`. Run `--dry-run` — the rejection breakdown prints
exactly how many tenders each filter removed and why.

**Graph email fails with `AADSTS700016` / `invalid_client`.**
The app registration or secret is wrong, or the secret has expired (client
secrets expire — 24 months maximum). Re-check `AZURE_CLIENT_ID` and generate a
new secret.

**Graph email fails with `ErrorAccessDenied`.**
`Mail.Send` was added as a *delegated* permission instead of an *application*
permission, admin consent was not granted, or the ApplicationAccessPolicy
excludes the sender mailbox.

**SMTP fails with `535 5.7.139 Authentication unsuccessful`.**
Basic auth / SMTP AUTH is disabled on the mailbox — the default in many tenants. Use Graph
instead; IT generally will not re-enable SMTP AUTH.

**SAM.gov returns HTTP 429.**
Public keys are limited to 10 requests per day. Wait, or request a higher tier.

**Timeouts on a slow network.**
Raise `REQUEST_TIMEOUT` in `config.py`. Retries already use exponential backoff
(3 attempts, 5-second base). `POLITE_DELAY_SECONDS` enforces a 2-second gap
between requests to the same host — do not remove it, it is what keeps the
scrapers from being rate-limited or blocked.

**The email looks truncated in Outlook.**
Outlook clips messages over about 100 KB. The reporter renders full detail for
the top `MAX_INLINE_TENDERS` (default 50) and lists the remainder as a compact
table, with everything in the attached workbook. Lower that number in
`config.py` if you still see clipping.

## Security

- `.env` is git-ignored and must never be committed. `.gitignore` also excludes
  `*.db`, `output/`, `__pycache__/` and `*.pyc`.
- Credentials are never printed or written to `tender_monitor.log` — only the
  method attempted and whether it succeeded.
- Scope the Azure app to a single mailbox (step 4.6). Do not leave a tenant-wide
  `Mail.Send` grant in place.
- Rotate the client secret before it expires and treat it as a secret in every
  environment you deploy to.

## Project layout

```
jordan_tender_monitor/
├── agents/
│   ├── scraper.py      # Agent 1 orchestration: parallel scraping, per-portal status
│   ├── filter.py       # Agent 2: filter, score, deduplicate
│   ├── reporter.py     # Agent 3: email body + Excel/JSON/CSV/HTML
│   ├── emailer.py      # Agent 4: Graph -> SMTP -> file
│   └── tracker.py      # SQLite seen-tender tracker
├── portals/
│   ├── base.py         # polite HTTP, retries, multilingual date/value parsing
│   ├── htmlkit.py      # extraction cascade, feeds, diagnosis, pagination
│   ├── harvester.py    # shared scrape pipeline used by all HTML portals
│   ├── worldbank.py ted.py samgov.py          # REST APIs
│   ├── ebrd.py eib.py ungm.py giz.py kfw.py isdb.py fcdo.py   # HTML scrapers
│   └── sfd.py adfd.py jica.py                 # announcement scrapers (limited)
├── data/seen_tenders.db
├── output/
├── tests/
│   ├── fixtures/           # saved pages in each CMS shape, incl. failure modes
│   ├── test_extraction.py  # page -> tenders
│   ├── test_pipeline.py    # tenders -> filtered, scored, reported, delivered
│   └── run_all.py
├── config.py
├── fixtures.py         # sample tenders for --self-test
├── run.py
├── requirements.txt
├── .env.example
└── .gitignore
```

## Portal reliability

| Portal | Method | Expected reliability |
|---|---|---|
| World Bank | REST API, no key | High |
| EU TED | REST API, no key | High |
| SAM.gov | REST API, key required | High once a key is approved |
| UK FCDO / Find a Tender | OCDS API, HTML fallback | High |
| UNGM | Search endpoint, Playwright fallback | Medium — richest Jordan source |
| EBRD, EIB, GIZ, KfW, IsDB | HTML scraping | Medium — markup changes break these first |
| Saudi Fund, ADFD, JICA | Announcement scraping | Low — no structured procurement database |

### Source URL validation (August 2026)

Several source URLs inherited from the original brief pointed at pages that no
longer carry notices. These were corrected against the live web:

| Portal | Was | Now |
|---|---|---|
| EBRD | `ebrd.com/work-with-us/procurement.html` | `ebrd.com/home/work-with-us/project-procurement/procurement-notices.html` + ECEPP `noticeSearchResults.html` |
| EIB | `eib.org/en/projects/procurement/` | `eib.org/en/about/procurement/all/index.htm` |
| GIZ | `giz.de/en/mediacenter/117.html` (old media centre) | `giz.de/en/partner/contractor/tenders` + `ausschreibungen.giz.de` |
| **KfW** | KfW's own site (carries *regulations*, not notices) | **`gtai.de/en/trade/tenders`** — GTAI is formally entrusted with publishing KfW tender notices |
| IsDB | `isdb.org/procurement` | `isdb.org/project-procurement/tenders` |
| SFD | `sfd.gov.sa/en/tenders` | `sfd.gov.sa/en/tenders-view` |
| JICA | generic tender index | country-office page `jica.go.jp/jordan/english/office/others/procurement.html` |

Confirmed unchanged: World Bank `api/v2/procnotices` (open, no auth), Find a
Tender `api/1.0/ocdsReleasePackages` (cursor pagination), UNGM notice
permalinks `ungm.org/Public/Notice/{id}`.

`tests/test_extraction.py` asserts every portal's `HREF_PATTERN` matches real
notice permalinks observed on that portal — the one part of the scrapers checked
against the live web rather than against fixtures.

**Limit of this validation.** It confirms *which URLs to request* and *what
notice links look like*. It does **not** confirm CSS classes or DOM structure —
no channel available from the build environment returns page markup. The
selector hints in each module are therefore informed guesses.

Two things address that directly: the quality gate (below) stops a wrong guess
from doing damage, and `--capture` turns confirming them into a one-command job.

### Confirming selectors against a live page

```bash
python run.py --capture ebrd
```

For each of that portal's sources this fetches the live page, saves it to
`tests/fixtures/live/`, and prints how every extraction layer performed:

```
  layer         rows  quality
  json             0     0.00
  selectors        0     0.00     <- the guess missed
  tables           0     0.00
  structure       24     0.92     <- this one worked
  anchors         31     0.55
  chosen: structure (24 rows)
  selectors this page actually uses: ['div.notice-row', "div[class*='notice-row']"]
```

Paste the suggested selectors into that module's `SELECTORS` and re-run. Commit
the saved page and it becomes a permanent regression fixture, so the next
redesign is caught by the test suite rather than by a silent empty report.

Run it once per HTML portal on first use — it takes about a minute each and
converts the one genuinely unverified part of this system into a known quantity.

### Why a wrong selector guess is survivable

Selectors run *before* the class-independent layers, so an over-broad guess —
bare `article`, `table tbody tr` — could match navigation, teasers or a
related-documents table and short-circuit the layer that would have worked.

Each layer's rows are therefore scored for "listing-likeness" (0–1) and a layer
must clear `QUALITY_THRESHOLD` (0.5) to win; otherwise the cascade keeps
looking. Carrying a published or closing date is weighted most heavily at 0.40,
because it is the single trait separating a notice listing from navigation.
Distinct URLs, distinct titles and row count make up the rest. If no layer
clears the bar the best-scoring one is still returned, so a marginal page yields
something rather than nothing.

### How the HTML scrapers resist redesigns

Every scraper runs the same cascade (`portals/htmlkit.py`), most structured
first, and takes the first layer that yields rows:

| Layer | Survives a redesign? |
|---|---|
| 1. RSS/Atom feed | Yes — a published contract |
| 2. Embedded JSON (JSON-LD, `__NEXT_DATA__`, drupalSettings) | Yes — data, not presentation |
| 3. CSS selectors | No — fastest while the markup holds (gated, see above) |
| 4. Header-aware tables | Mostly — keys off "Deadline"/"Published" column names |
| 5. Structural inference | Yes — finds the repeated sibling block, ignoring class names |
| 6. Anchor URL pattern | Mostly — keys off the notice URL shape |

Layers 1, 2 and 5 depend on no class name at all, so a portal has to change
substantially before it goes dark. Pagination is followed (`rel="next"`, up to
`MAX_PAGINATION_PAGES`), and notices missing a deadline on the listing page get
it recovered from their own page within a per-portal request budget
(`DETAIL_FETCH_BUDGET`) so politeness limits are respected.

Adding or repairing a portal means editing `SOURCES` and `SELECTORS` in that
module; the pipeline itself lives in `portals/harvester.py`.

**Expected runtime.** Each portal now tries several sources and follows
pagination, with a 2-second gap enforced per host. A healthy full run takes
roughly 3–8 minutes on 5 workers; a run where portals are unreachable takes
longer, because each source is retried three times with exponential backoff.
That is fine for a daily job. If you need it faster, lower
`MAX_PAGINATION_PAGES`, set `ENRICH_FROM_DETAIL = False`, or raise `MAX_WORKERS`
— but do not lower `POLITE_DELAY_SECONDS`, which is what keeps these scrapers
from being rate-limited or blocked outright.

The last group has no procurement database at all. ADFD items in particular are
press releases about financing agreements — leads that procurement may follow,
not live tenders — and are labelled as such.
