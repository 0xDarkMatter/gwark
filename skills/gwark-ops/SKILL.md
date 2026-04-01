---
name: gwark-ops
description: "Google Workspace CLI setup, authentication, configuration, and module routing. Use for: initial setup, OAuth, config, profiles, calendar, or when unsure which gwark module to use. Triggers: gwark, google workspace cli, gwark config, gwark auth, gwark setup, gwark calendar, calendar meetings."
version: 1.0.0
category: productivity
requires:
  bins: ["gwark"]
allowed-tools: "Read Bash Grep Glob"
---

# gwark Operations

Google Workspace CLI. This skill covers setup, auth, config, calendar, and routes to module-specific skills.

## Setup

```bash
gwark config init                                # Create .gwark/ config directory
gwark config auth setup                          # OAuth2 (opens browser)
gwark config auth test                           # Verify Gmail connection
gwark config auth test --all                     # Preflight check ALL APIs
```

**First-time setup:** `init` then `auth setup`. Other APIs authenticate on first use.

## Module Skills

For detailed usage, load the specific skill:

| Module | Skill | When to Use |
|--------|-------|-------------|
| **Email** | `gwark-email` | Search emails, find senders, sent analysis, AI summaries |
| **Docs** | `gwark-docs` | Create/edit docs, themes, sections, AI review |
| **Drive** | `gwark-drive` | List, search, move, copy, share files |
| **Sheets** | `gwark-sheets` | Read/write data, pivot tables, export |
| **Slides** | `gwark-slides` | Create/edit presentations from markdown |
| **Forms** | `gwark-forms` | Create surveys, add questions, export responses |
| **Triage** | `gwark-triage` | Email triage and priority classification |

## Calendar

Calendar is simple enough to cover here (2 commands):

```bash
# List all calendars (get IDs for multi-calendar queries)
gwark calendar list

# Meetings from last 30 days
gwark calendar meetings --days 30

# Multi-calendar, work only, interactive
gwark calendar meetings -C "primary,work@group.calendar.google.com" --work-only -i

# Export as JSON
gwark calendar meetings --days 60 --format json -o meetings.json
```

### Calendar Options

| Option | Purpose |
|--------|---------|
| `-n/--days` | Days to look back (default: 30) |
| `-C/--calendars` | Comma-separated calendar IDs |
| `-w/--work-only` | Exclude personal events |
| `-i/--interactive` | Terminal viewer |
| `-f/--format` | json, csv, markdown |
| `-p/--profile` | Named filter profile |

## Profiles

Filter content for different contexts:

```bash
gwark config profile list                        # Show profiles
gwark config profile create -n work              # Create profile
```

Edit `.gwark/profiles/work.yaml`:
```yaml
filters:
  email:
    exclude_senders: ["no-reply@", "notifications@"]
    exclude_domains: ["newsletter.com"]
    exclude_labels: ["CATEGORY_PROMOTIONS"]
  calendar:
    work_only: true
    exclude_keywords: ["personal", "dentist"]
```

Use with any command: `gwark email search --profile work`

## Shared Patterns

### Output Formats

All commands support `--format` and `--output`:

```bash
gwark <module> <command> --format json -o output.json
gwark <module> <command> --format csv -o output.csv
gwark <module> <command> --format markdown          # Default
```

### Interactive Mode

Add `-i` to browse results:

```bash
gwark email search -d example.com -i
gwark calendar meetings --days 60 -i
gwark sheets read SHEET_ID -i
gwark slides get PRES_ID -i
```

### URL Handling

All commands accept Google document IDs or full URLs:

```bash
gwark docs get "https://docs.google.com/document/d/1abc.../edit"
gwark sheets read "https://docs.google.com/spreadsheets/d/1xyz..."
```

### Exit Codes

| Code | Meaning |
|------|---------|
| 0 | Success |
| 1 | General error |
| 2 | Auth required |
| 3 | Not found |
| 4 | Validation error |

## Gotchas

- **Rate limits:** 250 req/sec for Google Workspace. gwark has built-in retry with exponential backoff.
- **Sync API only.** Async batch operations cause SSL errors. gwark uses thread-local services.
- **Token storage:** OS keyring (primary), legacy pickle files (auto-migrated).
- **Scope detection:** gwark auto-detects mismatched token scopes and re-authenticates.
- **People API** (for `--enrich`) requires separate OAuth. First use opens browser.
