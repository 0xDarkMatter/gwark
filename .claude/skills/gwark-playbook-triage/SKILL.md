---
name: gwark-playbook-triage
description: "Email triage workflow: fetch, filter, classify, and report on inbox priority. Use when: reviewing inbox, catching up on email, email audit, priority analysis, post-holiday catchup. Triggers: email triage, inbox review, catchup, priority analysis, inbox zero, email audit."
version: 1.0.0
category: productivity
requires:
  bins: ["gwark"]
allowed-tools: "Read Bash Grep Glob"
---

# Email Triage Playbook

Classify and prioritize inbox emails. Produces a markdown report with urgent/important/respond/noise categories.

## What This Produces

A triage report at `reports/triage_*.md` with:
- Priority breakdown (urgent > important > respond > noise > sales)
- AI-generated summaries for actionable emails
- Awaiting reply section
- Filtered noise (collapsed)

## Prerequisites

- Gmail OAuth configured (`gwark config auth test`)
- Optional: `ANTHROPIC_API_KEY` for AI classification
- Optional: Work profile for noise filtering

## Quick Start

```bash
# Basic triage (last 30 days)
gwark workflow run triage --account you@company.com --since 2025-03-01

# With work profile (excludes promotions, newsletters)
gwark workflow run triage --account you@company.com --since 2025-03-01 --profile work

# Preview without AI (faster, free)
gwark workflow run triage --account you@company.com --since 2025-03-01 --skip-ai

# Export data for Claude Code classification
gwark workflow run triage --account you@company.com --since 2025-03-01 --export-data
```

## Stages

### 1. Fetch
Fetches emails matching `to:account after:date`. Handles pagination automatically.

### 2. Filter
Applies profile rules to remove noise:
```yaml
# .gwark/profiles/work.yaml
filters:
  email:
    exclude_senders: ["no-reply@", "noreply@"]
    exclude_subjects: ["Invitation:", "Out of Office"]
    exclude_labels: ["CATEGORY_PROMOTIONS", "CATEGORY_SOCIAL"]
```

### 3. Analyze
Detects response status per thread:
- `needs_response` — they sent last, you haven't replied
- `awaiting_reply` — you sent last, waiting on them
- `replied` — conversation ongoing

### 4. Classify (AI)
Emails needing response get classified:

| Priority | Criteria | Action |
|----------|----------|--------|
| **urgent** | Deadlines, payments, penalties | Act now |
| **important** | Compliance, approvals, HR | Act soon |
| **respond** | Known/prior senders, genuine emails | Reply when able |
| **noise** | Receipts, digests, automated updates | Archive |
| **sales** | Cold outreach from unknown senders | Bulk delete |

### 5. Report
Markdown report saved to `reports/triage_*.md`.

## Manual Alternative

If you prefer step-by-step control:

```bash
# 1. Search and export
gwark email search --query "to:me newer_than:7d" --format json -o inbox.json

# 2. Find unique senders
gwark email senders --query "to:me newer_than:7d" --enrich

# 3. Summarize actionable emails
gwark email summarize inbox.json --interactive

# 4. Create action report in Google Docs
gwark docs create "Inbox Triage" -f report.md --open
```

## Options

| Option | Purpose |
|--------|---------|
| `--account` | Email account to analyze |
| `--since` | Start date (YYYY-MM-DD) |
| `--profile` | Filter profile |
| `--max-results` | Max emails (default: 500) |
| `--skip-ai` | Skip AI classification |
| `--dry-run` | Preview without classification |
| `--export-data` | Export JSON for external classification |
