# Setup Guide

Complete guide to installing and configuring gwark.

## Prerequisites

- Python 3.10 or higher
- Google account (personal or Workspace)
- Google Cloud Platform account (free tier is sufficient)

## Installation

### 1. Clone and Install

```bash
git clone https://github.com/yourusername/gwark.git
cd gwark

# Install with uv (recommended — 10-100x faster)
uv pip install -e .

# Or with standard pip
pip install -e .
```

### 2. Google Cloud Setup

See [OAUTH_SETUP.md](OAUTH_SETUP.md) for detailed Google Cloud Console configuration.

Quick steps:

1. Create a Google Cloud project
2. Enable APIs: Gmail, Calendar, Drive, Docs, Sheets, Slides, Forms
3. Create OAuth2 credentials (Desktop App type)
4. Download credentials JSON
5. Save as `.gwark/credentials/oauth2_credentials.json`

### 3. Initialize Configuration

```bash
# Create .gwark/ directory with default config and profiles
gwark config init
```

This creates:

```
.gwark/
├── config.yaml          # Main settings
├── credentials/         # Place OAuth2 credentials here
│   └── oauth2_credentials.json
├── tokens/              # OAuth tokens (auto-created on first auth)
└── profiles/
    ├── default.yaml     # Default profile (no filters)
    └── work.yaml        # Work-only filters
```

### 4. Authenticate

```bash
# Set up OAuth (opens browser for Google sign-in)
gwark config auth setup
```

This authenticates the Gmail API. Other services (Calendar, Drive, Sheets, etc.) authenticate on first use — gwark will open a browser prompt automatically.

### 5. Test Connection

```bash
# Verify authentication works
gwark config auth test

# Quick functional test
gwark email search --domain gmail.com --days 1 --max-results 3
```

## Configuration

### Main Config

Edit `.gwark/config.yaml`:

```yaml
defaults:
  days_back: 30
  max_results: 500
  output_directory: reports
  output_format: markdown
```

### Profiles

Profiles filter content for different contexts (work vs personal):

```yaml
# .gwark/profiles/work.yaml
filters:
  email:
    exclude_senders:
      - no-reply@
      - notifications@
    exclude_subjects:
      - "Out of Office"
  calendar:
    work_only: true
    exclude_keywords:
      - personal
      - dentist
```

Use with any command: `gwark email search --domain company.com --profile work`

### Environment Variables

Optional `.env` file for AI features:

```env
# AI Summarization (optional — requires Anthropic API key)
ANTHROPIC_API_KEY=sk-ant-...

# Logging
LOG_LEVEL=INFO
```

## API Rate Limits

gwark is optimized for Google Workspace accounts:

| Limit | Value |
|-------|-------|
| Per-user quota | 15,000 queries/min (250/sec) |
| Default concurrent ops | 10 |
| Configurable max | 50 concurrent |

## Directory Structure

After setup, your project looks like:

```
gwark/
├── src/
│   ├── gwark/              # CLI tool
│   │   ├── commands/       # Command modules
│   │   ├── core/           # Utilities
│   │   └── schemas/        # Config models
│   └── gmail_mcp/          # Core library (OAuth, API clients)
├── .gwark/                 # Runtime config (gitignored)
│   ├── config.yaml
│   ├── credentials/
│   ├── tokens/
│   └── profiles/
├── config/                 # Config templates
└── reports/                # Generated output
```

## Troubleshooting

### "No OAuth2 credentials file found"

- Run `gwark config init` to create the directory structure
- Download credentials from Google Cloud Console
- Save as `.gwark/credentials/oauth2_credentials.json`

### "Token has been revoked or expired"

```bash
gwark config auth remove gmail
gwark config auth setup
```

### "insufficient_scope" Error

gwark auto-detects missing scopes and re-authenticates. If it persists:

```bash
# Remove the specific service token and retry
gwark config auth remove people
gwark email senders --name "test" --enrich
```

### "API has not been used in project"

Enable the required API in Google Cloud Console:
- Go to APIs & Services > Library
- Search for the API mentioned in the error
- Click Enable

### Rate Limit Errors (429)

gwark has built-in exponential backoff retry. If you hit limits frequently, reduce concurrency in `.gwark/config.yaml`.

## Next Steps

- [QUICKSTART.md](QUICKSTART.md) — Get running in 5 minutes
- [OAUTH_SETUP.md](OAUTH_SETUP.md) — Detailed Google Cloud setup
- [TRIAGE_WORKFLOW.md](TRIAGE_WORKFLOW.md) — AI-powered email triage
