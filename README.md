# Jordan Tender Intelligence Monitor

Automated multi-agent system that monitors 13 donor and international financial
institution procurement portals for Jordan-related consulting opportunities,
scores them for relevance, and writes a Word bid-review pack and an Excel
working file to disk.

Full documentation: **[`jordan_tender_monitor/README.md`](jordan_tender_monitor/README.md)**

## Status — first live run completed 3 August 2026

The scrapers have now run against live pages. Results by portal:

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

**Two defects the first run exposed, both now fixed.** The World Bank API
silently ignores `countryshortname=Jordan`; because that module trusted the
parameter and skipped client-side filtering, the first report led with a
Caribbean education project and roughly 140 of 259 entries were not Jordan at
all. And World Bank titles were read from `project_name`, so six different
notices rendered as six identical lines.

**Still unverified:** the CSS selectors for the portals that have not yet
returned a clean listing. Run `python run.py --capture PORTAL` against those.

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
python jordan_tender_monitor/tests/run_all.py    # 606 checks, no network, no credentials
```

CI runs the suite and `pyflakes` on Python 3.11 and 3.12, on pushes to `main`
and on pull requests.

## Security

Email is off by default, so no mail credentials are required — nothing to leak
or rotate. `.env` is never committed and holds only the optional SAM.gov API
key. If you later switch delivery back on, read the `Mail.Send` scoping warning
in the [full README](jordan_tender_monitor/README.md#security) first: as an
Azure *application* permission it is tenant-wide.

## License

[MIT](LICENSE)
