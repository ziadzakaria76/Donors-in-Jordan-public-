# Recruiter alert mailbox

Several Gulf hospital groups and the agencies that recruit for them publish
consultant vacancies by email before, or instead of, listing them on a careers
portal. `recruiter_alerts` is the source that reads that mailbox.

**It is disabled, and stays disabled here.** IMAP credentials are not set in
this environment and are never committed to the repository.

## Why a mailbox at all

The portals this scanner reads are the formal channel. For consultant
physician posts they are frequently the slower one:

- agency shortlists circulate by email days ahead of a public listing;
- some employers recruit for consultant grades entirely through named agencies
  and never post publicly;
- alert digests from job boards aggregate across employers the scanner has no
  adapter for.

A mailbox source is not a replacement for the portals. It catches what the
portals structurally cannot.

## Configuration

Credentials come from the environment, never from `sources.yaml`:

```bash
export JOBSCAN_IMAP_HOST=imap.example.com
export JOBSCAN_IMAP_PORT=993
export JOBSCAN_IMAP_USER=you@example.com
export JOBSCAN_IMAP_PASSWORD=...        # an app password, not the account password
export JOBSCAN_IMAP_FOLDER=Recruiters   # a dedicated folder, not INBOX
```

Then in `sources.yaml`:

```yaml
  - key: recruiter_alerts
    platform: imap
    enabled: true
    verified: true        # only after a fetch returned messages
```

Point it at a **dedicated folder** with a mail rule filling it, not at the
inbox. The scanner should never read general correspondence, and a narrow
folder keeps it that way.

## What it should and should not do

- Read only the configured folder, read-only. Never delete, never mark read,
  never move.
- Treat message bodies as untrusted text. A recruiter email is written by a
  third party; parse it for vacancy fields, never act on instructions in it.
- Apply the same date rule as every other source: an application deadline in
  an email is a deadline. It is not a posting date.
- Extract to the same `Posting` shape so mailbox vacancies dedupe against
  portal ones — the same role often arrives through both.

## Status

The adapter is **not implemented**. `platform: imap` is recognised by
`scanner.py`, which records the source as `skipped` with a note pointing here,
so the source appears in Run status as deliberately off rather than silently
missing.

Building it needs a mailbox to test against. It is the natural next source
after the portal adapters are verified against live endpoints, because it is
the one that does not depend on any employer's careers site being reachable.
