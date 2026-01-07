# gwark - Claude Code Development Guide

Google Workspace CLI tool for Gmail, Calendar, and Drive operations.

## Project Overview

**gwark** is a unified CLI built with Typer for interacting with Google Workspace APIs. It provides email search, calendar analysis, and drive activity tracking with YAML-based configuration and profile support.

## Quick Reference

```bash
# Test CLI
python -m gwark --help
python -m gwark config auth test
python -m gwark email search --domain example.com --days 7 --max-results 5

# Run specific command
gwark email search --domain company.com --format markdown
gwark calendar meetings --work-only
gwark config show
```

## Project Structure

```
gwark/
├── src/
│   ├── gwark/                  # CLI tool (Typer-based)
│   │   ├── commands/           # Command modules
│   │   │   ├── email.py        # email search/sent/summarize
│   │   │   ├── calendar.py     # calendar meetings
│   │   │   ├── drive.py        # drive activity
│   │   │   └── config.py       # config init/show/auth/profile
│   │   ├── core/               # Utilities
│   │   │   ├── config.py       # YAML config loading
│   │   │   ├── output.py       # Formatters (md/json/csv)
│   │   │   ├── dates.py        # Date parsing
│   │   │   └── email_utils.py  # Email extraction
│   │   ├── schemas/            # Pydantic models
│   │   │   └── config.py       # GwarkConfig, ProfileConfig
│   │   └── main.py             # Typer app entry point
│   │
│   └── gmail_mcp/              # Core library
│       ├── auth/               # OAuth2 management
│       ├── gmail/              # Gmail API client
│       ├── cache/              # SQLite caching
│       └── config/             # Settings & constants
│
├── .gwark/                     # Project configuration
│   ├── config.yaml             # Main settings
│   └── profiles/               # Filter profiles
│       ├── default.yaml
│       └── work.yaml
│
├── config/                     # OAuth credentials
├── data/tokens/                # Encrypted OAuth tokens
├── reports/                    # Generated output files
└── scripts/                    # Standalone utilities
```

## Key Files

| File | Purpose |
|------|---------|
| `src/gwark/main.py` | Typer app with subcommand registration |
| `src/gwark/commands/email.py` | Email search using sync Gmail API |
| `src/gwark/core/config.py` | YAML config loading with Pydantic |
| `.gwark/config.yaml` | Main configuration (rate limits, AI, auth) |
| `.gwark/profiles/work.yaml` | Work profile with personal item filters |

## Configuration

### .gwark/config.yaml

```yaml
version: "1.0"
defaults:
  days_back: 30
  max_results: 500
  output_format: markdown

auth:
  credentials_path: config/oauth2_credentials.json
  tokens_path: data/tokens

ai:
  model: claude-3-haiku-20240307
  batch_size: 10

gmail:
  rate_limit_per_second: 250
  max_concurrent: 10  # Increase to 50 for stable networks

active_profile: default
```

### Profiles

Profiles filter content (work vs personal):

```yaml
# .gwark/profiles/work.yaml
filters:
  email:
    exclude_senders: [no-reply@, notifications@]
    exclude_subjects: ["Out of Office"]
  calendar:
    work_only: true
    exclude_keywords: [personal, family, dentist]
```

## Development Notes

### Email Search Implementation

The email search uses **sync API calls** (not async batch) for reliability:

```python
# src/gwark/commands/email.py:137-162
service = get_gmail_service()
for msg_id in message_ids:
    email_data = service.users().messages().get(
        userId="me", id=msg_id, format=api_format
    ).execute()
```

This avoids SSL errors that occurred with concurrent batch operations.

### Rate Limits

Optimized for Google Workspace:
- 250 requests/second per user
- 10 concurrent (conservative default, can increase to 50)
- 1.2M queries/minute project-wide

### Dependencies

- **typer[all]** - CLI framework
- **rich** - Console output
- **pyyaml** - Configuration
- **pydantic** - Schema validation
- **google-api-python-client** - Google APIs
- **anthropic** - AI summarization (optional)

## Common Tasks

### Adding a New Command

1. Create `src/gwark/commands/newcmd.py`
2. Define Typer app: `app = typer.Typer()`
3. Register in `src/gwark/main.py`: `app.add_typer(newcmd.app, name="newcmd")`

### Adding Profile Filters

Edit `src/gwark/schemas/config.py` to add new filter types, then update profile YAML files.

### Testing

```bash
# Quick test
python -m gwark email search --domain test.com --days 1 --max-results 3

# Full test with AI
python -m gwark email search --domain test.com --summarize --max-results 5
```

## Environment

```env
ANTHROPIC_API_KEY=sk-ant-...  # For AI summarization
LOG_LEVEL=INFO
```

## Git Branch

Currently on `feature/email-summarization` branch.

## Status

- CLI: Working
- Email search: Working (sync API)
- Calendar/Drive: Commands defined, need testing with real APIs
- MCP Server: Deferred to future release
