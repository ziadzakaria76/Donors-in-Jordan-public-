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
| B-1 | Has a written statement been obtained from the Department of Lands and Survey confirming the classification of this project's units and that non-Jordanians may own them? | **Unanswered** | — | — |
| B-2 | Does the signed contract actually contain (a) the named finishing-specifications annex, (b) a delay penalty in the buyer's favour, (c) the two-year finishing and ten-year structural warranty, and (d) the quarterly photographic progress report? | **Unanswered** | — | — |

Consequences while B-1 is unanswered — enforced by the app, not by convention:

- the non-Jordanian buyer module stays behind its blocking gate (brief §5.9);
- no campaign whose track is `NONJO` can be set to Active;
- the Dashboard carries a persistent banner.

Consequence while B-2 is unanswered: any claim in the list above is **omitted**
from WhatsApp templates, share cards and ad copy. The app must not put a promise
in front of a client that the contract does not carry. Each of the four is a
separate switch in seed data, so three can ship if only one turns out to be
absent.

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
| B5 | Modern Standard Arabic for expatriate and non-Jordanian templates; light Jordanian dialect for local buyers | Milestone 6 |
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
| D-3 | Is 45 JOD the target per **raw** lead (as the budget arithmetic implies) or per **qualified** lead (as the brief's wording says)? Implemented as 45 raw / 150 qualified / 200 stop threshold, all editable in Settings | Awaiting confirmation — no rework either way |
| B-1, B-2 | The two blocking questions in section 0 | Awaiting a written answer. Not defaultable |
