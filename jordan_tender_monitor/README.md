# Jordan Tender Intelligence Monitor

Monitors 13 donor and IFI procurement portals for Jordan-related consulting
opportunities, scores them, and writes a Word bid-review pack and an Excel
working file to disk.

---

## Verification status — read this first

**The scrapers ran against live pages for the first time on 3 August 2026.**
Before that date nothing here had ever touched a real portal; the build
environment blocked all 13 domains.

| | Status |
|---|---|
| **Verified against the live web** | EBRD (4,004 notices scanned, 119 Jordan) and the World Bank API, both returning correct Jordan results. UK Find a Tender and IsDB read cleanly and currently have no open Jordan notices. |
| **Verified offline against fixtures** | Extraction cascade, quality gate, parsers, filtering, scoring, deduplication, reporting, all output formats, alerting, `--capture`, scraper resilience — **606 checks** |
| **Diagnosed and reworked** | UNGM — both HTTP routes are dead ends (POST search: 395 bytes; GET listing: 141 KB of pure navigation, no notices). It now renders in a headless browser. GIZ — the English giz.de page carries no listing at all and has been dropped; the German portal reads cleanly at quality 1.00. |
| **Known broken, live** | EU TED (HTTP 400) · JICA (404, URL moved) · ADFD (no listing found) · GIZ deadline column mis-mapped |
| **Blocked by the site** | EIB and KfW/GTAI return bot walls from a data-centre IP; Saudi Fund times out |
| **Still unverified** | The CSS selectors for every portal that has not yet returned a clean listing |

### What the first live run taught us

**Never trust a source's own country filter.** The World Bank API accepts
`countryshortname=Jordan` and ignores it, returning worldwide notices. That
module was the only one skipping `jordan_only()` — on the strength of a comment
I wrote justifying the omission — so the first report led with a Caribbean
education project and roughly 140 of 259 entries were not Jordan. Every module
now filters client-side regardless, and a test enforces it structurally.

**A count alone cannot diagnose a portal.** Five portals reported `OK: 0` and
the number could not distinguish "returned nothing" from "returned 500
worldwide notices, none Jordan". Portal health now carries the pre-filter
count, which turned those five identical zeroes into five different diagnoses
in a single run.

## Quick start

```bash
pip install -r requirements.txt
pip install -r requirements-browser.txt && playwright install chromium  # UNGM only
cp .env.example .env        # then fill it in
python run.py --check-portals   # can this machine see the portals at all?
python run.py --dry-run         # scrape, filter, print — change no state
python run.py --capture ungm    # confirm one portal's selectors
python run.py --run             # the real run: write the files into output/
```

The second line is optional and needed by exactly one portal. UNGM builds its
listing in JavaScript, so no HTTP fetch can read it. Skip it and UNGM reports
`unavailable` with those two commands as its reason; the other twelve portals
are unaffected. It costs roughly 400 MB of browser, which is why it is not in
`requirements.txt`.

## Deploying

**[Run it from your phone](RUN-FROM-YOUR-PHONE.md)** — a GitHub Actions workflow
with a tappable Run button, a weekday schedule, results rendered on the run page
and the files attached as artifacts. Nothing to install, and a failed run is the
alert.

**[Windows Server deployment guide](DEPLOYMENT-WINDOWS.md)** — Python setup,
Azure app registration with mailbox scoping, portal verification, and Task
Scheduler including the Amman/UTC offset table.

Nothing runs until it is deployed. This repository is source code, not a
running service, and no email is sent until `--send` is scheduled.

## Commands

| Command | What it does |
|---|---|
| `--check-portals` | Reachability of every enabled portal, with a diagnosed reason per failure |
| `--dry-run` | Full pipeline, printed. Writes the files but records nothing as seen |
| `--run` (alias `--send`) | The real run: writes the Word and Excel files into `output/` and records what was reported |
| `--capture PORTAL` | Fetches a portal's live pages, saves them under `tests/fixtures/live/`, and reports per-layer row counts and quality, which layer won, and the selectors the page actually uses |
| `--self-test` | Runs the whole pipeline on offline fixtures in a temp directory |
| `--reset-db` | Forgets every reported tender, so the next run reports in full once |
| `--schedule` | Runs continuously on the configured schedule |
| `--only PORTAL...` | Restricts a run to named portals |

