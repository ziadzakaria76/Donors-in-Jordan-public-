# Deploying on Windows Server

Start-to-finish setup for Windows Server 2016 or later. Roughly 45 minutes,
plus however long the Azure app registration takes your IT team.

Read step 6 before you start. It is the one step people skip, and skipping it
is the difference between a monitor that works and one that quietly reports
nothing.

---

## Before you begin

You need:

- **Windows Server 2016+** with outbound HTTPS to the internet, and a service
  account that can run a scheduled task whether or not anyone is logged in.
- **Outbound access to 13 donor domains.** If your network filters egress, get
  these allow-listed first — otherwise every portal reports unavailable and
  you will spend a day debugging a firewall:

  ```
  search.worldbank.org      api.ted.europa.eu        api.sam.gov
  www.find-tender.service.gov.uk                     www.ungm.org
  www.ebrd.com             ecepp.ebrd.com            www.eib.org
  www.giz.de               ausschreibungen.giz.de    www.gtai.de
  www.isdb.org             www.sfd.gov.sa            www.adfd.ae
  www.jica.go.jp
  ```

- **A folder for the output**, and somewhere your team can reach it — a shared
  drive or a synced folder works well, since the reports are files rather than
  emails.

You do **not** need an Azure app registration, mail credentials, or any secret.
Email is off by default; the system writes a Word pack and an Excel file to
disk and stops there.

---

## 1. Install Python

Download Python 3.11 or 3.12 (64-bit) from python.org. The suite is tested on
both.

During installation, tick **"Add python.exe to PATH"**. If you miss it, use the
full interpreter path everywhere below.

```powershell
python --version      # expect 3.11.x or 3.12.x
```

Install for **all users** if the task will run as a service account — a
per-user install is invisible to other accounts and produces a
"Python was not found" failure in Task Scheduler that gives no clue why.

---

## 2. Get the code

```powershell
cd C:\Services
git clone https://github.com/ziadzakaria76/Donors-in-Jordan-public-.git jordan-tenders
cd jordan-tenders
```

No Git on the server? Download the ZIP from GitHub and extract it to
`C:\Services\jordan-tenders`. You will just need to re-download to update.

---

## 3. Create a virtual environment and install

```powershell
cd C:\Services\jordan-tenders
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r jordan_tender_monitor\requirements.txt
```

If `Activate.ps1` is blocked by execution policy:

```powershell
Set-ExecutionPolicy -Scope CurrentUser -ExecutionPolicy RemoteSigned
```

**Optional: the headless browser, for UNGM only.** UNGM is the richest Jordan
source — UNDP, UNICEF, WFP, UNOPS, UNHCR and UNRWA all publish there — and it
is the one portal that cannot be read over plain HTTP: its listing is assembled
in the browser after the page loads, so a fetch returns navigation and nothing
else. Reading it needs a real browser, which is about 400 MB:

```powershell
pip install -r jordan_tender_monitor\requirements-browser.txt
playwright install chromium
```

Skip this and nothing breaks: UNGM reports `unavailable` with those two
commands as its stated reason, and the other twelve portals run normally.

**Confirm the time zone database installed.** Windows ships no IANA time zone
database, so the schedule — pinned to `Asia/Amman` — depends on the `tzdata`
package. It is in `requirements.txt` for Windows, but verify:

```powershell
python -c "from zoneinfo import ZoneInfo; print(ZoneInfo('Asia/Amman'))"
```

Expect `Asia/Amman`. A `ZoneInfoNotFoundError` means the install was
incomplete — run `pip install tzdata`.

Now prove the code itself is sound before touching credentials:

```powershell
python jordan_tender_monitor\tests\run_all.py
```

Expect **All 699 checks passed**. This needs no network and no credentials, so
a failure here is an install problem, not a configuration one.

---

## 4. Choose where the reports land

