# GS3 Marketing Ops — decisions log

Every decision, assumption and answer that shapes this app, with the date it was
taken. Re-read this at the start of every milestone.

Brief: *Claude Code Build Brief — "GS3 Marketing Ops" Android App*, v1.4,
10 August 2026.

---

## 0. Blocking questions awaiting a written answer

These two are not preferences and cannot be defaulted. Both are recorded here
the moment they are answered, with the date and the reference.

| # | Question | Status | Answered on | Reference |
| --- | --- | --- | --- | --- |
| B-1 | Has a written statement been obtained from the Department of Lands and Survey confirming the classification of this project's units and that non-Jordanians may own them? | **Answered — no.** No longer blocks v1: the track it gated was removed instead (D-23) | 2026-08-29 | Owner |
| B-2 | Does the signed contract actually contain (a) the named finishing-specifications annex, (b) a delay penalty in the buyer's favour, (c) the two-year finishing and ten-year structural warranty, and (d) the quarterly photographic progress report? | **Answered in part — (a) and (d) yes; (b) and (c) not confirmed** | 2026-08-29 | Owner |

**B-1 answered 2026-08-29: no.** The statement has not been obtained.

**And later the same day the owner closed the question by removing the track.**
The consequences originally recorded here — a blocking gate, `NONJO` campaigns
that cannot be activated, a persistent Dashboard banner — are all gone, because
the module they guarded is gone. **This is not the gate being opened.** Nothing
in v1 markets to, processes, or promises anything to a non-Jordanian buyer, and
there is no longer a locked door to unlock: see **D-23** below for what was
deleted and **D-24**, **D-25** and **D-26** for the three consequences that had
to be decided along the way.

B-1 therefore stops being a blocker for v1 and becomes a precondition for ever
putting the track back. Whoever revives it needs the Department of Lands and
Survey statement *and* the legal opinion first, and rebuilds from D-23 rather
than re-enabling something dormant.

**B-2 answered 2026-08-29, in part.** The owner confirms the signed contract
carries **(a)** the finishing-specifications annex and **(d)** the quarterly
photographic progress report. **(b)** the delay penalty and **(c)** the two-year
and ten-year warranty are **not confirmed**.

This is the case the four-rows-not-one-switch design was for, and it is now
carrying it: (a) and (d) are seeded confirmed and dropped from the banned-phrase
guard, so client-facing text may use them; (b) and (c) stay unverified and stay
banned. No clause references were supplied, so `contractReference` is null on
both confirmations — worth filling in when someone next has the contract open,
because without it the next reader has to ask a person rather than open a file.

"Not confirmed" means nobody has checked, **never** "verified absent". Both
readings keep the claim out of a client's hands, so the app behaves identically
either way; the distinction matters only to whoever is still chasing (b) and (c).

One consequence worth stating plainly: (d) was previously flagged during
authoring, when a delivery objection offering "regular photographic updates on
progress" was caught as too close to an unverified promise. That promise is now
verified, so the phrasing is permissible. The catch was still correct at the
time — it was unverified when written.

---

## 1. Environment (2026-08-10)

Verified by running the checks, not by assumption. Actual output is in the
milestone report.

| Component | Status |
| --- | --- |
| JDK | ✅ OpenJDK 21.0.10 at `/usr/lib/jvm/java-21-openjdk-amd64` |
| Gradle | ✅ 8.14.3 at `/opt/gradle` (the project will use its own wrapper) |
| `services.gradle.org`, `plugins.gradle.org`, Maven Central | ✅ reachable |
| Android SDK | ❌ **not installed and not installable in this environment** |
| `dl.google.com` | ❌ **denied by the egress policy (HTTP 403 on CONNECT)** |

### D-1 — The build is blocked on network egress, and this is not routed around

`dl.google.com` is refused by this session's egress proxy. That single host
carries everything an Android build needs:

- the SDK itself — `platforms;android-36`, `build-tools;36.0.0`, `platform-tools`;
- **and** every Google-hosted Maven artifact. `maven.google.com` is reachable but
  only 301-redirects to `dl.google.com`, so the Android Gradle Plugin, all of
  AndroidX, Compose, Room, WorkManager and Hilt's AndroidX components cannot be
  resolved either. Maven Central does not mirror them (checked: 404).

Debian packages an Android SDK, but only up to platform 23; the API-36
installer packages fetch from the same blocked host.

**Decision:** report the blocked host and stop, rather than fetch build plugins
from a third-party mirror. Two reasons, and the second is the stronger one: the
proxy's own guidance is not to route around an organisation policy denial, and
pulling the Android Gradle Plugin from an unofficial mirror puts an unverified
binary into the build of an app that will hold client contact details.

**Fix:** allow `dl.google.com` for this environment (add
`android.googlesource.com` too if source-level dependencies are ever needed).
Nothing else about the plan changes, and no work already done is wasted.

#### D-1 is resolved (2026-08-15)

The row above and this decision are left as written, because they are the record
of what was true on 10 August. They are no longer true. On an environment
created specifically to unblock this work, with `dl.google.com` and
`maven.google.com` on a custom allowlist **extending** rather than replacing the
default package-manager list:

| Check | Result |
| --- | --- |
| `curl -o /dev/null -w "%{http_code}" https://dl.google.com/` | **302** — Google's own redirect to `/chrome`, with `server: downloads`, not a proxy denial |
| `curl … /android/repository/repository2-3.xml` | **200**, 408,907 bytes — a real artefact, not an error page |
| `curl … https://repo1.maven.org/maven2/` | **200** — the existing Kotlin build is unaffected |
| Android SDK | ✅ `platform-tools` 37.0.1, `platforms;android-36` rev 2, `build-tools;36.0.0`; licences accepted non-interactively |

Both halves of that allowlist mattered. Had Maven Central been refused, it would
have meant the "also include the default list of common package managers" box
was left unticked and Custom had *replaced* the trusted list rather than
extended it — which would have broken the Kotlin build that was already green.
It was not refused.

