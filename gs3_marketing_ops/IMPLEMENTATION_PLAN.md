# GS3 Marketing Ops — implementation plan

A native Android app for the team selling the fourteen apartments at General
Sherman 3. Offline, local-only, Arabic-first. Built from the v1.4 build brief;
this file is the plan for executing it, and [`DECISIONS.md`](DECISIONS.md) is
the record of what was decided along the way.

**Current status: Milestones 0, 0.5, 1 and 2 complete and green.** The
`dl.google.com` block that stopped the first two attempts is lifted. The SDK is
installed, `:app` is in `settings.gradle.kts`, and `./gradlew check
assembleDebug` produces a real APK at targetSdk 36 (minSdk 26, no `INTERNET`
permission) with lint and `verifyStrings` clean. The version matrix in
`DECISIONS.md` → D-2 is confirmed rather than proposed.

The bilingual foundation and the data layer are in: a live language switch, both
string files in step at 98 keys, five Room tables with an exported schema for
every version and a real migration for each step from 1 to 4, and a seed derived
from `:domain` rather than re-typed. **Milestone 7 lost half its scope** when the
non-Jordanian track was removed (D-23); Milestone 3 is the next unstarted row.

---

## Module shape

One Gradle project, `:app`, plus a pure-Kotlin `:domain` module.

`:domain` earns its place rather than being architecture for its own sake. The
business rules the brief cares about — funnel maths, budget allocation and
seasonal normalisation, fee calculation, SLA evaluation against a lead's own
time zone, price-per-m², the discount guard — are pure functions over plain
data. Kept in a module with no Android dependency, they are testable at JVM
speed with no Robolectric, which is what makes the ≥80% coverage gate on
business logic cheap to hold rather than a chore. Everything Android — Room,
Compose, WorkManager, Hilt — stays in `:app`.

Inside `:app`, packages by feature (`inventory`, `leads`, `campaigns`,
`content`, `whatsapp`, `calculators`, `reports`, `compliance`, `settings`),
each with its own `ui` / `data` split. MVVM, unidirectional flow, one activity.

There was a `nonjordanian` package. It is gone with the track (`DECISIONS.md` →
D-23); `compliance` is what is left of it, and holds the four contract claims,
which were never about non-Jordanian buyers in the first place.

## Cross-cutting work that cannot be retrofitted

Four things get built into Milestone 0's foundations, because adding any of them
later means reopening every screen:

1. **Edge-to-edge and window insets** — API 36 removes the opt-out. Every
   screen handles insets from its first commit.
2. **Adaptive layout** — no orientation locking is permitted at ≥600dp.
   `WindowSizeClass` and a list/detail two-pane scaffold exist before the first
   list is written; Leads and Inventory use it for real.
3. **RTL and bilingual strings** — `start`/`end` only, no hardcoded literal ever
   reaches a Composable, and `verifyStrings` fails the build on either mistake
   from the first milestone rather than the last.
4. **UTC storage, `ZoneId` rendering** — every timestamp, from the first entity.
   A lead in Toronto and a lead in Amman are the same code path.

## Milestones

