# Jordan Tender Intelligence Monitor

Automated multi-agent system that monitors 13 donor and international financial
institution procurement portals for Jordan-related consulting opportunities,
scores them for relevance, and writes a Word bid-review pack and an Excel
working file to disk.

Full documentation: **[`jordan_tender_monitor/README.md`](jordan_tender_monitor/README.md)**

## Status — the scrapers have never run against a live page

This was built in an environment whose egress policy blocked **all 13 portal
domains** with `HTTP 403` at the proxy. That is a policy denial, and it was not
worked around.

- **Verified against the live web:** nothing
- **Verified offline against fixtures:** extraction, parsing, filtering,
  scoring, reporting, delivery fallback — 507 checks
- **Not verified:** every portal URL, every CSS selector, every API response
  shape, and email delivery

**The CSS selectors are guesses.** The quality gate stops a wrong selector from
producing bad data — it falls through to a class-independent layer. It cannot
make a wrong selector right. Run `python run.py --capture PORTAL` against each
HTML portal before trusting it.

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

## Deploying

Step-by-step setup for a Windows Server, including Azure app registration and
Task Scheduler:
**[`jordan_tender_monitor/DEPLOYMENT-WINDOWS.md`](jordan_tender_monitor/DEPLOYMENT-WINDOWS.md)**

Note that nothing runs until it is deployed — this repository is source code,
not a running service.

## Tests

```bash
python jordan_tender_monitor/tests/run_all.py    # 507 checks, no network, no credentials
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
