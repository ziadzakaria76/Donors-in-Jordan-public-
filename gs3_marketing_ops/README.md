# GS3 Marketing Ops — Android app

The daily operations app for the team selling the fourteen apartments at
General Sherman 3: leads, campaigns, inventory and reminders, in Arabic and
English, working entirely offline on the phone.

It is the execution layer for the marketing strategy that the
[website](../website/) advertises. The two share the same unit schedule and the
same Arabic wording, and nothing else — no code, no build, no deployment.

## Status

**Both halves build, and both are green.**

```
./gradlew check assembleDebug
                     ->  BUILD SUCCESSFUL
                         238 tests passing (211 in :domain, 27 in :app)
                         98.7% line coverage on :domain (gate: 80%)
                         verifyStrings: 98 keys, both locales in step
                         lint: clean, abortOnError + warningsAsErrors
```

`:domain` is pure Kotlin with no Android dependency. Under test: the unit
schedule and its totals · price per m² · the discount guard and the incentive
ladder · price escalation · both funnel models and the four diagnostic rules ·
budget allocation, seasonal normalisation, cost per lead and the stop rules ·
the SLA engine with its time zones · fee and instalment calculators · the
campaign code and UTM builder · the lead pipeline with its mandatory loss
reasons · the WhatsApp link builder · CSV export · the dashboard "today" list ·
content pillar balance · and the weekly and monthly reports.

`:app` builds a real debug APK at targetSdk 36. The `dl.google.com` egress
block that stopped the first two attempts was lifted on 2026-08-15 —
`DECISIONS.md` → D-1 keeps the record of what was true before that.

**No non-Jordanian buyer track.** It was removed from v1 on 2026-08-29 rather
than shipped behind a gate nobody could open — `DECISIONS.md` → D-23. The
external track was then re-sized to 5,805 JOD so that removing it did not cost
the plan its third external unit — D-28.

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
