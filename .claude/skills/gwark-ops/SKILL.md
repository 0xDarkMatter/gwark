---
name: gwark-ops
description: Google Workspace CLI operations with gwark. Use when working with Gmail, Google Calendar, Google Drive, Google Docs, or Google Forms via command line. Triggers on email search, calendar meetings, drive activity, document creation/editing, form responses, or any Google Workspace API task.
---

# gwark Operations

gwark is a Google Workspace CLI for Gmail, Calendar, Drive, Docs, and Forms. All output goes to `./reports/` by default.

## Quick Reference

```bash
# Email
gwark email search --domain example.com --days 30
gwark email search --sender user@example.com --subject "invoice"
gwark email sent --year 2024 --month 12

# Calendar
gwark calendar list                    # Show all calendars
gwark calendar meetings --days 30 -i   # Interactive viewer

# Drive
gwark drive activity --year 2024 --month 12

# Docs
gwark docs create "Title" --file content.md --theme evolution7
gwark docs get DOC_ID --format markdown
gwark docs edit DOC_ID --append "## New Section"
gwark docs sections DOC_ID              # Show structure
gwark docs theme --list                 # Available themes

# Forms
gwark forms list
gwark forms get FORM_ID
gwark forms responses FORM_ID --format csv
gwark forms create "Survey" --description "Feedback form"

# Config
gwark config init                       # Create .gwark/ directory
gwark config auth setup                 # OAuth2 authentication
gwark config auth test                  # Verify connection
```

## Command Groups

### Email (`gwark email`)

| Command | Purpose | Key Options |
|---------|---------|-------------|
| `search` | Search emails | `--domain`, `--sender`, `--recipient`, `--subject`, `--query`, `--days` |
| `sent` | Sent emails for month | `--year`, `--month`, `--estimate-time` |
| `summarize` | AI summarize JSON file | `--batch-size` (requires API key) |
| `session-summarize` | Summarize via Claude session | No API key needed |

**Search examples:**
```bash
# Domain-based search
gwark email search --domain australianballet.com.au --days 120

# Combined filters
gwark email search --sender john@company.com --subject "Q4 Report" --days 60

# Raw Gmail query
gwark email search --query "is:unread has:attachment" --days 7

# Interactive viewer with full email bodies
gwark email search --domain client.com --days 30 --interactive
```

### Calendar (`gwark calendar`)

| Command | Purpose | Key Options |
|---------|---------|-------------|
| `list` | List all calendars | - |
| `meetings` | Extract meetings | `--days`, `--calendars`, `--work-only`, `--interactive` |

**Multi-calendar example:**
```bash
# List calendars first to get IDs
gwark calendar list

# Fetch from multiple calendars
gwark calendar meetings --calendars "primary,work@group.calendar.google.com" --days 30

# Work meetings only (excludes personal keywords)
gwark calendar meetings --work-only --days 60
```

### Drive (`gwark drive`)

| Command | Purpose | Key Options |
|---------|---------|-------------|
| `activity` | Monthly file activity | `--year`, `--month`, `--owned-only`, `--include-shared` |

```bash
gwark drive activity --year 2024 --month 12 --owned-only
```

### Docs (`gwark docs`)

| Command | Purpose | Key Options |
|---------|---------|-------------|
| `create` | Create from markdown | `--file`, `--template`, `--theme`, `--folder`, `--open` |
| `get` | Export document | `--format` (markdown, json, text) |
| `edit` | Modify document | `--append`, `--prepend`, `--replace`, `--insert-after`, `--move-section`, `--delete-section` |
| `sections` | Show structure | `--format` (table, tree, json) |
| `theme` | Manage themes | `--list`, `--show`, `--apply` |
| `comment` | Manage comments | `--list`, `--text`, `--reply`, `--resolve` |
| `list` | List all docs | `--query`, `--folder`, `--owned-only` |
| `review` | Process editorial comments | `--filter`, `--dry-run` |
| `apply` | Apply approved suggestions | `--dry-run` |

**Section-aware editing:**
```bash
# View document structure first
gwark docs sections DOC_ID

# Insert after a specific section
gwark docs edit DOC_ID --insert-after "Introduction" --file new_content.md

# Move a section
gwark docs edit DOC_ID --move-section "Conclusion" --before "References"

# Delete a section (with confirmation)
gwark docs edit DOC_ID --delete-section "Draft Notes" --confirm

# Preview changes without applying
gwark docs edit DOC_ID --append "## New Section" --dry-run
```

**Theme application:**
```bash
# List available themes
gwark docs theme --list

# Show theme details
gwark docs theme --show professional

# Apply theme to document
gwark docs theme --apply evolution7 --doc DOC_ID
```