By default they go to `jordan_tender_monitor\output\` inside the install
directory. To put them on a share instead, set `JTM_OUTPUT_DIR`:

```powershell
setx JTM_OUTPUT_DIR "\\fileserver\Bids\JordanTenders" /M
```

Make sure the service account that runs the scheduled task can **write** there —
a permissions failure at 07:00 on a share is the most likely way this silently
stops producing files.

Each run leaves two files:

```
jordan_tenders_20260803_0700_7-opportunities.docx    <- circulate and annotate
jordan_tenders_20260803_0700_7-opportunities.xlsx    <- filter, sort, assign
```

Files accumulate, one pair per weekday. Housekeeping is up to you; nothing
deletes them.

### Optional: email later

If you ever want these emailed as well, set `EMAIL_METHOD = "graph"` in
`config.py` and fill in the Azure credentials in `.env`. Before granting
`Mail.Send` as an Azure **application** permission, read the warning in the
project README — it is tenant-wide, and must be scoped to a single mailbox with
`New-ApplicationAccessPolicy`. None of that is needed for file output.

## 5. Configure

There is nothing you must configure to get file output — the defaults work.

`.env` is only needed for the optional SAM.gov API key:

```powershell
copy jordan_tender_monitor\.env.example jordan_tender_monitor\.env
notepad jordan_tender_monitor\.env
```

```ini
SAM_API_KEY=
```

SAM.gov issues free keys with **1-4 weeks** approval. Leave it blank until yours
arrives; the portal then reports as *not configured* rather than *unavailable*,
so a pending key never looks like a broken scraper.

Everything else lives in `config.py` — sectors, minimum value, which portals to
poll, output formats. Each setting is commented with the reasoning behind it.

## 6. Verify the portals — do not skip this

Two commands, in this order.

### 6a. Can the server reach the portals?

```powershell
python jordan_tender_monitor\run.py --check-portals
```

Every portal should read `OK` or `NOT SET UP` (SAM.gov, until its key arrives).
Any `UNREACHABLE` is a firewall or proxy problem, and the output names the URL
to test by hand. **Fix this before going further** — nothing downstream can work
if the server cannot see the sites.

### 6b. Verify the selectors against the live pages

**The CSS selectors in this codebase are unverified guesses.** They were written
in an environment where all 13 portal domains were blocked, so not one has been
checked against a real page. The extraction cascade is built to survive a wrong
selector — it falls through to layers that use no class names at all — but a
wrong guess still costs you data quality.

Run this for each of the nine HTML portals:

```powershell
foreach ($p in "ungm","ebrd","eib","giz","kfw","isdb","sfd","adfd","jica") {
    python jordan_tender_monitor\run.py --capture $p
}
```

For each portal it prints every extraction layer, its row count and quality
score, which layer won, and — derived from the live DOM, not guessed — the
selectors the page actually uses.

Read the output:

- **A layer wins with good quality** → that portal works. Nothing to do.
- **`BELOW QUALITY GATE`** → it extracted something but is not confident. Paste
  the derived selectors into that portal's `selectors` list in
  `jordan_tender_monitor\portals\<portal>.py` and re-run.
- **`bot wall (Cloudflare/Incapsula)`** → the site is blocking automated access.
  Try from a different network, or install Playwright.
- **`JavaScript shell`** → run `pip install playwright` then
  `playwright install chromium`.
- **Every source failed** → the URL has moved. Find the current listing page and
  update `urls` in that module.

Expect to spend an hour here. It is the difference between a monitor that finds
tenders and one that reports thirteen portals of nothing.

---

## 7. Dry run, then a real send

```powershell
python jordan_tender_monitor\run.py --dry-run
```

This scrapes, filters, scores and prints — and sends nothing, records nothing.
Check that the tenders listed look like work you would actually bid on. If the
list is empty but the portals all read OK, revisit step 6b.

Then send one email by hand:

```powershell
python jordan_tender_monitor\run.py --send
```

**The first run reports the entire currently-open pipeline**, not just new
notices, because the seen-tenders database starts empty. That first email will
be long. From the next run onward it reports only what is new.

Confirm it arrives. If it does not, the console names the reason: a Graph
failure falls back to SMTP, then to writing the files into
`jordan_tender_monitor\output\` — you never lose a run to a delivery problem.

---

## 8. Schedule it

Use **Task Scheduler**, not `--schedule`. A scheduled task survives reboots and
logoffs; a console process does not.

### The wrapper script

Create `C:\Services\jordan-tenders\run-monitor.cmd`:

```bat
@echo off
cd /d C:\Services\jordan-tenders
call .venv\Scripts\activate.bat
python jordan_tender_monitor\run.py --run >> logs\task.log 2>&1
exit /b %ERRORLEVEL%
```

```powershell
mkdir C:\Services\jordan-tenders\logs
```

### Register the task

Run PowerShell **as Administrator**:

```powershell
$action  = New-ScheduledTaskAction -Execute "C:\Services\jordan-tenders\run-monitor.cmd"
$trigger = New-ScheduledTaskTrigger -Weekly `
             -DaysOfWeek Monday,Tuesday,Wednesday,Thursday,Friday `
             -At 7:00am
$settings = New-ScheduledTaskSettingsSet `
             -StartWhenAvailable `
             -RunOnlyIfNetworkAvailable `
             -ExecutionTimeLimit (New-TimeSpan -Hours 1) `
             -MultipleInstances IgnoreNew

Register-ScheduledTask -TaskName "Jordan Tender Monitor" `
  -Action $action -Trigger $trigger -Settings $settings `
  -User "DOMAIN\svc-tenders" -RunLevel Limited `
  -Description "Weekday scan of 13 donor procurement portals for Jordan consulting opportunities"
```

