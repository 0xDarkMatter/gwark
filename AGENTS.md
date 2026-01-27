# AGENTS.md - AI Assistant Guide for gwark

This document provides context for AI assistants working on the gwark codebase.

## Project Overview

**gwark** is a Google Workspace CLI tool built with Python/Typer for Gmail, Calendar, and Drive operations. It uses OAuth2 for authentication and supports AI-powered email summarization via Claude.

## Architecture

```
src/
├── gwark/                  # CLI application (Typer)
│   ├── main.py             # Entry point, subcommand registration
│   ├── commands/           # Command modules (email, calendar, drive, config)
│   ├── core/               # Utilities (config, output, dates, email_utils)
│   └── schemas/            # Pydantic models for configuration
│
└── gmail_mcp/              # Core library (reusable)
    ├── auth/               # OAuth2 management
    ├── gmail/              # Gmail API client
    ├── cache/              # SQLite caching
    └── config/             # Settings & constants
```

## Key Conventions

### Adding Commands

1. Create `src/gwark/commands/{name}.py`
2. Define Typer app: `app = typer.Typer()`
3. Register in `src/gwark/main.py`: `app.add_typer({name}.app, name="{name}")`

### API Calls

- Use **sync API calls** (not async batch) to avoid SSL errors
- Rate limits: 250 req/sec for Google Workspace accounts
- Default concurrent operations: 10 (can increase to 50)

### Configuration

- Project config lives in `.gwark/config.yaml`
- Profiles in `.gwark/profiles/*.yaml` filter content (work vs personal)
- OAuth credentials: `.gwark/credentials/oauth2_credentials.json`
- Tokens stored in: `.gwark/tokens/`

### Output Formats

Supported formats via `--format` flag:
- `markdown` (default) - Tables with Rich formatting
- `json` - Structured data
- `csv` - Spreadsheet-compatible

## Dependencies

| Package | Purpose |
|---------|---------|
| typer | CLI framework |
| rich | Console output |
| pyyaml | Configuration |
| pydantic | Schema validation |
| google-api-python-client | Google APIs |
| anthropic | AI summarization |

## Testing

```bash
# Quick functional test
python -m gwark --help
python -m gwark config auth test
python -m gwark email search --domain example.com --days 1 --max-results 3
```

## Common Tasks

| Task | Location |
|------|----------|
| Add email filter | `src/gwark/commands/email.py` |
| Add output format | `src/gwark/core/output.py` |
| Add config option | `src/gwark/schemas/config.py` + `.gwark/config.yaml` |
| Add profile filter | `src/gwark/schemas/config.py` + `.gwark/profiles/*.yaml` |

## Current Status

- **Working**: CLI, email search (sync API), config management
- **Needs Testing**: Calendar meetings, Drive activity
- **Planned**: MCP server, summary caching, retry logic

## Don't

- Don't use async batch operations for Gmail (causes SSL errors)
- Don't commit `.env` or `.gwark/credentials/oauth2_credentials.json`
- Don't hardcode API keys