## How it is configured

Everything is in [`config.py`](config.py), with each setting labelled by the
interview question it answers.

| | Setting |
|---|---|
| Sectors | All. Tagged for grouping, never used to filter |
| Keywords | No filter. An Arabic-inclusive lexicon drives ranking only |
| Minimum value | $100k **on published values only**; unknown values kept and flagged |
| Notice types | All; the type is shown as a label |
| Lookback | None — everything currently open |
| Deadlines | Closed excluded (today counts as open); undated kept and flagged |
| New-only | On, SQLite-backed |
| Language | Arabic included in the original, flagged for manual review |
| Eligibility | National-only flagged and penalised 25 points, never excluded |
| Portals | All 13, tiered by reliability |
| Delivery | **Files on disk.** Email is off (`EMAIL_METHOD = "none"`) |
| Report | Full detail, top 50 inline, the rest tabled |
| Outputs | **Word and Excel**, written to `output/` |
| Schedule | Weekdays 07:00, pinned to `Asia/Amman` |
| Alerting | Portal health in the **filename** + a status page in both documents, plus an optional ACTION NEEDED email on total failure |

### Two settings worth understanding

**Unknown values are kept.** Most donor notices publish no value at notice
stage — UNGM, GIZ and EBRD almost never do. Dropping them against the $100k
floor would remove the majority of the pipeline, and the report would look
perfectly healthy while doing it. The floor applies only when a value was
actually published.

**Scoring weights renormalise.** A component whose filter is disabled awards
every tender identical points and carries no information. With all sectors
selected, the sector component is dropped and the rest renormalise to 100:
keyword 57.1 / value 21.4 / urgency 21.4.

## Surviving site redesigns

Each page runs through six layers, and the first whose rows score as a genuine
notice listing wins:

1. **RSS/Atom feed** — a published contract; survives redesigns
2. **Embedded JSON** — JSON-LD, `__NEXT_DATA__`, `drupalSettings`
3. **CSS selectors** — fast while the markup holds
4. **Header-aware tables** — maps Deadline/Published/Value columns to fields
5. **Structural inference** — the repeated sibling block, ignoring classes
6. **Anchor URL pattern** — last resort

Layers 1, 2 and 5 use no class names at all.

**The quality gate is the point.** Selectors run before the class-independent
layers, so an over-broad guess like bare `article` will match a navigation menu
and short-circuit the layer that would have worked. Each layer's rows are scored
and must clear a threshold. Carrying a date is weighted most heavily and gated
outright — every real listing dates its rows; almost no nav menu does. If no
layer clears the bar, the best one is returned labelled `BELOW QUALITY GATE`,
because a weak result you can see beats a silent zero.

Failures are diagnosed apart, because each needs a different fix:

| Diagnosis | Fix |
|---|---|
| bot wall (Cloudflare/Incapsula) | different network, or Playwright |
| JavaScript shell | `playwright install chromium` |
| layout change | update selectors — run `--capture` |
| transport error | wrong URL, or the host is blocked |

## Portals

**Tier 1 — REST APIs.** World Bank · EU TED · SAM.gov · UK Find a Tender.

SAM.gov needs a free API key with **1–4 weeks** approval. Until `SAM_API_KEY` is
set it reports as *not configured*, which is deliberately distinct from
*unavailable* — a paperwork delay is not a broken scraper, and conflating them
would cry wolf for a month.

**Tier 2 — HTML.** UNGM (the richest Jordan source: UNDP, UNICEF, WFP, UNOPS,
UNHCR, UNRWA) · EBRD + ECEPP · EIB · GIZ + ausschreibungen.giz.de · KfW · IsDB.

**KfW does not publish tender notices on kfw.de.** Germany Trade & Invest is
entrusted with them, so the source is `gtai.de/en/trade/tenders`. Pointing a
scraper at kfw.de makes the portal report "unavailable" forever while looking
like an honest failure.

