# The Android app

Reads the Jordan Tender Monitor from a phone: the last report offline, a Run
button, every portal's health, and the Word and Excel packs.

**It does not scrape.** Thirteen portals on a handset would mean Python on
Android, a headless browser, and a device that has to be awake and charged.
The pipeline already runs free on GitHub's servers on a weekday schedule; this
app is a client to it.

---

## What is verified, and what is not

Be clear about this before relying on any of it.

| | |
|---|---|
| **Compiles** | Yes — CI builds it on every push. That is the only place it is compiled; it is developed in an environment with no Android SDK |
| **Unit tested** | Token redaction, the API client's failure paths (401 / 403-permission / 403-rate-limit / 404 / 410 / 5xx / offline), report parsing and schema refusal, the artifact zip reader, editing `portals.json` without destroying the prose in it, and the notification and retry policies |
| **Tested on an emulator** | The Keystore-backed token store, Room against real SQLite, the notification channels, and every screen rendering and navigating. Run on API 26 and API 35 by **Android emulator tests** — see below |
| **NOT tested end to end** | The background worker itself, and the probe round-trip. Their decision logic is tested and their pieces are exercised on the device; the full sequences — WorkManager firing, dispatch, poll, download — have never run against real GitHub |
| **NOT run on a handset by anyone** | No physical device. An emulator is not a phone: it says nothing about a real manufacturer's "install unknown apps" flow, battery-optimisation killing background work, or how anything looks on a real screen |

If something behaves differently from this document, this document is wrong.

---

## Testing it on an emulator

