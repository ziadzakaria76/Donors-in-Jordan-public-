# Jordan Tender Intelligence Monitor

Monitors 13 donor and IFI procurement portals for Jordan-related consulting
opportunities, scores them, and delivers a structured report by email.

---

## ⚠️ Verification status — read this first

**No scraper in this repository has ever run against a live page.** It was built
in an environment whose egress policy blocked all 13 portal domains with
`HTTP 403` at the proxy. That is a policy denial, not a transient failure, and
it was not worked around.

| | Status |
|---|---|
| **Verified against the live web** | **Nothing.** Zero portal domains were reachable. |
| **Verified offline against fixtures** | Extraction cascade, quality gate, value/date/country parsers, filtering, scoring, deduplication, the email body, all five output formats, delivery fallback, `--capture`, scraper resilience, the portal registry, and the four REST modules' response parsing against synthetic payloads — **459 checks** |
| **Verified in this environment (no portals)** | Dependency install, `pyflakes`, `--check-portals`, `--dry-run`, `--capture`, `--self-test` all run end to end and behave correctly under total portal failure |
| **Not verified at all** | Every portal URL · every CSS selector · **whether the real APIs return the shapes assumed** · the UNGM POST payload · email delivery (no credentials were present) |

On the REST modules specifically: their parsing is now exercised against payloads
in the shapes the documentation describes, which proves the parsing is correct
*given* those shapes. It does not prove the shapes are right. If an API returns
something different, these tests still pass and the portal still fails — though
it will fail with a diagnosed `PortalError` rather than silently returning
nothing, which is the property the tests do guarantee.

**The CSS selectors are guesses.** They are informed by the CMS each portal
appears to run, but not one has been checked against the live DOM. The same
applies to the API field names — the World Bank, TED, SAM.gov and Find a Tender
modules read several possible spellings for each field precisely because the
real ones could not be confirmed.

The quality gate stops a wrong selector from producing *bad* data — it falls
through to a class-independent layer instead. It cannot make a wrong selector
*right*. **Run `--capture` against each HTML portal before trusting this.**

The portal URLs could not be checked either. Several published lists of donor
procurement URLs are years out of date; treat these as a starting point.

---

## Quick start

```bash
pip install -r requirements.txt
cp .env.example .env        # then fill it in
python run.py --check-portals   # can this machine see the portals at all?
python run.py --dry-run         # scrape, filter, print — send nothing
python run.py --capture ungm    # confirm one portal's selectors
python run.py --send            # build, save, and email
```

## Deploying

**[Windows Server deployment guide](DEPLOYMENT-WINDOWS.md)** — Python setup,
Azure app registration with mailbox scoping, portal verification, and Task
Scheduler including the Amman/UTC offset table.

Nothing runs until it is deployed. This repository is source code, not a
running service, and no email is sent until `--send` is scheduled.

## Commands

| Command | What it does |
|---|---|
| `--check-portals` | Reachability of every enabled portal, with a diagnosed reason per failure |
| `--dry-run` | Full pipeline, printed. Sends nothing, records nothing as seen |
| `--send` | Builds the report, writes the files, emails it, then records what was sent |
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
| Delivery | Graph → SMTP → disk; recipients in `.env` |
| Report | Full detail, top 50 inline, the rest tabled |
| Outputs | Word, Excel, JSON, CSV, HTML — Word and Excel attached |
| Schedule | Weekdays 07:00, pinned to `Asia/Amman` |
| Alerting | Portal health in the subject line + a diagnosed status table |

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

The subject line carries portal health, because a subject reading
"0 opportunities" whether every portal failed or every portal worked lets a dead
monitor go unnoticed for weeks:

```
Jordan Tenders - 7 new opportunities
Jordan Tenders - no new opportunities (13/13 portals OK)
Jordan Tenders - 4 new opportunities, 3 of 13 portals unavailable
ACTION NEEDED: Jordan Tenders - all 13 portals unreachable
```

The body carries a per-portal table with the diagnosed cause and the URL to
check by hand.

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
python tests/run_all.py    # 459 checks, no network, no credentials
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
