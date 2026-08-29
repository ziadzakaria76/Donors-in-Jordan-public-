# Running it from your phone

No install, no server, no laptop. GitHub runs the monitor; you tap a button and
read the results.

---

## One-time setup

Nothing to configure. The workflow is already in the repository at
`.github/workflows/monitor.yml` and is live as soon as it is on `main`.

Two optional extras:

- **SAM.gov key.** If yours has come through, add it as a repository secret so
  that portal works: **Settings → Secrets and variables → Actions → New
  repository secret**, named `SAM_API_KEY`. Without it, SAM.gov reports as *not
  configured* and everything else runs normally.
- **Notifications.** GitHub emails you when a run *fails*, and a total portal
  outage deliberately makes the run fail — so alerting works with no credentials
  at all. To hear about successful runs too, see *Getting told, instead of
  remembering to look* below; the system itself sends nothing.

---

## Running it

1. Open the repository on your phone and go to the **Actions** tab.
   (On mobile the tabs collapse — it is under **`More ▾`**.)
2. Choose **Jordan tender monitor** in the left-hand list.
3. Tap **Run workflow**. Two choices appear:

   | Field | What it does |
   |---|---|
   | **What to report** | *everything currently open* (default — best when you are looking now) or *only what is new since the last run* |
   | **Limit to these portals** | Leave blank for all thirteen. Or name a few, space-separated: `ungm worldbank giz` |

4. Tap the green **Run workflow** button. It takes a couple of minutes.

Direct link to the Actions tab:

```
github.com/ziadzakaria76/Donors-in-Jordan-public-/actions
```

---

## Reading the results

**On the run page itself.** Open the finished run and scroll to the summary. The
opportunities are a table with tappable links straight to each notice, followed
by the status of every portal. **You do not have to download anything to see
what was found** — this is the point of the whole arrangement.

**The Word and Excel files** are at the bottom of the run page under
**Artifacts**, as a zip. Download it if you want to circulate the bid-review
pack or work the pipeline in Excel. They are kept for 90 days, then deleted.

To get there: **Actions** -> **Jordan tender monitor** -> tap the run -> scroll
to the **bottom** -> **Artifacts** -> tap `jordan-tenders-<number>`.

Three things that will waste your time on a phone if you do not know them:

* **You have to be signed in to GitHub.** Artifact downloads require a login
  even on a public repository. Signed out, the link bounces you to a sign-in
  page rather than telling you why.

* **Use a mobile browser, not the GitHub app.** The app's run view does not show
  the Artifacts section at all, so the files look as though they were never
  produced. Safari or Chrome on the handset works; try "Request desktop site"
  if the section still does not appear.

* **It is always a zip**, even though there are only two files inside. iOS and
  Android both save it to Files or Downloads; tap it to expand before opening
  in Word or Excel.

None of that is needed to see what was found -- the summary above is the whole
report. Downloading is for circulating it or working it in Excel.

---

## Telling a quiet day from a broken one

| What you see | What it means |
|---|---|
| Green tick, summary lists opportunities | Working, and there is something to look at |
| Green tick, "No new opportunities" | Working. Genuinely nothing new — the summary confirms every portal was read |
| **Red cross**, "ACTION NEEDED" | The monitor could not read its sources. The summary names each failure and the URL to check |
| Partial: some portals unavailable | Ran, but the picture is incomplete. Named in the summary |

A red run is deliberate. A total outage exits non-zero so GitHub marks the run
failed and notifies you — which is how the alert reaches your phone without any
mail configuration at all.

**The one thing this cannot tell you is that a scheduled run never happened.**
GitHub also disables scheduled workflows on repositories with no activity for 60
days. If you have not seen a run in a while, open the Actions tab and check.

---

## The schedule

Weekdays at **04:17 UTC = 07:17 in Amman**. Jordan is UTC+3 year-round, so this
never needs a seasonal adjustment. Scheduled runs report only what is new;
manual runs default to the whole current pipeline.

To change it, edit the `cron` line in `.github/workflows/monitor.yml`. GitHub
cron is always UTC.

**Expect it late, and by more than a few minutes.** The cron asks for 04:17;
across nine measured mornings GitHub actually started the run between 04:54 and
05:48 UTC -- 37 to 91 minutes late, median 40. So in practice the report lands
around **08:00 in Amman**, not 07:17. That is GitHub queueing scheduled work,
not a fault, and there is no cron setting that fixes it: `schedule` is
best-effort and carries no delivery promise. If you need a guaranteed time, the
answer is an external scheduler calling `workflow_dispatch`, not a different
cron line.

**Why :17 and not :00.** GitHub delays scheduled runs under load and can drop
them entirely, and the top of every hour is the busiest minute on the platform
because that is where most people point their crons. This workflow was set to
04:00 and fired zero times before the minute was moved. If a morning ever
passes with no run, check the Actions tab.

---

## Getting told, instead of remembering to look

**The system itself sends nothing.** `EMAIL_METHOD = "none"` in `config.py`: it
writes the Word and Excel files and stops there. That is deliberate -- it is
what let the whole Azure `Mail.Send` credential be dropped -- but it means a
good morning is silent, and by default GitHub only emails you when a run
*fails*. So the only thing that currently reaches you unprompted is bad news.

To be told about every run, turn on GitHub's own notifications:

**github.com -> your avatar -> Settings -> Notifications -> "Actions"**

* tick **Email** (and/or Web)
* **untick "Only notify for failed workflows"** -- this is the one that matters

Three things to know before you do:

* **It is global, not per-repository.** GitHub offers no way to switch this on
  for one repo. Every repository whose Actions you are subscribed to will start
  emailing you.

* **The subject line does not carry the count.** It reads "Run succeeded:
  Jordan tender monitor". You have to open it -- but the run page you land on
  already renders the whole report, and the artifact filename carries the
  number (`jordan_tenders_..._95-opportunities.docx`).

* **Quiet days email you too.** Scheduled runs report only what is new, so most
  mornings will legitimately say nothing new was found. That is the system
  working, not failing.

Notifications for a scheduled run go to whoever last modified the workflow
file, which for this repository is its owner.

**If you would rather have the files themselves in your inbox** than a link to
fetch them, that is a different setting: `EMAIL_METHOD = "smtp"` (or `"graph"`)
in `config.py` plus credentials in `.env`. The delivery code is retained and
still tested. Read the `ApplicationAccessPolicy` warning above that setting
before granting `Mail.Send` as an Azure *application* permission -- it is
tenant-wide otherwise, meaning the app could send as any mailbox in the
organisation.

---

## Before you trust the results

Every portal has been read live and its result checked against what the source
actually publishes. At the time of writing two were genuinely unreachable (EIB
behind a bot wall, the Saudi Fund timing out), two published no listing at all
(ADFD, JICA), and SAM.gov needed a key.

**Do not trust that list -- trust the run.** Portals break, recover and get
fixed, so the portal status table in every run is the authority and this
paragraph is only a snapshot. If the two disagree, the table is right.

That does not make the results permanently trustworthy: donor sites redesign,
and a portal that silently starts returning nothing looks exactly like a quiet
week. The check you can run from a phone is the same one that found every fault
so far:

**Actions → Run workflow → What to do: `diagnose portals (--capture)` → Limit to
these portals: `ungm`**

The summary then reports, per extraction layer, how many rows were found and at
what quality, which layer won, the selectors the page really uses, and the
network calls it makes. Repeat for any portal whose count looks wrong. Fixing
it needs a real editor; diagnosing it does not.

---

## Cost

Free. Public repositories get unlimited GitHub Actions minutes, and this uses
roughly two minutes per run.