### D-2 — Version matrix

The brief forbids "latest stable" and requires an explicit matrix (§2.3 trap 1).
Everything below is now **confirmed**: it resolves, it compiles, and it produces
an APK. Nothing here is marked proposed any more.

| Component | Pin | Status |
| --- | --- | --- |
| JDK | 21.0.10 | ✅ confirmed |
| Gradle | 8.14.3 (wrapper committed) | ✅ confirmed |
| Kotlin | 2.1.21 | ✅ confirmed — compiles with `allWarningsAsErrors` |
| JUnit 5 | 5.11.4 | ✅ confirmed — permitted for the pure-Kotlin module by §2 |
| JaCoCo | 0.8.12 | ✅ confirmed |
| Android Gradle Plugin | **8.13.2** | ✅ confirmed. The newest *stable* 8.x. 9.x exists and is out of scope |
| KSP | **2.1.21-2.0.2** | ✅ confirmed. Prefix is the Kotlin pin by construction. `kotlin-kapt` appears nowhere |
| compileSdk / targetSdk | **36** | ✅ confirmed by `aapt2 dump badging`: `compileSdkVersion='36'`, `targetSdkVersion:'36'` |
| minSdk | **26** | ✅ confirmed — `minSdkVersion:'26'` |
| Compose | BOM **2025.06.01** | ✅ confirmed. One BOM pin; no Compose artifact carries its own version |
| Compose compiler | Kotlin plugin 2.1.21 | ✅ confirmed. Since Kotlin 2.0 it *is* the Kotlin version, so it cannot drift |
| Material3 adaptive | **1.1.0** | ✅ confirmed. Versioned separately from the BOM |
| AndroidX core / activity / lifecycle / navigation / window | 1.16.0 / 1.10.1 / 2.9.1 / 2.9.0 / 1.4.0 | ✅ confirmed |
| Room | **2.7.2** | ✅ confirmed. Compiler via KSP |
| WorkManager / DataStore | 2.10.2 / 1.1.7 | ✅ confirmed |
| Hilt | **2.56.2** (+ `hilt-navigation-compose` 1.2.0) | ✅ confirmed. Compiler via KSP |
| SQLCipher | `net.zetetic:sqlcipher-android` | not yet pinned — arrives with the encrypted store at Milestone 8 |
| Robolectric | **4.16.1** | ✅ confirmed at Milestone 1. 4.15.1 was tried first and rejects `sdk = 36` with `UnknownSdk`; 4.16.1 is a stable release, not a candidate |
| Roborazzi | **1.46.1** | ✅ confirmed. JVM-only; no emulator is used or needed |
| JUnit 4 | **4.13.2** | ✅ confirmed. `:app` only, because the Robolectric runner is a JUnit 4 runner. `:domain` keeps JUnit 5 |
| kotlinx-coroutines-test | **1.10.2** | ✅ confirmed |

**Why these are not the newest of each.** The anchor is Kotlin 2.1.21, which was
already confirmed against `:domain`. A library compiled by a *newer* Kotlin
carries metadata this compiler refuses to read, so "newest of each" is not a
combination that builds — it is a set of numbers that looks current. The
AndroidX and Compose pins are therefore chosen from Kotlin 2.1.21's own era.
They are old on purpose: this is the step-down rule applied deliberately rather
than an accident of picking stale versions.

Standing rule: on a version conflict, **step down** to the last known-good
combination. Never step forward into a release candidate, and never bump a
dependency in the middle of a milestone.

### D-7 — Build the pure-Kotlin domain first, while the Android half waits

D-1 blocks Android, but it does not block everything. The business rules the
brief actually cares about — funnel maths, budget allocation and seasonal
normalisation, fee calculation, SLA timing across time zones, price-per-m², the
discount guard, the campaign-code builder — are pure functions over plain data
with no Android dependency at all. Kotlin, JUnit and JaCoCo all come from Maven
Central, which is reachable.

So `:domain` was built and tested for real rather than waiting: 118 tests
passing at 99.3% line coverage, against the ≥80% gate. `verifyStrings` likewise
needs no Android plugin, so the bilingual guard runs today and was proved to
fail on all three of its cases.

This is not merely making use of the time. It front-loads the work most likely
to be wrong — arithmetic and time zones — into the place where it is cheapest to
test, and it means the Android milestones, when they start, are wiring a proven
core to screens rather than inventing and debugging both at once. `google()` is
deliberately absent from `settings.gradle.kts` until `:app` exists, so today's
build does not fail on a repository it has no need for yet.

---

## 2. Verification of the brief's own data (2026-08-10)

Done before any code, because seed data that is wrong is more expensive to find
later. Two independent sources agree: the brief's §8.1 schedule, and
`website/assets/js/data.js` in this repository, which the live site is built
from. Every unit's internal area, external area and price matches across both.

Arithmetic, all confirmed:

| Assertion | Computed | Verdict |
| --- | --- | --- |
| 14 units, 2,320 m² internal, 620 m² external | 14 / 2,320 / 620 | ✅ |
| Gross development value 1,496,000 JOD | 1,496,000 | ✅ |
| Weighted average 645 JOD/m² | 644.83, on internal area only | ✅ (rounds to 645) |
| External-track budget 7,200 = 4,680 + 2,520 | 7,200 (65% / 35%) | ✅ |
| Market rows sum to their track totals | 4,680 and 2,520 exactly | ✅ |
| Overall funnel 900 → 315 → 95 → 52 → 11 | 315 / 94.5 / 52.0 / 10.9 | ✅ |
| External funnel 160 → 48 → 17 → 3 | 48 / 16.8 / 3.02 | ✅ |
| External share of sales ≥ 27% | 3 of 11 = 27.3% | ✅ consistent |

### D-3 — The 45 JOD target is per *raw* lead, not per *qualified* lead

The one material defect found. §5.4 and quality gate §10 both call 45 JOD the
target **cost per qualified lead** for the external track. The arithmetic says
otherwise:

- 7,200 JOD ÷ 160 raw leads = **45.00 JOD exactly** — the figure is the planned
  cost per *raw* lead, to the fils;
- 7,200 JOD ÷ 48 qualified leads = **150 JOD**, which is what the same budget
  implies per qualified lead.

Read as written, the app would judge the external track against a target 3.3×
harder than its own budget allows, and the "persistently above 60 JOD" stop rule
would fire permanently from the first week and never clear — training the team to
ignore it, which is worse than having no stop rule.

**Decision, pending the owner's confirmation:** implement 45 JOD as the target
cost per **raw** external lead, and compute cost per **qualified** external lead
against 150 JOD, with the 60 JOD stop-rule threshold scaled to the same basis
(200 JOD per qualified lead). Both thresholds are editable in Settings, so a
correction costs nothing. Flagged to the owner — see the open question below.

#### Answered 2026-08-16 — the 45 JOD figure is removed entirely

The owner's instruction was "remove the 45 JOD". So it is gone rather than
reinterpreted: `CplTargets.perRawLead` no longer exists, and there is now
exactly **one** target for the external track — 150 JOD per qualified lead,
with a recorded decision forced above 200. Both are still editable in Settings.

This is the cleaner answer, and better than either branch of the original
question. The tension in D-3 came from holding two targets that could disagree
about whether the same month went well; with one basis there is nothing to
reconcile, and the basis kept is the one the budget actually plans for.

Cost per raw lead is still **measured** — `ChannelSpend.costPerRawLead` is
untouched, and the arithmetic that made 45 suspicious in the first place
(7,200 ÷ 160 = 45.00 to the fils) is still asserted by a test. What no longer
exists is a target to score it against.

Two tests hold the line: one asserts the qualified-lead target still matches the
budget's own arithmetic, and one asserts structurally that no `perRawLead` field
has reappeared — so a future reintroduction fails the build and sends whoever
did it back to this entry, instead of a second contradictory target creeping in
unnoticed.

### D-4 — Monthly budget is derived, never stored

The brief's monthly column is the annual figure ÷ 12, rounded. Those roundings
do not re-sum: the expatriate monthly rows total 389 JOD against a true 390.
The app therefore stores **annual** figures only and derives monthly on demand,
so a rounding artefact can never accumulate into a 12 JOD hole in the plan. The
monthly numbers shown match the brief's table.

### D-5 — Working days contradict the company's own published hours

Discovery default B1 proposes Sunday–Thursday with Friday and Saturday as the
weekend. The company's live website publishes «السبت – الخميس، ٩:٠٠ صباحاً – ٦:٠٠ مساءً»
— *Saturday* to Thursday, 09:00–18:00. This matters directly: business hours
decide when the 15-minute first-response SLA runs and when an out-of-hours
enquiry rolls to 10:00 the next working morning. Getting it wrong silently
mis-times every reminder on a Saturday. Raised as question B1 rather than
defaulted.

### D-6 — Seasonal multipliers need a composition rule

The brief fixes the annual total while multipliers scale each month, so the
months must be normalised: `spend(month) = annual × m(month) ÷ Σ m`. Two gaps
the brief leaves open, decided here:

- months named by no season take a multiplier of 1.0;
- where two multipliers land on the same month — Ramadan or an Eid falling
  inside another season — they **compose by taking the maximum, not the
  product**. Multiplying would let a Ramadan-in-summer month take 1.98× and
  quietly starve the rest of the year to pay for it.

Ramadan and Eid dates are user-settable per year, never hardcoded.

### D-8 — Any text matching folds Arabic-Indic digits first

Found by a failing test, and it would have shipped as a quiet nuisance.

The app offers ٠-٩ as a numerals setting, so an Arabic ad reasonably reads
«شقة ١٥١ م² … بسعر ٩٠٬٠٠٠ د.أ» while the unit record holds `151` and `90000`.
The ad-copy checklist compared the two literally, reported the area and price as
missing from correct copy, and would have taught the writer to ignore the
checklist — which is worse than not having one.

The rule, which applies anywhere the app matches typed text against stored
numbers: **fold Arabic-Indic (and extended Arabic-Indic) digits to Western and
drop grouping separators on both sides before comparing.** `CopyRuleChecker.foldDigits`
is the implementation and is tested directly.

The same failure has an Arabic-morphology twin, fixed alongside it: markers for
Arabic phrases match on stems, not whole words. The company's own site writes
«صور الواجهات تصاميم ثلاثية الأبعاد», and neither «تصميم» nor «ثلاثي الأبعاد» is a
substring of that. Matching «تصام»/«تصمي» and «ثلاثي» catches singular and
plural, masculine and feminine, without needing a morphological analyser.

### D-9 — Funnel counts are cumulative reach, and a lost lead keeps its history

A lead standing at Negotiation has passed through Qualified and Viewing.
Counting only where each lead stands *now* reports a conversion of zero on a
pipeline that is working perfectly, so the funnel report counts every stage a
lead reached.

The consequence for lost leads is the one that matters: a lead lost after a
viewing still counts toward the viewing stage. Dropping it instead would mean
losing a buyer retroactively *improves* the viewing-to-offer rate — the report
would look better the more sales were lost. Where a lead's furthest stage was
never recorded, it counts as having reached the enquiry stage and no further.

### D-10 — `UnusedResources` reports but does not fail the build, until Milestone 10

Android Lint runs with `warningsAsErrors = true`, which is the right default and
is why `abortOnError` is on. It promotes `UnusedResources` to an error, and that
one check does not fit how this project is built.

The Arabic string file is the **specification**, authored ahead of the screens
that read it — that is the whole point of "Arabic is the original text, not a
translation". At Milestone 0 there are five screens and 96 keys, so 80 keys are
correctly reported as unused: every one belongs to a screen scheduled for a
later milestone. Under `warningsAsErrors` that means each milestone's build
fails on account of the milestones not yet written.

The three ways out, and why this one:

