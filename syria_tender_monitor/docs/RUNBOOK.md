# Runbook — from this branch to a working daily report

Ordered by dependency. Steps 1–2 unblock everything else; step 3 is started
early only because its approval is slow.

Legend: ⏱ = elapsed time you wait on someone else, not effort.

---

## Stage 1 — Get the code onto GitHub  ✅ done

The code is in this repository, under `syria_tender_monitor/`, imported from the
bundle with its history intact. Nothing here is left to do.

Two things changed in the move, and the rest of this runbook assumes both:

- **Every path and command below is relative to `syria_tender_monitor/`.**
  Start with `cd syria_tender_monitor`.
- **The workflows moved to the repository root**, because that is the only
  place GitHub reads them from. `run-monitor.yml` is now
  `.github/workflows/syria-monitor.yml`, named **Syria tender monitor** in the
  Actions tab; `ci.yml` folded into the repository's existing
  `.github/workflows/tests.yml` as the jobs `syria` and
  `syria-browser-fallback`. Both run from `syria_tender_monitor/`, so the
  commands they issue are the ones documented here.

**Done when:** CI has run on the branch. Expect the `syria` job green on 3.11
and 3.12, and `syria-browser-fallback` green. The `test` and `website-content`
jobs in the same workflow belong to the other two projects in this repository
and are unrelated.

---

## Stage 2 — Prove it runs  (15 min, same computer)

```bash
cd syria_tender_monitor                 # every path below is relative to here
pip install -r requirements-dev.txt
python -m pytest tests/ -q              # expect: 511 passed, 1 skipped
                                        # (the skip is the browser test; it
                                        #  passes once Playwright is installed)
python -m pyflakes src/ tests/          # expect: no output

PYTHONPATH=src python -m syria_monitor.cli --self-test
```

The self-test runs the whole pipeline over committed fixtures with no network.
It prints the four-way classification split and writes sample Word/Excel/JSON
files to a temp directory. If that works, the machine is set up correctly.

Then check what the network can actually see:

```bash
PYTHONPATH=src python -m syria_monitor.cli --check-portals
```

**Done when:** portals report `ok` rather than `403`/`FAIL`. Any that fail here
are either genuinely down, blocked by your network, or have moved — note which.

---

## Stage 3 — Request the SAM.gov key  (5 min, usually immediate)

1. Register at https://sam.gov (sign-in is via Login.gov), then
   **Account Details → API Key → Request API Key**. The key is shown once.
2. Put it in `.env`:
   ```
   SAM_API_KEY=...
   ```

A **personal public API key** is normally issued immediately. The
multi-week approval some documentation mentions applies to a **system
account**, which exists for higher rate limits and machine-to-machine access —
not needed for one country's notices once a day. Entity registration (UEI,
CAGE) is a different thing again and is not required here.

**Until then:** SAM.gov reports `skipped -- SAM_API_KEY not set` and the other
nine portals run normally. Nothing else is blocked by this.

---

## Stage 4 — Unlock UNGM  (steps 1–3 done; step 4 needs a browser)

UNGM is the richest single Syria source and it is deliberately disabled until
this is done. It needs two things that cannot be derived, only observed. The
first is now in place; the second still needs a human at a browser.

1. ~~Capture the live pages.~~ **Done** — Actions run 33240256664, 2026-08-29.
   Re-run it any time from GitHub → Actions → **Syria tender monitor** → Run
   workflow → mode `diagnose portals (--capture)`, portals `ungm`. The id
   appears on the run summary
   page and the captured HTML comes back as an artifact.
   ```bash
   PYTHONPATH=src python -m syria_monitor.cli --capture ungm
   ```
2. ~~Read the line it prints.~~ **Done** — it printed:
   ```
   >>> set portals.ungm.country_id: 2490    (Syrian Arab Republic)
   ```
   HTTP 200, 142061 bytes, 2490 of 234 dropdown options.
3. ~~Put that number in `config.yml`.~~ **Done** — `portals.ungm.country_id:
   2490`. UNGM owns these ids and can renumber them, so if the portal ever
   starts returning nothing, re-run step 1 and compare before hunting for a
   scraper bug.
4. **Still to do, and it needs you at a browser.** Open devtools on
   https://www.ungm.org/Public/Notice, run a search, and copy the **request
   payload** of the POST to `/Public/Notice/Search`.
5. Replace `search_body()` in `src/syria_monitor/portals/ungm.py` with those
   fields, exactly as sent. Do not reconstruct it from documentation — a
   previous reconstruction is what convinced a team the endpoint was dead.