`.github/workflows/android-emulator.yml` boots a real Android system image on CI
and runs `app/src/androidTest` against it, on **API 26** (the app's minSdk) and
**API 35** (its target).

That workflow exists because three things cannot be checked anywhere else, and
silence about them reads exactly like coverage:

- **The token store.** `EncryptedSharedPreferences` needs the Android Keystore,
  and there is no Keystore on a JVM. The test does not merely round-trip the
  token — a plain unencrypted file round-trips perfectly. It writes the token,
  then searches **every file the app owns** for it as plaintext. If encryption
  were removed entirely, that is the test that would notice.
- **Room's SQL.** Room writes the queries at build time and does not check them
  until they run. A `LIMIT` that trims the wrong end compiles fine and quietly
  caches the oldest reports while discarding the current one.
- **Whether a screen draws.** A Compose screen can compile and still throw on
  first composition. The tests run with **no token and no data**, which is the
  state a phone is in thirty seconds after install and the one most likely to
  be broken.

On failure the run keeps the test reports, the device log, and a screenshot of
whatever was on screen — the only evidence available for a device nobody can
attach a debugger to. An absent report is reported as **untested**, never as a
pass.

**Running it yourself**, if you have the Android SDK and a machine with KVM:

```bash
cd android
./gradlew connectedDebugAndroidTest     # with an emulator or handset attached
```

**Reusing the workflow for another Android project.** Change
`working-directory` and the API-level matrix; nothing else in it is specific to
this app. Two settings do the real work: the **Enable KVM** step, without which
the emulator falls back to software rendering and the job *hangs* rather than
failing, and `emulator-options`, which turns off the animations, audio and
cameras that make a headless emulator flaky.

---

## Installing it on the phone

No Android Studio, no laptop. Two routes; **use the first one.**

### From a Release (easier)

1. **Allow your browser to install apps.** Android blocks this by default.
   **Settings → Apps → (your browser) → Install unknown apps → Allow.** Exact
   wording varies by manufacturer; search settings for "unknown apps".
2. Open the repository's **Releases** page on the phone and tap the newest
   `jordan-tenders-vX.Y.Z.apk`.
3. Tap the downloaded file. Android will warn you it is from an unknown
   source. That is expected: it is not from the Play Store.

**No sign-in needed**, and it is a plain `.apk` rather than a zip — which is
the whole reason this route exists. Each release also prints the file's SHA-256
so you can check the download if you want to.

### From the latest build (newer, more friction)

Every push that changes the app builds an APK and attaches it to the run. Use
this when you want something that has not been released yet.

1. Open the **Actions** tab in a **mobile browser, not the GitHub app** — the
   app's run view does not show artifacts at all.
2. Choose the **Android app** workflow and open the newest green run.
3. Scroll to the **bottom**, to **Artifacts**, and tap
   `jordan-tenders-apk-<number>`.
4. It downloads as a **zip**. Open it in Files or Downloads, extract the
   `.apk`, and tap it.

**You have to be signed in to GitHub** to download a build artifact, even on a
public repository. Signed out, the link bounces you to a sign-in page without
saying why. Release assets have no such requirement.

Build artifacts are kept for 90 days. Release assets are kept indefinitely.

**A note on what triggers a build.** The APK is rebuilt on pushes that touch
`android/`, not on every push to `main`. A commit that only changes the Python
pipeline leaves the app unchanged, so the previous APK is still the current
one — rebuilding it would produce a different file with identical behaviour.

### Which build is on the phone

**Settings → Apps → Jordan Tenders** shows the version. A released build shows
the tag it was cut from with the `v` dropped, so `v0.1.0` shows as `0.1.0`.
A build from the Actions tab shows `0.0.<commit-count>-<sha>`, which names the
exact commit it came from.

The version code is the repository's commit count, so it always increases and
Android can tell a newer build from an older one. It will refuse to install an
older APK over a newer one, which is the correct behaviour and not a fault.

---

## Creating the token

The app needs a **fine-grained personal access token**, scoped to this one
repository.

**github.com → Settings → Developer settings → Personal access tokens →
Fine-grained tokens → Generate new token**

| Field | Value |
|---|---|
| Repository access | **Only select repositories** → this repository, and nothing else |
| Actions | **Read and write** |
| Contents | **Read and write** |
| Everything else | leave as **No access** |

That is the minimum that works, and here is what each one buys:

- **Actions: read** — list runs, check a run's status, list and download the
  artifacts. Everything the Latest, Portals and Files screens do.
- **Actions: write** — `POST .../dispatches`, which is the Run button. There is
  no narrower permission for it; read alone cannot start a run.
- **Contents: read** — read `portals.json`.
- **Contents: write** — commit a change to `portals.json`: switching a portal
  on or off, adding one, removing one. If you never intend to manage portals
  from the phone, set Contents to **Read-only** and everything except the
  Portals screen still works — the app will report the 403 in those words
  rather than as a mystery.

No organisation permissions. No other repositories. No `repo` classic scope —
a classic token is all-or-nothing across every repository you can see, which
is precisely what a fine-grained token exists to avoid.

Paste it into **Settings → GitHub token** in the app, then tap **Check it
works**. That runs two calls, because they answer different questions: one
proves the token is valid at all, the other proves it can see *this*
repository. A token scoped to the wrong repository passes the first perfectly.

### Where it is kept

`EncryptedSharedPreferences`, with its key held by the **Android Keystore** —
hardware-backed where the device has a secure element. It is:

- never in the APK, never in source, never in a log line;
- never shown back to you after saving, only described ("set, ending `a1b2`,
  93 characters");
- stripped out of every error the app displays, by exact match **and** by
  shape, so a credential in a GitHub error body is removed too;
- excluded from cloud backup (`allowBackup=false`) — a backed-up credential is
  a copy of it somewhere the Keystore does not reach.

**Fine-grained tokens expire.** GitHub does not warn you; it simply starts
answering 401, which the app reports as "GitHub refused the token". Generate a
new one and paste it in.

---

## Cutting a release

### From the phone, with no terminal

1. Open the repository's **Releases** page → **Draft a new release**.
2. **Choose a tag** → type a new one, `v0.2.0`, and pick **Create new tag on
   publish**. Set **Target** to the branch you want to release from.
3. Give it a title, write notes or leave them empty, and **Publish release**.

The **Android release** workflow picks it up, builds the APK and attaches it
to the release you just made. Refresh the page after a few minutes and the
`.apk` is there.

It triggers on **published**, not on saving a draft — a draft you are still
editing does not build. And anything you wrote in the notes is **kept**: the
install instructions and the checksum are appended below your text, not put in
place of it. Only a release with no notes at all gets the generated ones as
its whole body.

### From a terminal

```bash
git tag v0.2.0
git push origin v0.2.0
```

Either route ends in the same place. The workflow runs the unit tests, builds
the APK, names it after the tag, and publishes it with its SHA-256. If the
tests fail, no release is published.

**Note.** Publishing from the web form can deliver both a `release` event and
a tag `push` for the same tag, which would start two builds racing to upload
the same asset. A concurrency group keyed on the tag allows one at a time and
lets the newest win.

It can also be run from the Actions tab (**Android release → Run workflow**)
against a tag that already exists — useful for re-cutting one whose build
failed for a reason since fixed. If the release is already there, its APK and
its notes are **replaced**, and the log says which of the two happened. That
matters for a tag that has been moved: leaving the old release in place would
publish the wrong build under the right name.

The release notes are generated, and they say the APK is debug-signed and what
that means. They also repeat that nothing has been run on a device, because a
Releases page is exactly where that stops being obvious.

**Why a separate workflow from the build.** `android.yml` has a `paths:` filter
so it does not rebuild for a Python-only change — and a `paths:` filter applies
to tag pushes too. Putting the tag trigger there would silently skip a release
whenever the tagged commit touched nothing under `android/`, which is a release
that quietly does not happen.

---

## Signing

The APK CI builds is **debug-signed**. That is fine for installing on your own
phone and is what this repository does today.

**If you set up release signing:** the keystore and its password go in
repository secrets, never in the repository. `.gitignore` covers `*.jks`,
`*.keystore` and `local.properties`.

Two things to know before you do:

**Switching to release signing breaks the upgrade path once.** Android
identifies an app by its signature, so a release-signed APK will not install
over the debug-signed one already on the phone. You will have to uninstall
first, which loses the stored token and the cached report. Do it deliberately,
not on the morning you need a report.

**If you lose the release keystore, you can never update that install again.**
Same reason, permanently. Back it up somewhere you will still have in two
years.

---

## What each screen does

**Latest** — the opportunities from the most recent finished run: score,
title, donor, sector, deadline, flags. Tap a row to open the notice. Sort by
score or deadline; filter by donor and sector. It opens with the last report
it downloaded, with no network at all.

**Run** — the workflow's real inputs. Scope (everything open / only what is
new), a portal filter, and mode (report / diagnose). Live status while it runs.
`workflow_dispatch` answers 204 with no body — it does not say which run it
started — so the app watches for a new run to appear and says so while it does,
rather than showing the previous run as though it were the new one.

**Health** — every portal, in full: read, unavailable, not set up, or no
listing; how many notices it read, how many were in scope, and the failure reason
with the URL to check by hand. This table is the honesty mechanism and it is
never summarised away.

**Portals** — the list itself. Switch a portal on or off, add one by URL, or
remove one. **Every change is a commit to `portals.json`**, with a message
saying what changed and why, and the resulting commit sha is shown back —
"saved" is a claim, a sha is evidence.

**This screen is Jordan-only, and says so when it cannot help.** It edits
`jordan_tender_monitor/portals.json`. Point Settings at another monitor and it
refuses rather than showing that file: the Syria monitor keeps its portals in
`syria_tender_monitor/config.yml`, in a format this screen cannot describe, and
a save here would have committed to Jordan's configuration while the app was
running Syria's. **Test it** is refused for the same reason — `--probe` is a
Jordan-only mode.

Adding a portal has a **Test it** step, and Save is not available until it has
run. It dispatches a `--probe` run that fetches the page on GitHub's runner and
reports what every extraction layer found, including the rows. That is there
because committing a URL nobody has looked at is exactly how a portal ends up
reporting "unavailable" forever while looking like an honest failure — which is
what happened with KfW, and with ADFD.

Read the sample rows before saving. A high quality score means the page *looks
like* a listing; it cannot see a single column being wrong. GIZ once scored 1.00
with every deadline on the portal garbage.

**Files** — download the run's Word and Excel packs and open or share them.

**Settings** — token, repository, and the permissions documentation above.

---

## Before the app can do everything

**The workflow the app drives must be on the repository's default branch.**
`workflow_dispatch` only offers inputs that exist on the branch the workflow
file is read from, so until the change that added the `--probe` mode is merged
to `main`, the Portals screen's **Test it** step will be rejected by GitHub
with a 422. Reading runs, downloading reports and files, and starting an
ordinary run all work regardless.

---

## Things the app cannot do, and why

**Read the run page summary.** GitHub's REST API does not expose a job's step
summary — they are written to an internal container the artifacts API does not
list. The markdown you see on the run page is unreachable from any client. The
app reads the run's `*.json` artifact instead, which the workflow writes for
exactly this purpose, and which is better anyway: structured, with the portal
health table intact.

**Tell "not found" from "not allowed".** GitHub deliberately answers 404 for a
resource that exists but that your token cannot see. When the app says "either
it does not exist, or the token cannot see it", that is the whole truth
available.

**Recover an expired artifact.** Run artifacts are deleted after 90 days. The
app says "expired", not "download failed", because there is nothing to retry.

**Edit how a coded portal reads.** UNGM and the four REST APIs keep their fetch
logic in Python, and `portals.json` declares which fields those modules own.
The app shows them as read-only and says so; setting one in the file is
*rejected* by the loader rather than quietly ignored, so an edit that looked
applied and was not is impossible.

**Overwrite someone else's change.** A commit carries the file's sha as loaded.
If the file moved in between, GitHub refuses the write and the app says the
list changed rather than clobbering it.

---

## Background checks and notifications

The app checks whether a run has finished and tells you what it found. It does
**not** start runs — the monitor has its own weekday schedule on GitHub's
servers that fires whether or not this phone is awake.

**Intervals:** off (the default), hourly, every 3 hours, every 6 hours, or once
a day. The monitor produces one run per weekday at 07:17 Amman, so hourly is
enough to hear about it the same morning and nothing shorter is offered.

Hourly costs about 24 checks a day, at most 3 requests each, against a budget
of 5,000 an hour. **The constraint is battery and data, not the rate limit** —
so do not pick a longer interval to protect a limit that was never at risk.

**Wi-Fi only, unless you say otherwise.** Checking hourly over mobile data to
find out that nothing changed spends your allowance without asking.

**Two channels, so you can tune them apart:**

| Channel | Carries | Why separate |
|---|---|---|
| Run results | "12 new opportunities"; "No new opportunities — all 13 portals read" | Routine. Mute it in a busy fortnight if you like |
| Needs attention | "ACTION NEEDED — nothing could be read"; "3 of 13 portals unavailable"; "the monitor cannot check — token refused" | High priority. Muting results must never mute this |

A notification about unreachable portals opens **Health**, not the opportunity
list — a short report with no reason for it is worse than no report.

**"Last check" in Settings is the important line.** No notifications means
either no news or no checks, and only that line says which. It shows when the
app last reached GitHub, what it found, and how many checks in a row have
failed.

**Android decides when a background job actually runs.** The interval is a
floor, not an appointment; a sleeping phone can delay it considerably. If that
matters on a given morning, open the app and pull to refresh.

If the app cannot check for a reason a person has to fix — a refused token, a
missing permission, a repository it cannot see — it says so on the attention
channel straight away rather than going quiet. Temporary failures (no
connection, GitHub having an afternoon, a rate limit) retry with backoff and
only produce a notification after eight in a row, by which point the silence
would otherwise be indistinguishable from "no new tenders".

---

## Building it yourself

```bash
cd android
./gradlew assembleDebug        # app/build/outputs/apk/debug/app-debug.apk
./gradlew testDebugUnitTest    # the JVM tests
```

Needs JDK 17 and an Android SDK with API 35. CI does both on every push that
touches `android/`.


## Signing, and why an update used to fail

**Every CI build used to be signed with a different key.** Gradle signs debug
builds with `~/.android/debug.keystore` and *generates one at random when the
file is absent*. Every GitHub runner is a fresh machine with no keystore, so
each run produced an APK signed by a throwaway key — and Android refuses to
install one over another. The symptom is `App not installed`, which names no
cause; the only way through was uninstall and re-authenticate, on every update.

The build now signs with a shared key when CI can supply one, restored from a
repository secret. The key is **not in this repository** — it is public.

### Setting it up (once)

Create four repository secrets under **Settings → Secrets and variables →
Actions**:

| Secret | What it holds |
| --- | --- |
| `ANDROID_KEYSTORE_BASE64` | the keystore file, base64-encoded |
| `ANDROID_KEYSTORE_PASSWORD` | its store password |
| `ANDROID_KEY_ALIAS` | the key alias inside it |
| `ANDROID_KEY_PASSWORD` | the key password |

To make a keystore yourself, on any machine with a JDK:

```bash
keytool -genkeypair -v -keystore signing.jks -alias tender-monitor \
  -keyalg RSA -keysize 4096 -validity 10950 \
  -dname "CN=Tender Monitor"
base64 -w0 signing.jks        # paste this into ANDROID_KEYSTORE_BASE64
```

**Keep the file.** Losing it means the same problem again: no future build can
upgrade the installs signed with it, and everyone re-installs from scratch.

### With no secret set

The build still succeeds and still produces an installable APK. It just cannot
upgrade an earlier install, and the workflow emits a warning saying so — the
failure is announced at build time rather than discovered on a handset.

### Changing the key later

Any change of signing key breaks upgrades for every existing install, exactly
as the random-key situation did. There is no migration; it is uninstall and
re-authenticate for each device.