- delete the unused keys and re-add them per milestone — destroys authored
  Arabic, and reduces the string file from a specification to a changelog;
- add a lint **baseline** — hides today's findings from tomorrow, and would
  swallow genuinely unused keys added later. No baseline file exists in this
  project, deliberately;
- **downgrade this one check to informational, and put back its teeth at
  Milestone 10.** Chosen. It still runs, and every key it finds is still listed
  in `lint-results-debug.html`, which CI uploads on every run.

At Milestone 10 every screen exists, so an unused key means a key nobody wired
up — a real defect — and `informational += setOf("UnusedResources")` comes out
of `app/build.gradle.kts`. Nothing else is downgraded, and nothing is disabled.

### D-11 — The `-v26` mipmap qualifier stays, against Lint's advice

Lint's `ObsoleteSdkInt` says `mipmap-anydpi-v26` is pointless when minSdk is 26,
and recommends a bare `mipmap-anydpi`. Following that advice breaks the build:
AGP's resource merger drops the renamed folder silently — the files never reach
`packaged_res` — and the build then fails at link time with
`AAPT: error: resource mipmap/ic_launcher not found`. Reproduced twice, and
confirmed not to be caused by `resourceConfigurations` by removing that setting
and rebuilding.

The suppression therefore lives in `app/lint.xml`, scoped to that one folder and
carrying the evidence, so the check keeps working on every other folder. This is
the standing rule for that file: one issue, one path, and the reason it is a
false positive. Anything that is a real finding gets fixed instead.

### D-12 — The repository's own `.gitignore` was silently eating the app's source

The root `.gitignore` carries `**/data/*` and `**/output/*`, which keep the
tender monitor's local state out of version control. Both patterns are
unanchored, so they also match `app/src/main/kotlin/.../leads/data/` — the data
layer of every feature, in an app whose packages are organised as a `ui`/`data`
split per feature.

Left alone this fails in the worst way available: `git add` skips those files
without saying so, the branch builds perfectly on the machine that wrote it, and
CI fails pointing at a missing class rather than at a `.gitignore`. Two
negations in `gs3_marketing_ops/.gitignore` re-include `app/src/**` and
`domain/src/**`. Verified with `git add --dry-run` on a real path under a
feature `data/` directory, and verified in the other direction too — a `data/`
directory elsewhere in the module is still ignored, so the root rule still does
its job.

### D-13 — The language switch overrides composition locals; it does not restart the activity

The platform's per-app locales (`LocaleManager`) need API 33, or AppCompat for
the backport — and this app has one `ComponentActivity` and no XML views, so
AppCompat would be a library added purely to name a style. Both routes also
**recreate the activity**: the screen blinks and anything half-typed is gone.

`Gs3Localized` instead provides `LocalContext` (with localised resources),
`LocalConfiguration` and `LocalLayoutDirection`, so the switch re-composes in
place. A salesperson can flip to English to show a client a screen and flip back
without losing the lead they were part-way through entering.

One trap inside it is worth keeping: `createConfigurationContext` returns a
context that is **not** wrapped around the activity. Handing that straight to
`LocalContext` gives correct strings and quietly breaks every later piece of
code that walks `baseContext` to find the hosting activity — intents, biometric
prompts, permission requests. `LocalizedContextWrapper` wraps the original
context and overrides only `getResources`/`getAssets`, so the activity chain
survives.

### D-14 — Arabic month names are written out, not taken from the JVM

`Locale("ar")` gives «يناير, فبراير, مارس» — the Egyptian and Gulf names. Jordan
writes «كانون الثاني, شباط, آذار». They are not interchangeable to a reader: a
Jordanian client seeing «يناير» on a payment schedule is looking at a foreign
document. Worse, the JVM's answer for a locale tag is not always Android's, so
the date on screen and the date in an exported PDF could disagree while both
were "correct". `DateFormat` therefore carries all three sets of names —
Gregorian Arabic, Gregorian English, Hijri — explicitly, and a test asserts
«كانون الثاني» and asserts the absence of «يناير».

### D-15 — Two defects the screenshots caught that the tests did not

Both were found by *looking at* the generated PNGs, which is the argument for
generating them from Milestone 1 rather than Milestone 9.

**A digit range reverses in Arabic-Indic.** The numerals setting read
`Arabic-Indic digits (٠–٩)` and rendered as `(٩−٠)` — nine to zero. Arabic-Indic
digits are bidi class *Arabic Number*, so a neutral dash between two of them
resolves right-to-left and swaps the endpoints. Wrapping it in an LTR isolate
does **not** fix it, which was tried first: the isolate sets the surrounding
direction, not the resolution of neutrals between two AN runs. The fix is to
stop expressing it as a range — the setting now shows a sample, `١٢٣٤`, which is
a single number run, cannot reorder, and shows the reader the actual glyphs.
The general rule stands: never put a bare dash between Arabic-Indic numerals.

**The screenshots were not being taken at all.** `captureRoboImage` is a silent
no-op unless Roborazzi is in record mode. The four tests passed, the report was
green, and no PNG existed. Fixed in two independent places, deliberately: the
test task sets `roborazzi.test.record`, *and* each test asserts that the file it
just captured exists and is larger than 10 kB. The assertion is the one that
matters — it does not depend on a line of build configuration staying put.

### D-16 — Language splitting is disabled in the bundle

Lint's `AppBundleLocaleChanges` caught a defect that would have shipped. An App
Bundle is split by language by default and a device installs only the locales it
is configured for, fetching the rest through Play. This app switches language at
runtime, holds no INTERNET permission, and is sideloaded. On a phone set to
English it would have installed with no Arabic resources — and Arabic is the
language the app opens in. `bundle { language { enableSplit = false } }` is the
fix lint asks for, not a suppression of it.

### D-17 — Unit tests run on the debug variant only

`ui-test-manifest` supplies the `ComponentActivity` that `createComposeRule`
launches, and it is `debugImplementation` because that activity has no business
in a shipping APK. Robolectric resolves the launcher intent against the
variant's merged manifest, so the release unit-test run failed with "Unable to
resolve activity for Intent".

