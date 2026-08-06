# Running it from your phone

No install, no server, no laptop. GitHub runs the monitor; you tap a button and
read the results.

**There is also an app.** Same runs, fewer taps: the last report readable
offline, a Run button, the full portal health table, the Word and Excel packs,
portal management, and a notification when a run finishes. Install it from the
repository's Releases page — see
[`android/ANDROID.md`](../android/ANDROID.md). Everything below still works
exactly as it did, and is what to fall back on if the app misbehaves; it is
also the only route that has actually been used, since the app has never been
run on a device.

---

## One-time setup

Nothing to configure. The workflow is already in the repository at
`.github/workflows/monitor.yml` and is live as soon as it is on `main`.

Two optional extras:

- **SAM.gov key.** If yours has come through, add it as a repository secret so
  that portal works: **Settings → Secrets and variables → Actions → New
  repository secret**, named `SAM_API_KEY`. Without it, SAM.gov reports as *not
  configured* and everything else runs normally.
- **Failure notifications.** GitHub emails you when a workflow run fails, and a
  total portal outage deliberately makes the run fail. Check it is on at
  **github.com/settings/notifications → Actions**. This replaces the Azure mail
  setup entirely — no credentials, no client secret.

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

Scheduled runs can start a few minutes late when GitHub is busy. That is normal
and does not mean anything is wrong.

**Why :17 and not :00.** GitHub delays scheduled runs under load and can drop
them entirely, and the top of every hour is the busiest minute on the platform
because that is where most people point their crons. This workflow was set to
04:00 and fired zero times before the minute was moved. If a morning ever
passes with no run, check the Actions tab -- and note that GitHub also disables
scheduled workflows automatically in a repository with no activity for 60 days,
which a monitor nobody commits to will eventually hit.

---

## Before you trust the results

The CSS selectors in this codebase have never been checked against a live page —
see the main README. From your phone you can start that verification:

**Actions → Run workflow → Limit to these portals: `ungm`**

Then read the portal status table in the summary. Repeat for `ebrd`, `eib`,
`giz`, `kfw`, `isdb`, `sfd`, `adfd`, `jica`. Any portal reporting a diagnosed
failure needs its selectors or its URL corrected — that work needs a real
editor, but the diagnosis you can do entirely from the phone.

---

## Cost

Free. Public repositories get unlimited GitHub Actions minutes, and this uses
roughly two minutes per run.
