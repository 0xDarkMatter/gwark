---
name: gwark-email
description: "Gmail operations with gwark: search, sender analysis, sent tracking, AI summaries. Use when: searching emails, analyzing senders, reviewing sent mail, summarizing threads. Triggers: email search, gmail, search emails, sender analysis, email summary, inbox, find emails, unique senders."
version: 1.0.0
category: productivity
requires:
  bins: ["gwark"]
allowed-tools: "Read Bash Grep Glob"
---

# gwark Email

Search Gmail, find unique senders, analyze sent mail, and summarize threads.

## Search

```bash
# By domain (from or to)
gwark email search --domain example.com --days 30

# By sender
gwark email search --sender alice@example.com --days 60

# By subject
gwark email search --subject "Q4 Report" --days 90

# Raw Gmail query (full syntax)
gwark email search --query "from:alice@example.com has:attachment larger:5M" --days 30

# Combined filters
gwark email search --domain example.com --subject "invoice" --days 120 --format json

# Interactive viewer (loads full email bodies)
gwark email search --domain example.com -i
```

### Key Options

| Option | Default | Purpose |
|--------|---------|---------|
| `-d/--domain` | | Domain (matches from: OR to:) |
| `-s/--sender` | | Exact sender address |
| `-r/--recipient` | | Recipient address |
| `--subject` | | Subject text |
| `-q/--query` | | Raw Gmail query (overrides other filters) |
| `-n/--days` | 30 | Days to look back |
| `-m/--max-results` | 500 | Max emails to fetch |
| `-f/--format` | markdown | json, csv, markdown, text |
| `--summarize` | false | AI summarization (needs ANTHROPIC_API_KEY) |
| `-i/--interactive` | false | Terminal viewer |
| `-p/--profile` | | Named filter profile |

### Search Strategy

1. **Start broad, narrow down.** Domain search first, then add sender/subject/date.
2. **Use `--query` for complex searches.** Gmail syntax supports `OR`, `NOT (-)`, `has:attachment`, `larger:`, `is:unread`, `label:`, date ranges.
3. **Profile filters stack.** `--profile work` applies exclude rules on top of search criteria.
4. **Pagination is automatic.** gwark handles `nextPageToken` — just set `--max-results`.

For full Gmail query syntax, see [references/gmail-query-syntax.md](references/gmail-query-syntax.md).

## Unique Senders

Find and deduplicate contacts from email history:

```bash
# By name (matches display name in From header)
gwark email senders --name "smith" --days 365

# By domain
gwark email senders --domain example.com --days 90

# By email prefix
gwark email senders --sender john@ --days 365

# With Google Contacts enrichment (known/prior/unknown)
gwark email senders --name "smith" --enrich

# Spelling variants via raw query
gwark email senders --query "from:nevill OR from:neville"

# Export as CSV
gwark email senders --domain example.com -f csv -o contacts.csv
```

### Output Fields

| Field | Description |
|-------|-------------|
| Name | Best display name found |
| Email | Deduplicated email address |
| Count | Total emails from this sender |
| Last Seen | Most recent email date |
| Contact | `known` (My Contacts), `prior` (Other Contacts), `unknown` (with `--enrich`) |
| Recent Subjects | Last 3 unique subjects for context |

### Senders Strategy

- **Name search is fuzzy.** `--name "smith"` matches display names AND email addresses via Gmail `from:"smith"`.
- **Default lookback is 365 days** (vs 30 for search). Sender analysis needs history.
- **`--enrich` requires People API.** First use opens browser for OAuth. Contacts are cached 7 days.
- **Max 500 emails scanned by default.** Increase with `-m 2000` for comprehensive results.

## Sent Analysis

```bash
# Sent emails for a specific month
gwark email sent --year 2025 --month 12

# With AI time estimation
gwark email sent --year 2025 --month 12 --estimate-time
```

## AI Summarization

```bash
# Search + summarize in one step
gwark email search --domain example.com --summarize

# Or from saved JSON
gwark email summarize reports/email_search_*.json --batch-size 10

# Interactive mode (no API key — uses Claude Code session)
gwark email summarize reports/emails.json --interactive
```

**Requirements:** `ANTHROPIC_API_KEY` env var for API mode. Interactive mode (`-i`) uses the active Claude Code session — no API key needed.

## Pipe Patterns

| From | To | Pattern |
|------|----|---------|
| search | summarize | `gwark email search -d example.com -f json -o emails.json && gwark email summarize emails.json` |
| search | sheets | `gwark email search -d example.com -f csv -o emails.csv && gwark sheets write SHEET_ID -f emails.csv` |
| senders | csv | `gwark email senders -d example.com -f csv -o contacts.csv` |
| search | docs | `gwark email search -d example.com -f markdown -o report.md && gwark docs create "Report" -f report.md` |

## Gotchas

- `--days 30` is the default for search. For historical analysis, always set `--days 365` or higher.
- `--max-results 500` default may miss emails. Gmail returns most recent first.
- `--summarize` requires `ANTHROPIC_API_KEY`. Use `--interactive` mode as alternative.
- Profile filters (`--profile work`) only exclude from results — they don't change the Gmail query.
- `--query` overrides all other filter options (`--domain`, `--sender`, etc.).