Making it pass would mean adding test scaffolding to the release manifest —
shipping test code to clients so that a duplicate test run goes green. Unit
tests are not processed by R8, so both variants execute identical bytecode; the
release run was adding no coverage and doubling the time. Every test still runs,
in full, on every `check`.

### D-18 — `OldTargetApi` is disabled, because it contradicts the pinned targetSdk

Lint's `OldTargetApi` wants `targetSdk` raised to the newest platform it can
find. Following that here would break a rule the project rests on: 36 is pinned
deliberately (brief §2.1), it already clears the Play floor for 31 August 2026,
and anything above it today is a **preview** API — precisely the "step down on
conflict, never forward into a release candidate" case the version matrix exists
to prevent. The check is not wrong in general; it is wrong about this project.

What made it expensive to diagnose is that it is **environment-dependent**. The
check compares `targetSdk` against the newest platform *installed on the
machine*, so it stays silent in a container holding only `android-36` and fails
on a CI runner whose image ships a newer one. `./gradlew check` was genuinely
clean locally while the identical commit failed in CI four times running — the
same code, the same lint version, two different verdicts. A check whose result
depends on which machine ran it cannot be a gate, so it is disabled outright
rather than left to chance.

Deliberately **not** fixed with a lint baseline. A baseline would suppress every
other lint error present today as well, which is the opposite of what this gate
is for. `abortOnError = true` and `warningsAsErrors = true` stay exactly as they
are; this removes one named check and nothing else.

**Confirmed by reproduction, not by reasoning alone (2026-08-16).** The
environment-dependence above was a hypothesis until it was made to happen on
purpose: installing `platforms;android-37.1` into the build container made the
identical commit fail locally with the identical message, and the fix made it
pass again with that platform still installed.

That platform is now **kept installed** in the build environment. The local
build therefore runs under the stricter of the two conditions, so this class of
"green here, red in CI" cannot recur silently for any check that grades against
the newest installed SDK.

A second thing made this expensive, and it is fixed separately in
`.github/workflows/tests.yml`: the failure was unreadable. GitHub serves raw job
logs *and* uploaded artifacts from a storage host that a restricted egress
allowlist does not cover, so four red runs arrived with no stated reason. The
job now writes its failure to the step summary **and** emits it as an
`::error::` annotation — annotations being the only one of the two that comes
back through the REST API.

### D-19 — The seed runs on every launch, and every insert is `IGNORE`

Reference data is not seeded in `RoomDatabase.Callback.onCreate`, which is the
obvious place for it. `onCreate` fires exactly once in a database's life, so a
template or objection added in a later release would never reach anyone who
already had the app — on an offline app the only way to get it would be to
reinstall, which means losing their data to receive a corrected sentence.

So the seed runs on every launch, which makes overwriting someone's work the
risk to design against. Every insert is `OnConflictStrategy.IGNORE`: a row whose
primary key exists is left exactly as it is. `REPLACE` would silently undo a
reworded template or a ticked contract claim on the next launch — and only for
the people who had customised something, which is the worst possible
distribution for a bug.

Four tests hold it: a re-seed leaves counts unchanged; a unit edited to
Contracted with an agreed price and justification survives a re-seed; a cleared
eligibility gate is never re-closed; a confirmed contract claim stays confirmed.

### D-20 — Units and budgets are derived from `:domain`, never re-typed

`Gs3Seed.units()` maps `Gs3Schedule.apartments`; `Gs3Seed.marketBudgets()` maps
`Gs3Budget.externalTrackMarkets`. Neither re-types a figure.

Fourteen prices typed a second time would be a third copy — after the brochure
and `website/assets/js/data.js` — and the way that failure surfaces is a client
being quoted a price the company's own website does not show. The seed test
asserts whole-object equality against the domain rather than spot-checking
fields, because a right price with a wrong priority class is still a defect.

### D-21 — `fallbackToDestructiveMigration` is absent, and a test proves it

It means "if the schema moved and nobody wrote a migration, delete the user's
data and start again". This database is the only copy of every lead, agreed
price and discount justification the company holds; there is no server to
re-sync from, and the encrypted backup is a manual act someone may not have
performed recently.

An absent line is precisely what code review does not catch, so the test is
behavioural: it stamps the database file with a version this build knows nothing
about, opens it through `Gs3Database.build` — the same builder Hilt uses, not a
replica — and asserts Room *refuses*, then asserts the fourteen units are still
in the file afterwards.

**The guard was proved to fail before being relied on.** Adding
`fallbackToDestructiveMigration(dropAllTables = true)` to the builder makes the
test fail; removing it makes it pass. A guard that has never been seen to fail
is not yet a guard.

Migrations are wired from version 1 with an intentionally empty `MIGRATIONS`
array, so writing the first real one is filling in an established mechanism
rather than a decision taken in a hurry next to a tempting one-line alternative.

### D-22 — `verifyStrings` could not see the seeded text, so a test does

`verifyStrings` polices `strings.xml`. The moment templates and objections were
authored, client-facing text also existed in Kotlin seed data — outside
everything that guard checks. That was a real gap, opened by this milestone.

`SeedContentTest` closes it by scanning every seeded template and objection, in
both languages, for two families of phrase:

- the four **B-2 contract claims** — the finishing annex, the delay penalty, the
  warranty, the quarterly progress report. Nobody has read the signed contract
  and confirmed any of them, so none may be promised;
- the standing **forbidden phrases** — a fee exemption the company cannot grant,
  an approval belonging to the authorities, a return belonging to the market.

It caught its first defect during authoring: the delivery-timing objection
originally offered "regular photographic updates on progress", which is close
enough to the unverified quarterly photographic progress report to be a promise
the team might not be able to keep. It now commits to keeping the client
informed — which the app's own ten-day external-track update rule already backs
— and says that what follows from a delay is set by the contract text.