### Forms (`gwark forms`)

| Command | Purpose | Key Options |
|---------|---------|-------------|
| `list` | List all forms | `--owned-only` |
| `get` | Get form structure | - |
| `responses` | Get responses | `--format` (json, csv, markdown) |
| `create` | Create new form | `--description`, `--quiz` |
| `add-question` | Add question | `--type`, `--choices`, `--required` |

**Question types:** text, paragraph, choice, checkbox, dropdown, scale, date, time

```bash
# Create form with quiz mode
gwark forms create "Q4 Survey" --description "Quarterly feedback" --quiz

# Add multiple choice question
gwark forms add-question FORM_ID --title "How satisfied are you?" \
  --type choice --choices "Very,Somewhat,Not at all" --required
```

### Config (`gwark config`)

| Command | Purpose |
|---------|---------|
| `init` | Initialize .gwark/ directory |
| `show` | Display current config |
| `auth setup` | Configure OAuth2 |
| `auth test` | Verify connection |
| `auth list` | List accounts |
| `profile list` | List profiles |
| `profile create` | Create new profile |

## Themes System

Themes are YAML files in `.gwark/themes/`. See [references/themes.md](references/themes.md) for complete theme specification.

**Theme location:** `.gwark/themes/<name>.yaml`

**Quick theme example:**
```yaml
name: company-brand
description: Company brand theme

styles:
  TITLE:
    font_family: Roboto
    font_size: 32
    bold: true
    color: "#002d3c"
    space_after: 24

  HEADING_1:
    font_family: Roboto
    font_size: 24
    bold: false
    color: "#60b2d3"
    space_before: 28
    space_after: 14

  NORMAL_TEXT:
    font_family: Roboto
    font_size: 11
    color: "#333333"
    line_spacing: 1.15
```

## Output Formats

All commands support `--format` and `--output`:

| Format | Extension | Use Case |
|--------|-----------|----------|
| `markdown` | `.md` | Human-readable reports |
| `json` | `.json` | Programmatic processing |
| `csv` | `.csv` | Spreadsheet import |
| `text` | `.txt` | Plain text |

```bash
# Save to specific location
gwark email search --domain client.com --format json --output ./exports/emails.json
```

## Common Workflows

### Email Triage with Summaries
```bash
# 1. Search and export to JSON
gwark email search --domain important-client.com --days 30 --format json

# 2. Use session-summarize (no API key needed)
gwark email session-summarize reports/email_search_*.json
# Claude Code processes the emails and generates summaries
```

### Document Creation Pipeline
```bash
# 1. Create document from markdown
gwark docs create "Q4 Report" --file report.md --theme professional --open

# 2. Check structure
gwark docs sections DOC_ID

# 3. Edit sections
gwark docs edit DOC_ID --insert-after "Summary" --file additional_content.md
```

### Editorial Review Workflow
```bash
# 1. Create anchored comments in Google Docs UI with instructions
# 2. Run review to generate AI suggestions
gwark docs review DOC_ID

# 3. In Google Docs, reply "accept" to suggestions you want
# 4. Apply approved changes
gwark docs apply DOC_ID
```

## Configuration

### .gwark/config.yaml
```yaml
version: "1.0"
defaults:
  days_back: 30
  max_results: 500
  output_format: markdown
  output_directory: ./reports

calendar:
  calendars:
    - primary
    - work@group.calendar.google.com

auth:
  credentials_path: .gwark/credentials/oauth2_credentials.json
  tokens_path: .gwark/tokens
```

### Profiles

Create profiles in `.gwark/profiles/` for different use cases:

```yaml
# .gwark/profiles/work.yaml
name: work
description: Work email filtering
filters:
  email:
    exclude_domains:
      - newsletter.com
      - notifications.linkedin.com
    exclude_labels:
      - CATEGORY_PROMOTIONS
  calendar:
    work_only: true
    exclude_keywords:
      - Personal
      - Dentist
```

Use with: `gwark email search --profile work --days 30`

## URL Handling

All commands accept either document IDs or full URLs:
```bash
# These are equivalent
gwark docs get 1mVBEx0Rmj7kYXBr6CIUKDS_x0__686Z4xuLhqfLRABY
gwark docs get "https://docs.google.com/document/d/1mVBEx0Rmj7kYXBr6CIUKDS_x0__686Z4xuLhqfLRABY/edit"
```

## Exit Codes

| Code | Meaning |
|------|---------|
| 0 | Success |
| 1 | General error |
| 2 | Auth required |
| 3 | Not found |
| 4 | Validation error |
