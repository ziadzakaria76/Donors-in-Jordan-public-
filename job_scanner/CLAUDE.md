# job_scanner — working rules

A vacancy scanner for one target role: **Consultant Gastroenterologist**,
across Gulf hospital groups. It reads each employer's careers source, scores
what it finds against a frozen profile, and writes a workbook, a shortlist
document, a JSON dump and a static page.

```bash
pip install -r requirements.txt
python qa_check.py                                   # the gate; must be green
python scanner.py --only kfshrc,jhah --out runs/baseline.xlsx
python scanner.py --out runs/jobs_$(date +%F).xlsx \
                  --docx runs/shortlist_$(date +%F).docx \
                  --json runs/scan_$(date +%F).json \
                  --html site/index.html
```

## The rules

**The `profile` block in sources.yaml is frozen.** Never edit any value in it,
`max_age_days` included. `.profile.lock` holds its fingerprint and qa_check
compares them, so an edit turns the battery red rather than passing quietly.

`max_age_days` is the value most likely to be "just widened a bit" when a run
comes back thin, and it is the one that must not move. It exists because stale
portals report healthy: a mirror whose newest vacancy closed in 2019 returns
HTTP 200, a well-formed payload and a full page of jobs. Nothing in the
transport layer is wrong. Age is the only signal that separates it from a live
board. Sidra is exactly this case and is `permanently_disabled`.

**`verified` is a claim about evidence.** Three values, and the difference
matters:

| value | means |
| --- | --- |
| `unconfirmed` | nothing has been checked |
| `url-confirmed` | careers URL and platform confirmed from the live site; **the search API has not been called** |
| `true` | a call was made and it returned postings |

Never set `true` on the strength of a URL that loads. Never set it because a
payload parsed — it has to have carried vacancies.

**A closing deadline is never a posting date.** `Posting` keeps `posted_at`
and `closing_at` in separate fields, and `Posting.from_deadline_only()` raises
if handed a `posted_at`. A portal that publishes only a deadline yields
`posted_at=None` — unknown — because "unknown" keeps a stale posting visible
as stale while "today" launders it straight past `max_age_days`.

**Never weaken, skip or delete a check to make something pass.** Every check
in qa_check.py exists because something could go wrong in a way the output
would not reveal.

**Non-fatal observations go through `scanner.note(source_key, message)`**, never
to stderr. The weekly run is unattended; a message on the console is gone
before anyone opens the spreadsheet. `note()` puts it in the Run status sheet
beside the numbers it explains.

**The request delay is a floor of 1.5s**, enforced in `Fetcher.__init__` rather
than configured. Skip any site whose terms prohibit automated access.

**Endpoints stay hard-coded once found.** Playwright is a discovery-time tool,
in `requirements-browser.txt` and never in `requirements.txt`. The weekly run
is a handful of HTTP requests, not a browser fleet.

## What is and is not committed

`runs/` **is** committed — the workflow writes there and the history of runs is
the point. Not committed: `site/`, `alert_state.json`, `scan_recovery.json`,
captured live pages, and any credential. `.gitignore` names these explicitly;
do not replace them with a broad pattern, for the reason recorded at the top of
that file.

## An empty result is not a result

The distinction the whole design turns on: **a scraper that returns zero looks
exactly like an employer with no vacancies.** So

- adapters raise `AdapterError` with the real response detail rather than
  returning `[]`;
- an endpoint that returns a well-formed but empty array is recorded as an
  observation, not passed off as a clean run;
- the shortlist document says in bold, on a run where nothing was reachable,
  that an empty shortlist does **not** mean there are no vacancies;
- Run status separates `blocked` (refused before reaching the site — a network
  problem) from `error` (the site answered, and the answer was a problem).

## Current state

**No source is enabled and none is verified.** Every one of the sixteen careers
hosts was probed and every one was refused at the egress gateway (`curl` 000;
proxy log `connect_rejected`; headless Chromium
`net::ERR_TUNNEL_CONNECTION_FAILED`). No careers URL has been loaded and no
search API has been called.

The adapters are proven against payload fixtures shaped like each platform's
real response, which validates the **parsing** and nothing whatever about any
endpoint. The `careers_url` values in sources.yaml are targets to confirm, not
confirmed facts.

To take this further you need a network that can reach those hosts. Then:

1. `python discover_playwright.py <careers-url> --key <source>` per employer.
2. Paste the emitted block into sources.yaml; set `verified` honestly.
3. `python scanner.py --only <source>` and check it returns postings.
4. Add a regression check to qa_check.py using a fixture taken from the real
   response, confirm the battery is green, and commit with the source key in
   the message.