The non-Jordanian objection is written for the world as it is: it defers to the
competent authorities and promises nothing. It was rewritten on 2026-08-29 — see
D-23 — because its original wording said the statement and the legal opinion
were being sought, and after the owner dropped the track nobody was seeking
them.

### D-23 — The non-Jordanian track is removed from v1 (2026-08-29)

The owner's decision, taken after B-1 came back "no": rather than ship a module
that stays permanently locked behind a gate nobody can open, drop the track.

**This is a removal, not an unlocking.** The distinction is the whole point. An
app carrying a locked non-Jordanian module is one settings toggle away from
marketing to buyers whose eligibility nobody has confirmed in writing. An app
with no such module is not. So the gate, the eight-step journey, the approval
authorities, the document checklist and the `NONJO` track were **deleted** —
not commented out, not left as unreachable enum values.

Gone, in full:

| Deleted | Was |
| --- | --- |
| `domain/nonjordanian/BuyerFile.kt` and its test | `EligibilityGate`, `NonJordanianFile`, `JourneyStep`, `StepStatus`, `DocumentItem`, `DocumentProvider`, `ApprovalAuthority` |
| `Track.NONJO` | the third track |
| `CampaignSpec.canActivate` | the gate seen from the campaign side. With no gated track it had nothing left to refuse |
| `eligibility_gate` table, `EligibilityGateEntity`, the three gate DAO methods | the persisted answer |
| Four `market_budgets` rows | IRQ, GULF, PSE, TEST — see D-24 |
| Two `NationalityCategory` values | `ARAB_NON_JORDANIAN`, `NON_ARAB` — see D-25 |
| Eight `strings.xml` keys, in **both** locales | every `gate_*`, plus `track_nonjo` and `disclaimer_non_jordanian`. 106 keys down to 98, both files in step |

**Kept, deliberately.** The four B-2 contract claims: they are terms of the
signed contract every buyer signs, not a non-Jordanian matter, and B-2 answered
(a) and (d) on the same day. They only ever *lived* in a package called
`nonjordanian` — which was wrong about them before the track went — so the file
moved to `compliance/data/ContractClaims.kt` and nothing about it changed.
`LossReason.ELIGIBILITY_OR_APPROVAL` is kept too: a bank refusal and a company
approval are both eligibility problems, and deleting the reason would erase the
history of every lead already lost for one.

**The objection stays, rewritten.** `non_jordanian_eligibility` is the scripted
answer to "I am not Jordanian — may I own?". Dropping a marketing track does not
stop that question being asked at a stand, and the objection library exists so
that nobody has to invent an answer under pressure — an invented answer is
exactly how an over-promise reaches the buyer this app is most exposed on. But
the old text said the written statement and the legal opinion "are being sought"
and undertook to pass the answer on, and after this decision nobody is seeking
them. A promise to report back that nobody is chasing is worse than no promise.
The replacement states that no written statement is held, promises nothing,
offers nothing, refuses nobody, and points at the Department and a lawyer. A
test asserts the stale sentences have not come back.

**Room: a real migration, and the destructive fallback stays absent.** Version
1 → 2 is `Gs3Database.MIGRATION_1_2`. It drops `eligibility_gate` and — the half
that is easy to miss — **deletes the four `NONJO` rows from `market_budgets`**.
That table is shared, and the seed is insert-only with `OnConflictStrategy.IGNORE`
by design (D-19), so a phone upgraded from version 1 would otherwise show 2,520
JOD of non-Jordanian media forever, on a track the app no longer has. The
`MIGRATIONS` array created empty at version 1 is what this filled in; the
builder was already wired for it and did not change.

`DatabaseMigrationTest` builds a real version 1 database — reading the
`CREATE TABLE` statements out of the **committed** `schemas/…/1.json` rather
than retyping them, because a retyped schema tests the retyping — then opens it
through `Gs3Database.build`. **Both halves were proved to fail before being
relied on:** removing the `DELETE` fails it, removing the `DROP TABLE` fails it,
and restoring each makes it pass. `fallbackToDestructiveMigration` is still
absent and the test that proves it is untouched.

### D-24 — The four non-Jordanian market rows are deleted, and the local track absorbs the money

**Needs the owner's confirmation.** The default applied is the conservative,
reversible one.

The external track was 7,200 JOD: expatriates 4,680 plus non-Jordanians 2,520
(IRQ 1,260, GULF 560, PSE 420, TEST 280). Those four rows are deleted with the
track. Total paid media stays at **18,000** — it is the approved annual figure
and it is editable in Settings — so the external track becomes expatriates alone
at 4,680, and `localTrackTotal` rises from 10,800 to **13,320** by the existing
subtraction, `local = total − external`. Nothing was re-derived to produce that
number; it falls out of arithmetic that was already there.

The tests were changed to the new truth rather than kept green. The old
`the external track takes forty per cent of paid media, split sixty-five
thirty-five` asserted two figures that described a track which no longer exists,
and the honest replacement is not a re-split — it is that there is nothing left
to split. The external share is now 26% of paid media, all of it expatriate.
**Inventing new market rows to keep a 65/35 assertion passing was available and
was not done.**

**What this does not settle.** The 2,520 lands on the local track because that
is where the subtraction puts it, not because anyone decided local media should
grow by a quarter. Withdrawing it from the plan instead is a one-line change to
`totalPaidMedia`, and is the owner's call.

### D-25 — `ARAB_NON_JORDANIAN` and `NON_ARAB` are removed, not remapped

**Needs the owner's confirmation.**

Both mapped to `Track.NONJO`. With the track gone they have no honest track left,
and the tempting alternative — point them at `EXPAT` — would have filed a
non-Jordanian buyer as a Jordanian expatriate in the single field the entire
process is chosen from. It would have looked healthy on every screen and been a
lie in the database. So `NationalityCategory` is `JORDANIAN_RESIDENT` (LOCAL)
and `JORDANIAN_EXPATRIATE` (EXPAT), and `Track` is `LOCAL` and `EXPAT`.

