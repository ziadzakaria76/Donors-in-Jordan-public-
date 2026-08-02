# Jordan Tender Intelligence Monitor

Automated multi-agent system that monitors 13 donor and international financial
institution procurement portals for Jordan-related consulting opportunities,
scores them for relevance, and delivers a structured report by email.

Full documentation: **[`jordan_tender_monitor/README.md`](jordan_tender_monitor/README.md)**

## What it does

Four agents run in sequence:

| Agent | Responsibility |
|---|---|
| Scrapers | Fetch notices from each portal, normalise to one schema |
| Filter & scorer | Filter, score 0–100, deduplicate across portals |
| Reporter | Build the email body and Word / Excel / JSON / CSV / HTML outputs |
| Emailer | Send via Microsoft Graph, falling back to SMTP, then to disk |

**Portals covered:** World Bank, EU TED and SAM.gov (REST APIs); UK Find a
Tender (OCDS API); UNGM — covering UNDP, UNICEF, WFP, UNOPS, UNHCR and UNRWA —
plus EBRD, EIB, GIZ, KfW and IsDB (HTML); Saudi Fund, ADFD and JICA
(announcements).

A portal that fails is skipped with a diagnosed reason and reported as
unavailable. It never aborts the run, and never silently reports zero tenders.

## Quick start

```bash
pip install -r jordan_tender_monitor/requirements.txt
cp jordan_tender_monitor/.env.example jordan_tender_monitor/.env   # then fill it in
cd jordan_tender_monitor

python run.py --check-portals   # are the portals reachable from here?
python run.py --dry-run         # scrape and print, send nothing
python run.py --send            # build, save, and email
```

Everything is configured in [`config.py`](jordan_tender_monitor/config.py):
sectors, keywords, minimum contract value, notice types, lookback window,
language handling, eligibility rules, which portals to poll, report format and
schedule.

## Design note: surviving site redesigns

The HTML scrapers do not depend on CSS class names alone. Each page runs through
a six-layer cascade — RSS feed, embedded JSON, CSS selectors, header-aware
tables, structural inference, anchor URL patterns — and the first layer whose
rows score as a genuine notice listing wins. Three of those layers use no class
names at all, so a site has to change substantially before a portal goes dark.

`python run.py --capture PORTAL` fetches a portal's live pages, saves them as
test fixtures, and reports which layer worked and what selectors the page
actually uses.

## Status

**The scrapers have not been run against live pages.** They were built in an
environment whose network policy blocked all 13 portal domains.

- Verified against the live web: source URLs and notice-link patterns
- Verified offline against fixtures: extraction, parsing, filtering, scoring,
  reporting, delivery fallback — 179 checks via `python tests/run_all.py`
- **Not verified: CSS selectors and DOM structure**

Expect to run `--capture` against each HTML portal on first use. The selector
hints are informed guesses; the quality gate keeps a wrong guess from producing
bad data, but it cannot make a wrong guess right.

## Tests

```bash
cd jordan_tender_monitor
python tests/run_all.py    # 179 checks, no network, no credentials
```

CI runs the same suites on every push and pull request across Python 3.11
and 3.12.

## License

[MIT](LICENSE)
