# GS3 Marketing Ops — Android app

The daily operations app for the team selling the fourteen apartments at
General Sherman 3: leads, campaigns, inventory and reminders, in Arabic and
English, working entirely offline on the phone.

It is the execution layer for the marketing strategy that the
[website](../website/) advertises. The two share the same unit schedule and the
same Arabic wording, and nothing else — no code, no build, no deployment.

## Status

**The business rules are built, tested and green. The Android app is blocked on
one network host.**

```
./gradlew check      ->  BUILD SUCCESSFUL
                         209 tests passing, 98.6% line coverage (gate: 80%)
                         verifyStrings: 88 keys, both locales in step
```

`:domain` is pure Kotlin with no Android dependency, so it builds here today.
Under test: the unit schedule and its totals · price per m² · the discount
guard and the incentive ladder · price escalation · both funnel models and the
four diagnostic rules · budget allocation, seasonal normalisation, cost per lead
and the stop rules · the SLA engine with its time zones · fee and instalment
calculators · the campaign code and UTM builder · the lead pipeline with its
mandatory loss reasons · the WhatsApp link builder · CSV export · the dashboard
"today" list · the non-Jordanian journey and its eligibility gate · content
pillar balance · and the weekly and monthly reports.

`:app` cannot be built yet. This environment's egress policy refuses
`dl.google.com`, the single host serving both the Android SDK and every
Google-hosted Maven artifact — the Android Gradle Plugin, AndroidX, Compose,
Room, WorkManager and Hilt included. `maven.google.com` resolves but only
redirects there, and Maven Central mirrors none of it. Rather than pull build
plugins from an unofficial mirror into an app that will hold client contact
details, the blocked host is reported and that half waits.

**To unblock: allow `dl.google.com` for this environment.** Nothing else in the
plan changes, and nothing built so far is wasted — the Android milestones wire
screens to a core that is already proven.

## Layout

| Path | What it holds |
| --- | --- |
| `domain/` | Pure-Kotlin business rules and their tests. No Android, no emulator, runs on the JVM |
| `app/src/main/res/` | The two string files. Arabic is authored; English is derived from it for anything client-facing |
| `config/` | The allowlist for `verifyStrings` |
| [`IMPLEMENTATION_PLAN.md`](IMPLEMENTATION_PLAN.md) | Module shape, the eleven milestones, and the four risks that would otherwise produce an app that looks finished and is not |
| [`DECISIONS.md`](DECISIONS.md) | Every decision with its date: the environment finding, the version matrix, the verification of the brief's figures, and the discovery-interview answers |

## Running it

```bash
cd gs3_marketing_ops
./gradlew check        # tests, coverage gate, and the bilingual guard
./gradlew coverage     # prints the actual coverage percentage
./gradlew verifyStrings
```

`verifyStrings` fails the build on three things, and each was proved to fail
before being relied on: a user-visible string hardcoded in a Composable, a key
present in one locale and missing from the other, and a forbidden phrase —
«إعفاء من الرسوم» / "fee exemption", "guaranteed approval", "guaranteed return".
The company contributes toward registration fees; it cannot exempt anyone from
them, and the build will not let the app say otherwise.

## Verified before writing any code

The brief's seed data was checked against `website/assets/js/data.js`, which the
live site is built from. Both agree on every unit's areas and price, and the
totals hold: 14 units, 2,320 m² internal, 620 m² external, 1,496,000 JOD gross,
644.83 JOD/m² weighted average. Both funnel models and every budget row sum
exactly as the brief states.

One figure does not hold, and it is in `DECISIONS.md` as D-3: the 45 JOD
external-track target is *exactly* 7,200 ÷ 160 raw leads, so it is a cost per
raw lead, not the cost per qualified lead the brief calls it. Taken literally it
would hold the track to a target 3.3× harder than its own budget allows, and
leave the stop-rule alarm on permanently. Awaiting the owner's confirmation.