`Track.isExternal` stays meaningful and stays as it was: `!= LOCAL`. It still
carries the 45-day staleness window and the 10-day update promise, which were
never non-Jordanian-specific — an expatriate lead four time zones away needs
both for the same reason it always did.

Two tests assert the *shape* rather than a value: `Track.entries` is exactly
`[LOCAL, EXPAT]` and `NationalityCategory.entries` is exactly the two Jordanian
ones. Reintroducing either enum value fails the build and sends whoever did it
here, instead of a track with no gate behind it reappearing quietly.

### D-26 — The 150 JOD qualified-lead target is left alone, and no longer matches the budget

**Needs the owner's confirmation.** This one is not in the brief that asked for
the removal; it was found while doing it.

D-3 settled on one target for the external track: 150 JOD per qualified lead,
with a recorded decision forced above 200. That 150 was not a preference — it
was 7,200 ÷ 48, the budget's own arithmetic. Removing the non-Jordanian track
takes the external budget to 4,680, and the same division gives **97.500**. The
target and its budget no longer agree.

The target is deliberately **left at 150**. Moving it down to 97.5 would tighten
an alarm on a funnel model nobody has re-estimated, which is D-3's failure
repeated exactly: an alarm that fires from week one, never clears, and teaches
the team to ignore alarms. When a threshold has to move on an unconfirmed
assumption, loose is the safe direction. Both figures remain editable in
Settings.

The test that asserted "the budget's arithmetic meets it" now asserts the gap
instead, with the numbers written out, so the next person to touch the default
finds the discrepancy and this entry rather than a stale claim.

### D-28 — 1,125 JOD of the freed 2,520 stays on the external track (2026-08-29)

**The owner's answer to D-24, D-26 and D-27, which turned out to be one
question rather than three.** D-24 asked where the freed money goes, D-26 asked
what to do about a cost-per-lead target that no longer matched its budget, and
D-27 flagged a funnel model sized for a track that had just lost a third of its
money. All three resolve the moment you answer: *does the external track still
have to deliver three units?* The owner's answer is yes.

The arithmetic, at the plan's own 45 JOD per raw external lead:

| External budget | Raw leads | Qualified | Contracts | Share of 11 |
| --- | --- | --- | --- | --- |
| 7,200 — as originally designed | 160 | 48 | 3 | 27.3% ✅ |
| **5,805 — this decision** | **129** | **39** | **3** | **27.3% ✅** |
| 4,680 — expatriate rows alone | 104 | 31 | 2 | 18.2% ❌ |

So the shortfall was never the whole 2,520. **1,125 JOD** is the least that had
to stay for the three-unit target and the ≥27% floor to remain fundable, and
that is what stays. The other 1,395 falls to the local track, which goes from
10,800 to **12,195**. `totalPaidMedia` is untouched at the approved 18,000.

**Why not simply leave it at 4,680.** `FunnelTargets.stateOf(2, 3)` is a ratio
of 0.67, below the 0.70 floor — so the dashboard would have shown the external
track **AT_RISK from its first month and never cleared**, while the track was
performing exactly to the budget it had been given. That is D-3's failure
repeated precisely: an alarm nobody can satisfy, which teaches a team to ignore
alarms. The alternative to funding the target was lowering it, and lowering it
is a bigger decision than moving 1,125 JOD.

**The five rows are rescaled, not redistributed.** Each market's annual figure
is its old share of the track applied to 5,805 and rounded to the nearest 5
JOD. No market's share moves by more than **0.03 of a percentage point**, and a
test asserts that rather than the individual figures — the split follows the
geographic distribution of remittances, and a rounding that quietly moved money
from Kuwait to the Emirates would be a strategy change wearing the costume of
arithmetic.

| | UAE | USA | KSA | QAT | KWT | Total |
| --- | --- | --- | --- | --- | --- | --- |
| was | 1,370 | 1,250 | 1,120 | 600 | 340 | 4,680 |
| now | 1,700 | 1,550 | 1,390 | 745 | 420 | **5,805** |

**`FunnelModel.EXTERNAL.rawLeads` moves from 160 to 129, and nothing else in it
moves.** The qualification, viewing and contract rates are the strategy's own
and are not re-derived for an expatriate-only audience — that would be
invention. Only the lead volume follows the budget, by division. A test pins
129 as a floor rather than a preference: at 128 raw leads the third contract
disappears, because three HALF_UP roundings sit between leads and contracts and
it does not fade out gradually.

**D-26 needed no decision in the end.** 5,805 over 39 qualified leads is
**148.846**, within 1% of the 150 that was already there. Worth not leaning on:
the two agree because both descend from the same 45-JOD assumption, not because
anything reconciles them.

**The one number here that is a floor, not an estimate.** 45 JOD per raw lead
was *blended* across expatriate and non-Jordanian markets. A lead from the
United States or the Emirates plausibly costs more than one from Iraq or
Palestine, so removing the cheaper half may push the true expatriate figure
above 45 — and if it is really 55, then 129 leads cost 7,095 and very nearly
the whole 2,520 has to come back. Nothing here assumes that away.
`ChannelSpend.costPerRawLead` already measures it, and the first month of real
spend settles it.

**Room 2 → 3, for a change that alters no schema.** Same tables, same columns;
Room would not have asked for a version bump. It exists because the *data* is
wrong on any database already created, for exactly the reason `MIGRATION_1_2`
had to delete rather than trust the seed: every insert is `IGNORE` (D-19), so
the five markets would keep their old annual figures for ever. It overwrites
unconditionally, which is **only acceptable while no screen can edit a market
budget** — that arrives at Milestone 5, and the next migration of this kind
must preserve edited rows instead. Both migration tests were proved to fail
with `MIGRATION_2_3` unwired and to pass with it restored.

### D-27 — The targets and the funnel model are left exactly as they were, and one of them is now doing more work