| # | Milestone | Done when |
| --- | --- | --- |
| 0 | Environment, plan, scaffolding | Toolchain verified with real output; project builds at targetSdk 36 with edge-to-edge, adaptive scaffolding, version catalog, Hilt, Room, Navigation, theme, typography and both string files wired; `DECISIONS.md` started |
| 0.5 | **Discovery interview (hard gate)** | Three batches asked and answered or explicitly defaulted; both blocker questions asked in writing; `DECISIONS.md` updated. No UI work begins before this row closes |
| 1 | Bilingual + RTL foundation | Live language switch that persists; numeral and date toggles; `verifyStrings` and Roborazzi wired; both-language screenshots of a sample screen |
| 2 | Data layer + seed | Entities, DAOs, migrations from day one, seeded units, budgets, templates, objections; seed assertions pass |
| 3 | Inventory, unit detail, share and ad copy | Price-per-m² computed, discount guard enforced, WhatsApp share with a working fallback, ad-copy generation |
| 4 | Leads, SLA engine, notifications | Capture, qualification, pipeline, timeline, mandatory loss reasons; every SLA rule firing against the *lead's* time zone including across a DST boundary; reminder health check; no client data on a lock screen |
| 5 | Campaigns, budget, performance | Code and UTM builder that cannot drift, allocation, seasonal normalisation, spend entry, CPL, stop-rule flags |
| 6 | Content planner + WhatsApp toolkit | Calendar, pillar balance, asset checklist, nurture sequences, quick replies, objection library |
| 7 | Calculators | All calculators with their disclaimers. The non-Jordanian tracker and its blocking gate were this milestone's other half and are removed from v1 — `DECISIONS.md` → D-23 |
| 8 | Dashboard, reports, export, backup | Dashboard aggregates correct; PDF and CSV with Arabic proven, not assumed; encrypted backup and a restore tested on a clean install |
| 9 | Polish, accessibility, adaptive, dark mode | Empty states, TalkBack, 200% font scale, dark theme, landscape and tablet two-pane, predictive back, insets under both navigation modes, full screenshot set |
| 10 | Release | Signed AAB and debug APK, keystore documented for offline safekeeping, icons, `README.md`, `USER_GUIDE_AR.md`, `USER_GUIDE_EN.md`, `QA_CHECKLIST.md`, `DECISIONS.md` |

Each milestone reports actual `assembleDebug`, `test`, `lint` and
`verifyStrings` output. A milestone with a known failure is not complete, and a
failing check is fixed rather than disabled.

## The risks worth naming

Not a generic risk register — these are the four that would produce an app that
looks finished and is not.

**Reminders that never fire.** The SLA reminder *is* the product. Aggressive
battery management on the devices common in this region kills WorkManager jobs
silently, and nobody discovers it, because a reminder that does not arrive looks
exactly like a quiet week. Hence exact alarms for the time-critical first
response, and a Settings screen that proves delivery end-to-end instead of
asserting it.

**Arabic in generated files.** The screen can be perfect while the exported PDF
comes out as disconnected or reversed glyphs, and the PDF is the artefact that
gets circulated. Tested by rendering a known Arabic sentence and asserting the
rasterised width against the on-screen render, with the page saved to
`screenshots/` so it can be eyeballed. CSV gets a UTF-8 byte-order mark, because
these files are opened in Excel on Windows.

**Time zones.** Amman has been UTC+3 with no daylight saving since 2022; Toronto
and London are not. An expatriate lead's "09:00 local" moves relative to Amman
twice a year, so a stored offset would break every North America reminder each
March and November. Store UTC, render through `ZoneId`, and test across a real
DST boundary.

**Two irreversible losses.** A lost backup passphrase makes the backup
unrecoverable; a lost signing keystore makes the app permanently un-updatable.
Neither would occur to a non-technical owner, so both are stated in bold, in
both languages, at the point of use.

## Deliberately not in v1

**No non-Jordanian buyer track.** The owner removed it on 2026-08-29 after the
Department of Lands and Survey statement came back not obtained, rather than
ship a module locked behind a gate nobody could open. Nothing in v1 markets to,
processes, or promises anything to a non-Jordanian buyer. It is a rebuild, not a
switch: see `DECISIONS.md` → D-23 for exactly what came out. D-28 briefly
re-sized the external track to cover the loss; D-29 reverted that when the owner
removed the cost-per-lead assumption it rested on.

No backend, accounts or cloud sync — data lives on the device, and encrypted
backup files are how it moves between phones. No ad-platform API integration;
spend is entered by hand. No broker or commission module — "broker" is a lead
source and nothing more. No analytics SDK, no crash reporting that transmits
personal data, no advertising ID. And no field anywhere for a passport number,
national ID, bank details or a scanned identity document: a ticked checklist
item records only that a document was received, never the document.
