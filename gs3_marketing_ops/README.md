# GS3 Marketing Ops — Android app

The daily operations app for the team selling the fourteen apartments at
General Sherman 3: leads, campaigns, inventory and reminders, in Arabic and
English, working entirely offline on the phone.

It is the execution layer for the marketing strategy that the
[website](../website/) advertises. The two share the same unit schedule and the
same Arabic wording, and nothing else — no code, no build, no deployment.

## Status

**Not yet building.** The plan and the decisions are written; no application
code exists, because none can be compiled here yet.

This environment's egress policy refuses `dl.google.com`, which is the single
host serving both the Android SDK and every Google-hosted Maven artifact — the
Android Gradle Plugin, AndroidX, Compose, Room, WorkManager and Hilt included.
`maven.google.com` resolves but only redirects there, and Maven Central does not
mirror any of it. Rather than pull build plugins from an unofficial mirror into
an app that will hold client contact details, the blocked host is reported and
the build waits.

**To unblock: allow `dl.google.com` for this environment.** Nothing else in the
plan changes.

## What is here

| File | What it holds |
| --- | --- |
| [`IMPLEMENTATION_PLAN.md`](IMPLEMENTATION_PLAN.md) | Module shape, the eleven milestones, and the four risks that would otherwise produce an app that looks finished and is not |
| [`DECISIONS.md`](DECISIONS.md) | Every decision with its date: the environment finding, the pinned version matrix, the verification of the brief's own figures, and the answers to the discovery interview as they arrive |

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