**Superseded by D-28 (2026-08-29), which is what this entry asked for.** The
targets it lists are unchanged and still stand; what changed is that the
external track is now funded to reach them. `FunnelModel.EXTERNAL.rawLeads` is
129 rather than the 160 recorded below. The entry is left as written because it
is the record of the question, and of the fact that the answer was to fund the
plan rather than to quietly re-cut the numbers.

Not a change — a statement of what was deliberately **not** changed, because the
arithmetic underneath it moved.

The 11-unit annual target, the 3-unit external-track target and the ≥27%
external share are unchanged. None was ever non-Jordanian-specific, and the
expatriate track carries them now.

`FunnelModel.EXTERNAL` is unchanged too: 160 raw leads → 48 qualified → 17
viewings → 3 contracts. **But those 160 were modelled for the whole external
track, when that meant expatriates and non-Jordanians together.** Expatriate
marketing alone now has to supply all 160 — on 4,680 JOD rather than 7,200.
Whether it can has not been re-estimated, and the numbers were left alone rather
than adjusted by guesswork, because a funnel model invented to make a
spreadsheet balance is worse than one that is visibly out of date. Flagged to
the owner; the model is a single object with five numbers in it and changing it
costs nothing once someone has decided what it should say.

---

## 3. Milestone 0.5 — the discovery interview

Batch A was put to the owner on 2026-08-10 with its recommended defaults. The
owner replied "continue", which under the brief's own rule — *apply the default,
record it as an assumption, and move on; never stall the build waiting for an
answer* — means the defaults stand for all three batches.

They are assumptions, not answers. Every one is reversible, and any of them can
be corrected without rework so long as it is corrected before the milestone that
depends on it (noted in the last column).

### Batch A — who uses this and what it holds

| Ref | Decision (default applied 2026-08-10) | Reversible until |
| --- | --- | --- |
| A1 | 2–3 users, no roles, no approval flow in v1 | Milestone 4 |
| A2 | The app opens in **Arabic** on first launch | Milestone 1 |
| A3 | Individual phones; encrypted backup files exchanged by hand, no merge | Milestone 8 |
| A4 | The final agreed price and discount **are** stored, with app lock on by default | Milestone 2 |
| A5 | Three unit statuses only — Available, Reserved, Contracted | Milestone 2 |
| A6 | Annual target 11 of 14 units, 3 of them from the external track | Milestone 2 |

### Batch B — how the team works

| Ref | Decision | Reversible until |
| --- | --- | --- |
| B1 | **Saturday–Thursday, 09:00–18:00 Asia/Amman; Friday the weekend.** Not the proposed Sunday–Thursday — see D-5; the company publishes Saturday–Thursday on its own website. Editable in Settings | Milestone 4 |
| B2 | The same salesperson handles both tracks | Milestone 4 |
| B3 | Loss reasons as specified — ten, single-select, mandatory | Milestone 4 |
| B4 | Lead sources as specified | Milestone 2 |
| B5 | Modern Standard Arabic for expatriate templates; light Jordanian dialect for local buyers. (Non-Jordanian templates were the third case and are gone with the track — D-23) | Milestone 6 |
| B6 | No broker module — "broker" is a lead source and nothing more | — |

### Batch C — look, feel and delivery

| Ref | Decision | Reversible until |
| --- | --- | --- |
| C1 | Palette per §4, with a typographic gold wordmark until a logo file arrives | Milestone 9 |
| C2 | «تسويق شيرمان ٣» / "GS3 Marketing" | Milestone 10 |
| C3 | Theme follows the phone | Milestone 1 |
| C4 | Western digits by default, toggleable | Milestone 1 |
| C5 | Sideloaded APK first; the app stays Play-ready at targetSdk 36 | Milestone 10 |
| C6 | Assessed value defaults to 100% of sale price — the conservative direction — editable per unit | Milestone 7 |

### Still genuinely open

| Ref | Question | Status |
| --- | --- | --- |
| B-2 (b), (c) | Does the signed contract carry the delay penalty and the two-year/ten-year warranty? | Unconfirmed. Both stay out of client-facing text until someone reads the contract |
| D-28 | Is 45 JOD still the right cost per raw lead once the cheaper non-Jordanian markets are gone? | **Open, and the one that could undo D-28's sizing.** 45 was blended; expatriate-only may be dearer. Measured by `ChannelSpend.costPerRawLead` from the first month of real spend |
| D-25 | Should `ARAB_NON_JORDANIAN` and `NON_ARAB` be removed, or kept and pointed somewhere? | **Default applied and needs confirming.** Removed — there is no honest track left, and `EXPAT` would be a lie |

### Closed

| Ref | Question | Answer |
| --- | --- | --- |
| D-3 | Is 45 JOD the target per **raw** lead or per **qualified** lead? | **Answered 2026-08-16.** Neither — the owner removed the 45 JOD figure. One target remains: 150 JOD per qualified lead, 200 stop threshold, both editable in Settings. See D-3 above, and D-26 for what happened to the arithmetic behind the 150 |
| B-1 | Has the Department of Lands and Survey statement been obtained? | **Answered 2026-08-29: no**, and closed as a v1 blocker on the same day by removing the track it gated rather than shipping a permanently locked module. See D-23. It becomes a precondition again only if the track is ever revived |
| D-24 | Does the 2,520 JOD freed by the removed markets stay in the plan on the local track, or come out of it? | **Answered 2026-08-29.** Neither in full: 1,125 stays on the external track so it can still fund three units, 1,395 falls to local (10,800 → 12,195), and total paid media is untouched. See D-28 |
| D-26 | The 150 JOD qualified-lead target no longer matches the budget (97.5). Move it or keep it? | **Answered 2026-08-29.** Neither — sizing the external track at 5,805 brings the arithmetic back to 148.846, within 1% of the target already there, so nothing had to move. See D-28 |
| D-27 | Can expatriates alone supply the external funnel's raw leads on 4,680 JOD? | **Answered 2026-08-29: no**, and the answer was to fund the plan rather than re-cut it. 4,680 buys 104 leads and two units; the track is sized at 5,805 for 129 and three. See D-28 |
