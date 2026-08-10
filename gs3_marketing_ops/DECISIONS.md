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

### D-2 — Version matrix

The brief forbids "latest stable" and requires an explicit matrix (§2.3 trap 1).
The Kotlin half is **confirmed** — it resolves and compiles here. The Android
half is still **proposed**, because verifying it means resolving it and
resolution is exactly what D-1 blocks; it will be re-recorded as confirmed with
real `./gradlew` output the moment the host is allowed.

| Component | Pin | Status |
| --- | --- | --- |
| JDK | 21.0.10 | ✅ confirmed |
| Gradle | 8.14.3 (wrapper committed) | ✅ confirmed |
| Kotlin | 2.1.21 | ✅ confirmed — compiles with `allWarningsAsErrors` |
| JUnit 5 | 5.11.4 | ✅ confirmed — permitted for the pure-Kotlin module by §2 |
| JaCoCo | 0.8.12 | ✅ confirmed |
| Android Gradle Plugin | 8.13.x | proposed. Stable 8.x line, **not** 9.x — still release-candidate per §2.3 |
| KSP | matched to the Kotlin pin | proposed. Kotlin-coupled; never chosen independently |
| compileSdk / targetSdk | 36 | proposed. §2.1 — non-negotiable |
| minSdk | 26 | proposed |
| Compose | via BOM | proposed. One BOM pin, no per-artifact versions |
| Room, Hilt, WorkManager, DataStore | pinned individually | proposed. Compilers via **KSP**; `kotlin-kapt` appears nowhere |
| SQLCipher | `net.zetetic:sqlcipher-android` | proposed. Not the deprecated `android-database-sqlcipher` |
| Robolectric + Roborazzi | pinned | proposed. JVM-only; no emulator is needed or available |

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
