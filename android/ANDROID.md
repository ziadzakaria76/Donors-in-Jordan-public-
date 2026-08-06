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
| **Unit tested** | Token redaction, the API client's failure paths (401 / 403-permission / 403-rate-limit / 404 / 410 / 5xx / offline), report parsing and schema refusal, the artifact zip reader |
| **NOT tested** | The Keystore-backed token store — `EncryptedSharedPreferences` needs a real Android Keystore and cannot run on a JVM. It is two AndroidX calls, deliberately with no logic around them |
| **NOT run on a device by anyone** | Every screen. No emulator, no handset. The first person to install this is the first person to see it render |

If something behaves differently from this document, this document is wrong.

---

## Installing it on the phone

No Android Studio, no laptop.

1. **Allow your browser to install apps.** Android blocks this by default.
   **Settings → Apps → (your browser) → Install unknown apps → Allow.** Exact
   wording varies by manufacturer; search settings for "unknown apps".
2. Open the repository's **Actions** tab on the phone, in a **mobile browser,
   not the GitHub app** — the app's run view does not show artifacts at all.
3. Choose the **Android app** workflow and open the newest green run.
4. Scroll to the **bottom**, to **Artifacts**, and tap
   `jordan-tenders-apk-<number>`.
5. It downloads as a **zip**. Open it in Files or Downloads, extract the
   `.apk`, and tap it.
6. Android will warn you the app is from an unknown source. That is expected:
   it is not from the Play Store.

**You have to be signed in to GitHub** to download an artifact, even on a
public repository. Signed out, the link bounces you to a sign-in page without
saying why.

APKs are kept for 90 days, like the report artifacts.

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
- **Contents: write** — commit a change to `portals.json`. **Phase 2 only.** If
  you never intend to add or disable a portal from the phone, set Contents to
  **Read-only** and everything except the Portals screen still works.

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

## Signing

The APK CI builds is **debug-signed**. That is fine for installing on your own
phone and is what this repository does today.

**If you set up release signing:** the keystore and its password go in
repository secrets, never in the repository. `.gitignore` covers `*.jks`,
`*.keystore` and `local.properties`.

And know what you are taking on: **if you lose the release keystore, you can
never update that install again.** Android identifies an app by its signature,
so a differently-signed APK is a different app — the only route is uninstall
and reinstall, losing the app's data. Back it up somewhere you will still have
in two years.

---

## What each screen does

**Latest** — the opportunities from the most recent finished run: score,
title, donor, sector, deadline, flags. Tap a row to open the notice. Sort by
score or deadline; filter by donor and sector. It opens with the last report
it downloaded, with no network at all.

**Run** — the workflow's real inputs. Scope (everything open / only what is
new), a portal filter, and mode (report / diagnose). Live status while it runs.

**Portals** — every portal, in full: read, unavailable, not set up, or no
listing; how many notices it read, how many were Jordan, and the failure
reason with the URL to check by hand. This table is the honesty mechanism and
it is never summarised away.

**Files** — download the run's Word and Excel packs and open or share them.

**Settings** — token, repository, and the permissions documentation above.

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

---

## Background notifications

**Not implemented yet — Phase 3.** The Settings screen says so rather than
showing a switch that does nothing. Today the app polls only while you are
looking at it.

---

## Building it yourself

```bash
cd android
./gradlew assembleDebug        # app/build/outputs/apk/debug/app-debug.apk
./gradlew testDebugUnitTest    # the JVM tests
```

Needs JDK 17 and an Android SDK with API 35. CI does both on every push that
touches `android/`.
