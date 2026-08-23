# Syria Tender Intelligence Monitor

Monitors donor and IFI procurement portals for Syria-related consulting
opportunities, classifies them by delivery location, screens named parties
against sanctions lists, and delivers a ranked report by email.

Country-specific data lives in `profiles/syria.yml`. The code takes a profile as
an argument and hard-codes no country, so a second country is a second YAML
file, not a refactor.

---

## What is verified, and what is not

**Read this before trusting any output.** The environment this was built in
could not reach a single portal: every donor site, every API and every sanctions
list returned `403` at the network proxy, as did `example.com`. That is a policy
denial, not a bug to work around.

### Verified against the live web
**Nothing.** No scraper in this repository has ever run against a live page
here. Nobody should read "the tests pass" as "the scrapers work".

### Verified offline, against committed fixtures
- Country matching, including every documented trap (`Assyrian`, `Syriac`,
  `Assyrien`, `Damascus, MD`, the `سوري` stem, `.sy` vs `ministry.system`).
- Delivery-location classification into the four categories.
- The tri-state country gate, including the Blantyre regression and its
  counterpart.
- Date parsing: the ISO `T` guard across every ambiguous month/day pair, the
  UNGM countdown, German/French/Levantine and Gulf Arabic dates.
- Value parsing: European formats, magnitude words, implausible values, and the
  SYP redenomination flags.
- The extraction cascade against Drupal views, Bootstrap cards, header tables
  (including the unclosed `<td>`), Next.js JSON, site-level JSON-LD, RSS, RTL
  Arabic, a Cloudflare wall, a JavaScript shell and an over-broad selector.
- Report writers: Arabic through JSON and Excel, real RTL through Word, a
  zero-row workbook, the email overflow path, delivery without credentials.
- Sanctions screening logic against synthetic lists.

### Not verified at all
- **Every URL in this repository.** All of them are tier-3: plausible, current
  as of writing, unchecked. Run `--check-portals` first.
- **Every HTML portal's page structure.** No CSS selectors are shipped —
  they would be unverified guesses, and a guess that matches navigation is
  worse than none. Extraction relies on the class-independent layers; run
  `--capture PORTAL` to see what each page actually contains and what the
  cascade makes of it.
- **UNGM's numeric country id for Syria.** Not derivable, not guessable. The
  portal refuses to run until you set it (see below).
- **UNGM's search POST body.** Shipped as a documented skeleton, to be replaced
  field-for-field from a real network trace.
- **Every institutional fact** in the code comments: World Bank re-engagement
  and its 2026 projects, IsDB membership restoration (March 2025), EBRD and EIB
  status, the sanctions timeline (EO 14312, the Caesar repeal, EU/UK easing),
  and the SYP redenomination date. These were current when written and must be
  re-checked; several sit at or beyond the knowledge cutoff of the model that
  wrote them.

---

## First run

```bash
pip install -r requirements-dev.txt
cp .env.example .env          # fill in; .env is gitignored and must stay that way

python -m pytest tests/ -q                 # offline, no credentials needed
python -m pyflakes src/ tests/

PYTHONPATH=src python -m syria_monitor.cli --check-portals
PYTHONPATH=src python -m syria_monitor.cli --dry-run     # scrapes, prints, sends nothing
```

### Then do this, before expecting UNGM to work

UNGM is the richest single Syria source and it does **not** use ISO country
codes — it uses its own numeric ids, read from a 234-option dropdown. There is
no table to derive one from and no way to guess it, so the portal refuses to run
rather than send a guess that would return nothing silently:

```bash
PYTHONPATH=src python -m syria_monitor.cli --capture ungm
#   ... selNoticeCountry: 234 options
#   >>> set portals.ungm.country_id: NNNN    (Syrian Arab Republic)
```

Put that number in `config.yml` under `portals.ungm.country_id`, and while you
are there, replace `search_body()` in `src/syria_monitor/portals/ungm.py` with
the real request body from the capture's network trace.

---

## Running

| Command | What it does |
|---|---|
| `--check-portals` | Reachability only. No parsing. |
| `--dry-run` | Scrape, filter, rank, print. Writes nothing, sends nothing, leaves the seen-database untouched. |
| `--run` | Full run. Writes `output/*.docx`, `*.xlsx`, `*.json`. **Does not send.** |
| `--run --send` | Delivers by Microsoft Graph. |
| `--capture PORTAL` | Fetches live pages to `tests/fixtures/live/`, prints per-layer row counts and quality, which layer won, and the selectors the page actually uses. |
| `--self-test` | Pipeline over fixtures with the database and output directory redirected. |
| `--portal NAME` | Limit a run to one or more portals (repeatable). |

