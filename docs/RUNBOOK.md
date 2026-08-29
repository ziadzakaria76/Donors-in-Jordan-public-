# Runbook — from this branch to a working daily report

Ordered by dependency. Steps 1–2 unblock everything else; step 3 is started
early only because its approval is slow.

Legend: ⏱ = elapsed time you wait on someone else, not effort.

---

## Stage 1 — Get the code onto GitHub  (10 min, needs a computer)

The branch exists only as a git bundle until this is done.

1. Move `syria-tender-monitor.bundle` from your phone to a computer with `git`
   (email, Drive, or cable).
2. Clone the repo, or use an existing clone:
   ```bash
   git clone https://github.com/ziadzakaria76/Donors-in-Jordan-public-
   cd Donors-in-Jordan-public-
   ```
3. Import the branch and push it:
   ```bash
   git fetch /path/to/syria-tender-monitor.bundle \
     claude/admiring-brown-wn1rmw:claude/admiring-brown-wn1rmw
   git push -u origin claude/admiring-brown-wn1rmw
   ```
4. Check you got the right thing before opening the PR:
   ```bash
   git log --oneline -3        # head should be the SHA quoted in the chat
   ```
5. On github.com, use the **Compare & pull request** banner. Paste `PR-body.md`
   as the description. Mark it **draft**.

**Done when:** the branch is on GitHub and CI has run. Expect the `test` job
green on 3.11 and 3.12, and the `browser-fallback` job green.

> Why this can't be done for you: the Claude session's GitHub credentials were
> issued before the app was installed and cannot be refreshed from inside it.
> A *new* Claude session, given the bundle, would have working credentials.

---

## Stage 2 — Prove it runs  (15 min, same computer)

```bash
pip install -r requirements-dev.txt
python -m pytest tests/ -q              # expect: 455 passed
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

## Stage 3 — Request the SAM.gov key  (5 min, then ⏱ 1–4 weeks)

Do this now, because the wait is the longest thing in this list.

1. Register at https://sam.gov and request a public API key.
2. When it arrives, put it in `.env`:
   ```
   SAM_API_KEY=...
   ```

**Until then:** SAM.gov reports `skipped -- SAM_API_KEY not set` and the other
nine portals run normally. Nothing else is blocked by this.

---

## Stage 4 — Unlock UNGM  (20 min, needs network — or a phone, see below)

UNGM is the richest single Syria source and it is deliberately disabled until
you do this. It uses its own numeric country ids, not ISO codes; the value
cannot be derived, and a wrong one returns nothing *silently*.

1. Capture the live pages:
   ```bash
   PYTHONPATH=src python -m syria_monitor.cli --capture ungm
   ```
   **From a phone instead:** GitHub → Actions → **Run monitor** → Run workflow →
   mode `capture`, portal `ungm`. The id appears on the run summary page, and
   the captured HTML comes back as an artifact. Requires Stage 1 to be done.
2. Read the line it prints:
   ```
   >>> set portals.ungm.country_id: NNNN    (Syrian Arab Republic)
   ```
3. Put that number in `config.yml` under `portals.ungm.country_id`.
4. Open your browser's devtools on https://www.ungm.org/Public/Notice, run a
   search, and copy the **request payload** of the POST to
   `/Public/Notice/Search`.
5. Replace `search_body()` in `src/syria_monitor/portals/ungm.py` with those
   fields, exactly as sent. Do not reconstruct it from documentation — a
   previous reconstruction is what convinced a team the endpoint was dead.

**Done when:** `--capture ungm` shows rows extracted with a quality score, and
`--dry-run --portal ungm` returns notices.

---

## Stage 5 — Confirm the other portals really parse  (1–2 hours, needs network — or a phone)

No scraper in this repository has ever run against a live page. This is where
that gets fixed. For each HTML portal:

```bash
PYTHONPATH=src python -m syria_monitor.cli --capture undp     # then srtf, giz, isdb, gtai
```

**From a phone instead:** Actions → Run monitor → mode `capture`, portal `all`.
One run walks every HTML portal and puts the whole report on the run summary.

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
- **Scheduled runs** — Actions → Run monitor → the run → **Artifacts** →
  `syria-tender-report` (kept 90 days). The summary is also on the run page
  itself, so you can see whether a run was healthy without downloading.
- **Somewhere shared** — add a step after "Run monitor" that copies `output/*`
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
2. Trigger **Run monitor** manually once (Actions tab → Run workflow) and read
   the run summary; the Word/Excel/JSON files upload as artifacts.
3. Leave the schedule on. The subject line tells you whether a quiet day was
   quiet or broken.

---

## Recurring, once a month

- `--check-portals` — donor sites move.
- Re-read the sanctions dates in the README. Residual designations remain, and
  the Caesar repeal carries 180-day certifications; the position can change.
- Re-run `--capture` on any portal whose kept-count drops to zero.
