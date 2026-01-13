# Email Triage Workflow

Automated email triage for inbox review, audits, and post-holiday catchup.

## Overview

The triage workflow fetches emails, filters noise, detects response status, enriches with sender signals, and classifies by priority using AI.

```
FETCH → FILTER → ANALYZE → CLASSIFY → REPORT
```

## Usage

```bash
# Basic usage
gwark workflow run triage \
  --account mack@company.com \
  --since 2025-12-01

# With options
gwark workflow run triage \
  --account mack@company.com \
  --since 2025-12-01 \
  --profile work \
  --max-results 5000
```

## Stages

### Stage 1: Fetch

Fetches emails from Gmail API matching:
- `to:account` - emails sent to the specified account
- `after:date` - emails after the specified date

Handles pagination automatically up to `--max-results`.

### Stage 2: Filter

Applies profile-based rules to remove noise:

```yaml
# .gwark/profiles/work.yaml
filters:
  email:
    exclude_senders:
      - "no-reply@"
      - "noreply@"
      - "notifications@"
    exclude_subjects:
      - "Invitation:"
      - "Out of Office"
    exclude_labels:
      - "CATEGORY_PROMOTIONS"
      - "CATEGORY_SOCIAL"
```

### Stage 3: Analyze

Detects response status for each email thread:

| Status | Meaning |
|--------|---------|
| `needs_response` | They sent last, you haven't replied |
| `awaiting_reply` | You sent last, waiting on them |
| `replied` | Conversation ongoing |

### Stage 4: Classify

Only emails with `needs_response` status are classified.

#### Sender Signals

Before AI classification, emails are enriched with sender quality signals:

| Signal | Source | Meaning |
|--------|--------|---------|
| `known` | My Contacts | Explicitly added contact |
| `prior` | Other Contacts | Auto-saved from past email interactions |
| `unknown` | Neither | No prior relationship |

**Caching**: Contacts are cached locally at `~/.gwark/cache/contacts_cache.json` for 7 days to avoid repeated API calls.

#### AI Classification

Model: `claude-sonnet-4-20250514`

Each email is classified into one of five priority tiers, with summaries for actionable emails:

| Priority | Criteria | Action |
|----------|----------|--------|
| **urgent** | Deadlines, payment failures, penalties, ATO notices | Act now |
| **important** | Compliance, tax/BAS, HR issues, approvals | Act soon |
| **respond** | Genuine emails from known/prior senders | Reply when able |
| **noise** | Receipts, digests, newsletters, automated updates | Archive/ignore |
| **sales** | Cold outreach from unknown senders | Bulk delete |

**Classification Signals**:

| Signal | Values | Impact |
|--------|--------|--------|
| Sender Quality | known, prior, unknown | known/prior → respond+, unknown → sales/noise |
| Gmail Category | Primary, Updates, Promotions, Social, Forums | Updates → noise, Primary → respond+ |

**Classification Logic**:

```
sender_quality = "unknown" + pitch content → sales
sender_quality = "unknown" + automated content → noise
sender_quality = "known" or "prior" + conversational → respond
gmail_category = "Updates" → noise
gmail_category = "Primary" → more likely respond/important
deadline/payment/penalty keywords → urgent
compliance/approval/HR content → important
```

**Summaries**: For urgent, important, and respond emails, the classifier generates a 1-2 sentence summary explaining what action is needed. Noise and sales emails don't get summaries.

### Stage 5: Report

Generates a markdown report with:
- Summary counts by category
- Priority breakdown (urgent → important → informational → sales)
- Awaiting reply section
- Filtered emails (collapsed)

Output: `reports/triage_{account}_{timestamp}.md`

## OAuth Scopes Required

| Scope | Purpose |
|-------|---------|
| `gmail.readonly` | Fetch emails |
| `contacts.readonly` | My Contacts lookup |
| `contacts.other.readonly` | Other Contacts lookup |

First run will trigger OAuth consent for People API scopes.

## Configuration

### Profile Filters

Create or edit `.gwark/profiles/work.yaml`:

```yaml
name: work
filters:
  email:
    exclude_senders:
      - "no-reply@"
      - "mailer-daemon@"
      - "notifications@"
    exclude_subjects:
      - "Invitation:"
      - "Accepted:"
      - "Declined:"
    exclude_labels:
      - "CATEGORY_PROMOTIONS"
      - "CATEGORY_SOCIAL"
      - "CATEGORY_UPDATES"
      - "CATEGORY_FORUMS"
```

### Cache Location

Contacts cache: `~/.gwark/cache/contacts_cache.json`

To force refresh, delete the cache file.

## Cost Estimate

For 100 emails needing classification:
- ~10 API calls to Claude Haiku
- Cost: ~$0.01-0.02
- Time: ~10-20 seconds
