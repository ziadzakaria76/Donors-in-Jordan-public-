# Donors in Jordan

Four unrelated projects share this repository. They have no code in common,
and none of them builds, imports or deploys another.

| Project | What it is | Where it lives |
| --- | --- | --- |
| **General Sherman Housing** | A bilingual (Arabic RTL / English LTR) marketing site for a Jordanian residential developer | [`website/`](website/) |
| **[Jordan Tender Intelligence Monitor](#jordan-tender-intelligence-monitor)** | A Python system that watches 13 donor and IFI procurement portals for Jordan-related consulting work | [`jordan_tender_monitor/`](jordan_tender_monitor/) |
| **[Syria Tender Intelligence Monitor](#syria-tender-intelligence-monitor)** | A separate Python system, country-agnostic by design, watching 10 portals for Syria-related work | [`syria_tender_monitor/`](syria_tender_monitor/) |
| **Doc2MD** | A standalone PWA that converts PDF, Word and Excel to token-efficient Markdown, entirely in the browser | [`doc2md/`](doc2md/README.md) |

The two tender monitors are **separate codebases that solve the same problem
twice**, not one system with two configurations. They share no module, no
dependency file and no test. Read
[Two monitors, one problem](#two-monitors-one-problem) before changing either
under the impression that the other will follow.

---

# جنرال شيرمان — General Sherman Housing

Plain HTML, CSS and JavaScript in [`website/`](website/): project showcases, a
live unit inventory with filters, a per-building availability grid, floor
plans, a gallery, and lead capture through WhatsApp, phone and forms. No build
step, no framework, no runtime dependencies.

**Full documentation: [`website/README.md`](website/README.md)** — running it
locally, deploying, what the content file holds, and what was deliberately left
blank rather than invented.

```bash
cd website
python3 -m http.server 8080
```

The site is deployed to <https://general-sherman-housing.com> through Cloudflare
Pages, publishing the contents of `website/`.

Deliberately not documented twice: everything about the site lives in
`website/README.md`, so there is one description of it and it is the one next
to the code.

---

# Jordan Tender Intelligence Monitor

Automated multi-agent system that monitors 13 donor and international financial
institution procurement portals for Jordan-related consulting opportunities,
scores them for relevance, and writes a Word bid-review pack and an Excel
working file to disk.

Full documentation: **[`jordan_tender_monitor/README.md`](jordan_tender_monitor/README.md)**

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

The list is data, in
[`jordan_tender_monitor/portals.json`](jordan_tender_monitor/portals.json), so
a portal can be added, disabled or repointed without touching code. Eight of
the thirteen are data alone and go through the generic extraction cascade; five
keep a module because their source is a search endpoint or an API rather than a
page. Why each is configured as it is:
[`PORTALS.md`](jordan_tender_monitor/PORTALS.md).

A failing portal is skipped with a diagnosed reason and reported as unavailable
with the URL to check by hand. It never aborts the run, and a broken run never
looks like a quiet one — portal health is in the output filename, and an
optional short **ACTION NEEDED** email fires when a run cannot read its sources
at all.

## Status — first live run completed 3 August 2026

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

**Two defects that first run exposed, both now fixed.** The World Bank API
silently ignores `countryshortname=Jordan`; because that module trusted the
parameter and skipped client-side filtering, the first report led with a
Caribbean education project and roughly 140 of 259 entries were not Jordan at
all. And World Bank titles were read from `project_name`, so six different
notices rendered as six identical lines.

**Still unverified:** the CSS selectors for the portals that have not yet
returned a clean listing. Run `python run.py --capture PORTAL` against those.

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

### The Android app

**[`android/ANDROID.md`](android/ANDROID.md)** — the same thing with fewer taps.
The last report offline, a Run button with the workflow's real inputs, the full
portal health table, and the Word and Excel packs downloaded and opened on the
phone. Install it from the phone: the APK is built by CI and attached to the run.

It does not scrape — it is a client to the pipeline that already runs on
GitHub's servers. It reads the `*.json` artifact each run writes, because
GitHub's REST API does not expose the run page's summary to any client.

It also **manages the portal list**: switch a portal on or off, add one by URL,
or remove one, each as a real commit to `portals.json`. Adding one tests the
page first — a `--probe` run fetches it on GitHub's runner and reports what
every extraction layer found, rows included — because committing a URL nobody
has looked at is how a portal ends up reporting "unavailable" forever while
looking like an honest failure.

Install it from the repository's **Releases** page — a plain `.apk`, no sign-in
needed. `git tag v0.4.0 && git push origin v0.4.0` cuts one: the workflow runs
the tests, builds the APK and publishes it with its SHA-256.

**Compiled by CI, never run on a device.** `ANDROID.md` opens with a table of
what that leaves unverified, and the generated release notes repeat it.

## Deploying

Step-by-step setup for a Windows Server, including Azure app registration and
Task Scheduler:
**[`jordan_tender_monitor/DEPLOYMENT-WINDOWS.md`](jordan_tender_monitor/DEPLOYMENT-WINDOWS.md)**

Note that nothing runs until it is deployed — this repository is source code,
not a running service.

## Tests

```bash
python jordan_tender_monitor/tests/run_all.py    # 1,521 checks, no network, no credentials
```

CI runs the suite and `pyflakes` on Python 3.11 and 3.12, on pushes to `main`
and on pull requests.

## Security

Email is off by default, so no mail credentials are required — nothing to leak
or rotate. `.env` is never committed and holds only the optional SAM.gov API
key. If you later switch delivery back on, read the `Mail.Send` scoping warning
in the [full README](jordan_tender_monitor/README.md#security) first: as an
Azure *application* permission it is tenant-wide.

---

# Syria Tender Intelligence Monitor

A second, independent monitor: it watches 10 donor and IFI portals for
Syria-related consulting opportunities, classifies each notice by where the work
is actually delivered, screens named parties against sanctions lists, and writes
a ranked Word bid-review pack, an Excel working file and a JSON record set to
disk. Nothing is emailed — the report is the files, and you download them.

Full documentation: **[`syria_tender_monitor/README.md`](syria_tender_monitor/README.md)**
Setup, step by step: **[`syria_tender_monitor/docs/RUNBOOK.md`](syria_tender_monitor/docs/RUNBOOK.md)**

```bash
cd syria_tender_monitor
pip install -r requirements-dev.txt
python -m pytest tests/ -q                            # 456 passed, 1 skipped
PYTHONPATH=src python -m syria_monitor.cli --self-test # whole pipeline, fixtures, no network
```

**Portals:** World Bank, EU TED, SAM.gov and UK Find a Tender (REST APIs); UNGM,
UNDP, SRTF, GIZ, IsDB and KfW via Germany Trade & Invest (HTML).

**Read its README's "What is verified, and what is not" section before trusting
any output.** No scraper in it has ever run against a live page: every URL, and
every HTML portal's page structure, is unverified. It ships no CSS selectors on
purpose and relies on class-independent extraction, and UNGM refuses to run
until you supply the numeric country id that `--capture ungm` reads off the
page. That is the honest starting state, not a defect to be surprised by later.

## Two monitors, one problem

They are not a fork of each other and neither is the successor. The differences
that matter if you are deciding which to touch:

| | Jordan | Syria |
| --- | --- | --- |
| Country | Hard-coded throughout | A profile argument; `profiles/syria.yml` holds the country data, so a second country is a second YAML file |
| Layout | Flat package, run with `python run.py` | `src/` layout, run with `python -m syria_monitor.cli` |
| Tests | Custom harness, `tests/run_all.py` | pytest, 457 tests |
| Extras | Email delivery, Windows deployment guide | Delivery-location classification, sanctions screening, a tri-state country gate |
| Live status | Ran against live portals on 3 August 2026; results above | Never run against a live page |

Merging them is a real option and a real project; nothing here has been done
towards it. Until someone does it, a fix to a shared-looking bug — a date
format, a portal's layout change — has to be made twice, by hand, in two
places.

---

## License

[MIT](LICENSE)