**Tier 3 — announcements only.** Saudi Fund · ADFD · JICA.

**ADFD has no procurement database at all** — only project news. It is expected
to be quiet, and the report labels it announcement-only so a quiet Tier 3 portal
is never mistaken for a broken one.

## Knowing the difference between quiet and broken

**The filename states the run's health.** With output going to disk rather than
an inbox, a total outage and a quiet week both leave a file behind — and
identically-named files make a dead monitor invisible until someone asks why a
bid was missed. The folder listing has to show the difference:

```
jordan_tenders_20260803_0700_7-opportunities.docx
jordan_tenders_20260803_0700_no-new-opportunities-13-of-13-portals-OK.docx
jordan_tenders_20260803_0700_4-opportunities-3-of-13-portals-unavailable.docx
jordan_tenders_20260803_0700_ACTION-NEEDED-all-13-portals-unreachable.docx
```

Inside, the Word pack opens with the run status in words, and the Excel file
carries a **Run status** sheet listing every portal, its diagnosed failure
reason, and the URL to check by hand.

### The ACTION NEEDED alert

Files cover every case but one: **a scheduler that stops firing produces no
file**, and with no email arriving there is nothing to notice. That gap is what
the alert closes.

It fires only when a run could not read its sources — by default when *every*
portal is unreachable. It is short, carries no attachments, names each failure
with the URL to check by hand, and says what to run next. A healthy run sends
nothing, so an alert in your inbox always means act.

```bash
python run.py --test-alert    # prove the path works before relying on it
```

Alerts need mail credentials in `.env`, which file-only output otherwise
removes — read the `Mail.Send` scoping note under Security before granting it.
Leave the credentials blank and everything still works; you just check the
folder yourself. When alerting is enabled but cannot send, every run says so up
front rather than letting you discover it at the moment it matters.

Set `ALERT_ON_PARTIAL_BROKEN = 4` in `config.py` to also alert when four or
more portals fail. The default is total-outage-only, because one flaky portal is
already visible in the filename and does not need to interrupt anyone.

## Security

**`.env` is never committed.** `.gitignore` covers `.env`, `*.db`, `output/`,
`__pycache__/`, `*.pyc` and captured live pages. Credentials are never printed
or logged — the Graph failure path logs the error code alone. Recipients live in
`.env` rather than `config.py` because this repository is public and git history
would keep committed addresses even after deletion.

**If `Mail.Send` is granted as an Azure *application* permission it is
tenant-wide.** That app registration can then send mail as *any mailbox in your
organisation*, so a leaked client secret becomes an organisation-wide
mail-sending capability. Scope it to one mailbox:

```powershell
New-ApplicationAccessPolicy -AppId <client-id> `
  -PolicyScopeGroupId tender-monitor@yourdomain.com `
  -AccessRight RestrictAccess `
  -Description "Restrict Jordan tender monitor to its own mailbox"
```

Prefer a delegated permission if your tenant allows it.

## Politeness

Two seconds between requests to the same host, a realistic User-Agent, and three
retries with exponential backoff. Do not lower the delay to speed runs up —
getting the IP blocked costs far more time than it saves.

## Tests

```bash
python tests/run_all.py    # 606 checks, no network, no credentials
```

State is redirected to a temp directory before `config` is imported, so no test
can touch the real seen-tenders database. That matters: a diagnostic which wrote
fixture IDs into it would make the next live run report nothing, and a monitor
reporting nothing looks exactly like a broken one.

CI runs the suite plus `pyflakes` on Python 3.11 and 3.12, on pushes to `main`
and on pull requests.

## Schedule

Weekdays at 07:00 pinned to `Asia/Amman`. Jordan is **UTC+3 year-round** — it
abolished DST in 2022 — so 07:00 on a UTC host would fire at 10:00 in Amman. The
timezone is pinned rather than inherited, so moving the machine cannot silently
shift the run by three hours.

To use cron instead of `--schedule`:

```cron
0 4 * * 1-5  cd /path/to/jordan_tender_monitor && python run.py --send
```