`--send` is deliberately separate from `--run`: review the files first.

---

## Configuration

`config.yml` holds run settings; `profiles/syria.yml` holds country data.

| Setting | Value | Why |
|---|---|---|
| Scope | `inside_syria` only | Cross-border, regional and refugee-hosting tenders are still classified, counted and written to the excluded list every run, so what is being left out stays auditable. Widening scope is a config change. |
| Sectors | all | No sector filter; the profile's `ranking_terms` rank instead, so a blank sector field never deletes a notice. |
| Keywords | none | Consulting terms rank rather than gate. |
| Minimum value | none | No floor, and notices with no published value are kept and flagged. Most donor notices omit value entirely. |
| Notice types | all | GPNs are kept and tagged `PIPELINE — not yet biddable`. |
| Lookback | all currently open | Posted date is reported, never used to exclude. SAM.gov still gets a rolling 364-day window because its API rejects longer ranges. |
| Deadlines | expired out, missing kept | A deadline of today counts as open. |
| New-only | off | Full open list every run; unseen tenders marked `NEW`. |
| Language | Arabic kept | Original script, flagged `ar`, real RTL in Word, Arabic terms in the ranking lexicon. |
| Eligibility | flag | Restricted tenders are kept with an eligibility badge. |
| Screening | flag | Hits are annotated, never excluded. |

### Sanctions screening

Screening output is **a triage aid, never legal clearance**. No counterparty is
ever reported as clear, and every report carries each list's fetch date — a
stale list that looks current is worse than no screening at all. Residual
designations remain in force notwithstanding the 2025–26 easing, and the Caesar
repeal carries 180-day presidential certifications, so re-verify the position
rather than treating any date in this repository as settled.

### Portals

Ten are built: World Bank, EU TED, SAM.gov, UK Find a Tender, UNGM, UNDP, Syria
Recovery Trust Fund, GIZ, IsDB and GTAI (which publishes KfW's notices — KfW
does not publish tenders on its own site).

**EBRD and EIB are deliberately absent.** Syria is eligible to join the EBRD but
is not a member and is not among its countries of operations; Syria was removed
from the EIB external-mandate eligible-country list by Delegated Act in April
2012 and has not been restored. Both are core to a Jordan build and neither
belongs here. Worth revisiting rather than treating as permanent: EBRD
membership is under active advocacy, and a proposed EU–UN guarantee window
involving EIB or EBRD has first transactions expected in 2027.

**Commercial aggregators are not built.** syriatenders.com, tendersontime.com
and rebuilding-syria.com resell notices, are frequently paywalled and stale,
sometimes restrict scraping in their terms, and their provenance is
unverifiable. UN Development Business and dgMarket are legitimate donor
publication channels rather than resellers, but UNDB is subscription-based —
check access before depending on either. SRTF publishes to both, which makes
them a useful completeness cross-check on that scraper.

---

## Email delivery (Microsoft Graph)

Register an application, grant `Mail.Send`, and put the credentials in `.env`.

> **`Mail.Send` as an application permission is tenant-wide.** The app can send
> as any mailbox in the tenant until you scope it:
>
> ```powershell
> New-DistributionGroup -Name "SyriaMonitorSenders" -Type Security `
>   -Members "reports@yourfirm.com"
> New-ApplicationAccessPolicy -AppId <client-id> `
>   -PolicyScopeGroupId "SyriaMonitorSenders@yourfirm.com" `
>   -AccessRight RestrictAccess -Description "Syria tender monitor"
> ```

Recipients live in `.env` (`REPORT_TO`, `REPORT_CC`), never in `config.yml` —
this is a public repository.

---

## Schedule

`0 3 * * *` UTC = **06:00 Europe/Amman**, daily. GitHub Actions cron is always
UTC; Amman is UTC+3 year-round, so no DST arithmetic is needed.

Two workflows:
- **CI** — pyflakes plus the full offline suite on Python 3.11 and 3.12.
- **Run monitor** — `workflow_dispatch` (triggerable from a phone) plus the
  daily schedule, uploading the Word, Excel and JSON files as run artifacts.

## Knowing when it breaks

Portal health is in the subject line, because a monitor that says
"0 opportunities" whether every portal failed or nothing matched goes unnoticed
for weeks:

```
Syria tenders -- 6 new, 34 open | all 10 portals OK
Syria tenders -- no new opportunities, 34 open | all 10 portals OK
Syria tenders -- 2 new, 19 open | WARNING: 3 portal(s) down (UNGM, GIZ, IsDB)
ACTION NEEDED: all portals unreachable -- no data this run
```

Each run also reports the full classification split — inside-Syria,
cross-border, regional, refugee-hosting-only — because a single total says
nothing about whether the classifier is working.