You will be prompted for the service account password. `-StartWhenAvailable`
means a missed run (server rebooting at 07:00) fires as soon as it can rather
than being skipped silently.

### Get the time right

**Task Scheduler triggers fire in the server's local time**, not Amman time.
Jordan is **UTC+3 year-round** — it abolished daylight saving in 2022 — so:

| Server time zone | Set the trigger to | Lands in Amman at |
|---|---|---|
| Asia/Amman (UTC+3) | 07:00 | 07:00 |
| UTC | 04:00 | 07:00 |
| Central Europe (UTC+1 winter / +2 summer) | 05:00 / 06:00 | 07:00 |
| US Eastern (UTC−5 / −4) | 23:00 previous day | 07:00 |

Check what your server actually uses:

```powershell
Get-TimeZone
```

Note the European and US rows shift twice a year while Jordan never does. If
your server observes daylight saving, either accept a one-hour drift for part
of the year, or set the server to UTC and use 04:00.

### Test it without waiting for morning

```powershell
Start-ScheduledTask -TaskName "Jordan Tender Monitor"
Get-ScheduledTaskInfo -TaskName "Jordan Tender Monitor" | Format-List LastRunTime, LastTaskResult
```

`LastTaskResult` of `0` is success. Then read `logs\task.log`.

---

## 9. Know that it is still alive

**The filename tells you the run's health**, so a glance at the output folder
answers "did this work?" without opening anything:

```
jordan_tenders_20260803_0700_7-opportunities.docx
jordan_tenders_20260804_0700_no-new-opportunities-13-of-13-portals-OK.docx
jordan_tenders_20260805_0700_4-opportunities-3-of-13-portals-unavailable.docx
jordan_tenders_20260806_0700_ACTION-NEEDED-all-13-portals-unreachable.docx
```

A quiet day and a dead monitor are different filenames, deliberately. Inside,
the Word pack opens with the run status in words, and the Excel file has a
**Run status** sheet naming each portal's diagnosed failure and the URL to check
by hand.

**No new file at all is the one state the monitor cannot report on itself.** If
a weekday passes with nothing new in the folder, the task did not run:

```powershell
Get-ScheduledTaskInfo -TaskName "Jordan Tender Monitor"
Get-Content C:\Services\jordan-tenders\logs\task.log -Tail 50
```

If you configured the `ACTION NEEDED` alert, a broken run emails you and a
healthy run stays silent -- but a *task that never fires* still sends nothing,
because nothing ran to notice. A weekly glance at the folder remains the only
guard against that, alert or no alert.

Re-verify the alert path after any credential rotation:

```powershell
python jordan_tender_monitor\run.py --test-alert
```

## Routine maintenance

| When | Do |
|---|---|
| A portal reports unavailable for several days | `--capture` that portal; the site has probably been redesigned or moved |
| Azure client secret expiry (if alerts are on) | Rotate in Azure, update `.env`, then re-run `--test-alert`. Set the reminder now. |
| SAM.gov key arrives | Put it in `.env`; the portal switches from *not configured* to live on the next run |
| Output folder grows | Archive or delete old reports; nothing prunes them automatically |
| Updating the code | `git pull`, then `pip install -r jordan_tender_monitor\requirements.txt`, then re-run the test suite |

### Useful commands

```powershell
# Forget every reported tender; next run re-sends the full open pipeline once
python jordan_tender_monitor\run.py --reset-db

# Exercise the whole pipeline on fixtures -- no network, no credentials,
# and it cannot touch the real database
python jordan_tender_monitor\run.py --self-test

# Investigate a single portal
python jordan_tender_monitor\run.py --dry-run --only ungm
```

Note `--dry-run` still writes the files; what it does not do is record the
tenders as seen, so the next real run reports them again.

---

## Troubleshooting

**"Python was not found"** in Task Scheduler but Python works in your shell —
Python was installed per-user and the service account cannot see it. Reinstall
for all users, or use the full path to `python.exe` in `run-monitor.cmd`.

**`ZoneInfoNotFoundError: No time zone found with key Asia/Amman`** — `tzdata`
is missing. `pip install tzdata`. Windows has no system time zone database.

**Task result `0x1` with an empty log** — the working directory is wrong, so
relative paths fail. The `cd /d` at the top of `run-monitor.cmd` handles this;
confirm it is there and the path is right.

**Every portal unreachable, but the sites open in a browser on the same
server** — an outbound proxy the browser is configured for and Python is not.
Set `HTTPS_PROXY` in `run-monitor.cmd` before the python line.

**Email never arrives, console says Graph returned HTTP 403** — the
`ApplicationAccessPolicy` is denying the sender mailbox. Re-run
`Test-ApplicationAccessPolicy` and confirm `SENDER_EMAIL` matches the scoped
mailbox exactly.

**Reports arrive but are always empty while portals read OK** — the selectors
are not matching. Go back to step 6b.