The id alone does not make UNGM work: it clears the refusal to run, and step 4
is what makes the search return anything. The capture in step 1 scored rows
against the *dropdown* page, which says nothing about how real notices parse.

**Done when:** `--capture ungm` shows rows extracted with a quality score, and
`--dry-run --portal ungm` returns notices.

---

## Stage 5 — Confirm the other portals really parse  (1–2 hours, needs network — or a phone)

Every HTML portal except SAM.gov has now been reached by the daily run, so this
stage is no longer first contact — it is how you check that reaching a page and
reading it correctly are the same thing, which for GIZ and GTAI they are not.
For each HTML portal:

```bash
PYTHONPATH=src python -m syria_monitor.cli --capture undp     # then srtf, giz, isdb, gtai
```

**From a phone instead:** Actions → **Syria tender monitor** → mode
`diagnose portals (--capture)`, leaving **portals** blank for all of them (or
naming keys, space-separated, to narrow it). One run walks every HTML portal and
puts the whole report on the run summary.

These are the workflow's literal choices, and a `type: choice` input is matched
as an exact string — the short `capture` this file used to name has not existed
since the inputs were changed to the Android app's vocabulary.

For each one, read the per-layer table:

- **A layer wins with quality ≥ 0.45** → that portal works. Move on.
- **Nothing clears the bar** → read the diagnosis line:
  - `bot_wall` → set `browser: always` for that portal in `config.yml`
  - `js_shell` → same; make sure `requirements-browser.txt` is installed
  - `layout_change` → the page moved; the captured HTML is in
    `tests/fixtures/live/` for inspection
  - `transport` → the URL is wrong or the host is blocked

Then replace the reconstructed fixtures with the real captures:

```bash
cp tests/fixtures/live/undp-index.html tests/fixtures/html/undp.html
python -m pytest tests/test_html_portal_mapping.py -q
```

**A failure here is the point.** It names a field whose mapping was assumed
wrongly. Same applies to `tests/fixtures/api/*.json` for the four REST portals.

---

## Stage 6 — Decide where the files land  (10 min)

Nothing is emailed. A run writes four files to `output/`:

```
syria-tenders-2026-08-28.docx          the bid-review pack
syria-tenders-2026-08-28.xlsx          one row per tender
syria-tenders-2026-08-28.json          full records, for debugging a bad run
syria-tenders-2026-08-28-summary.md    short summary, always written
```

Pick how you want to reach them:

- **Local runs** — they are simply in `output/`.
- **Scheduled runs** — Actions → **Syria tender monitor** → the run → **Artifacts** →
  `syria-tender-report` (kept 90 days). The summary is also on the run page
  itself, so you can see whether a run was healthy without downloading.
- **Somewhere shared** — add a step after "Run monitor" in
  `.github/workflows/syria-monitor.yml` that copies `output/*`
  to wherever your team looks (a share, a bucket, a Drive folder). Nothing in
  the code needs to change for that.

No credentials are required for any of this.

## Stage 7 — First real report  (20 min)

```bash
PYTHONPATH=src python -m syria_monitor.cli --dry-run    # read this carefully
PYTHONPATH=src python -m syria_monitor.cli --run        # writes the files to output/
```

What to check in the dry run, in order:

1. **Portal health line** — anything `UNAVAILABLE` is a scraper to fix, not a
   quiet day.
2. **Classification split** — if `inside_syria` is 0 while
   `refugee_hosting_only` is large, the classifier is keeping the wrong things;
   send me the numbers.
3. **A few titles** — do they look like Syria work? A Caribbean or Malawi
   project appearing is a country-gate bug and I want to know.
4. **Deadlines** — a wall of "not published" means a date-parsing bug on that
   portal, not a portal without deadlines.

---

## Stage 8 — Schedule it  (10 min)

Already configured: `0 3 * * *` UTC = 06:00 Europe/Amman, daily.

1. Repo → Settings → Secrets and variables → Actions → **Secrets**: add
   `SAM_API_KEY` (the only secret this system uses).
2. Trigger **Syria tender monitor** manually once (Actions tab → Run workflow) and read
   the run summary; the Word/Excel/JSON files upload as artifacts.
3. Leave the schedule on. The summary on each run page states portal health,
   so a quiet day and a broken scraper are distinguishable at a glance from the
   Actions run list.

---

## Recurring, once a month

- `--check-portals` — donor sites move.
- Re-read the sanctions dates in the README. Residual designations remain, and
  the Caesar repeal carries 180-day certifications; the position can change.
- Re-run `--capture` on any portal whose kept-count drops to zero.
