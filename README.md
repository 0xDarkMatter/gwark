# gwark

[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

**Google Workspace CLI** - A unified command-line tool for Gmail, Calendar, and Drive operations.

## Features

- **Email Search & Export** - Search emails by domain, sender, subject with markdown/JSON/CSV output
- **AI Summarization** - Generate email summaries using Claude Haiku
- **Calendar Analysis** - Extract and filter calendar meetings
- **Drive Activity** - Track file activity and changes
- **Profile System** - Filter work vs personal content with YAML profiles
- **High Performance** - Optimized for Google Workspace rate limits (250 req/sec)

## Quick Start

```bash
# Install
pip install -e .

# Initialize configuration
gwark config init

# Set up OAuth (opens browser)
gwark config auth setup

# Test connection
gwark config auth test
```

## Commands

```
gwark
├── email
│   ├── search      Search emails by domain/sender/query
│   ├── sent        Analyze sent emails for a month
│   └── summarize   AI summarize emails from JSON
├── calendar
│   └── meetings    Extract calendar meetings
├── drive
│   └── activity    Extract file activity
└── config
    ├── init        Initialize .gwark/ directory
    ├── show        Display configuration
    ├── auth        OAuth management (setup/test/list/remove)
    └── profile     Profile management (list/create/delete)
```

## Usage Examples

### Email Search

```bash
# Search emails from a domain (last 30 days)
gwark email search --domain example.com --format markdown

# With AI summarization
gwark email search --domain example.com --summarize

# Custom query with date range
gwark email search --query "has:attachment larger:5M" --days 60

# Export to CSV
gwark email search --sender john@example.com --format csv --max-results 100
```

### Calendar

```bash
# Get meetings for last 30 days
gwark calendar meetings --days 30

# Work meetings only (filters personal items)
gwark calendar meetings --work-only --profile work
```

### Drive

```bash
# File activity for a month
gwark drive activity --year 2025 --month 1
```

## Configuration

gwark uses a `.gwark/` directory for project-local configuration:

```
.gwark/
├── config.yaml          # Main settings
└── profiles/
    ├── default.yaml     # Default profile (no filters)
    └── work.yaml        # Work-only filters
```

### Profiles

Use profiles to filter content:

```bash
# Use work profile (excludes personal items)
gwark email search --domain company.com --profile work
gwark calendar meetings --profile work
```

Edit `.gwark/profiles/work.yaml` to customize filters:

```yaml
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
      - family
      - dentist
```

## Google Cloud Setup

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Create a new project or select existing
3. Enable APIs: Gmail, Calendar, Drive
4. Create OAuth2 credentials (Desktop App)
5. Download credentials JSON
6. Save as `config/oauth2_credentials.json`

See [docs/OAUTH_SETUP.md](docs/OAUTH_SETUP.md) for detailed instructions.

## Environment Variables

Create a `.env` file for additional settings:

```env
# AI Summarization (optional)
ANTHROPIC_API_KEY=sk-ant-...

# Rate limiting (Google Workspace defaults)
RATE_LIMIT_PER_SECOND=250
MAX_CONCURRENT=10

# Logging
LOG_LEVEL=INFO
```

## Architecture

```
gwark/
├── src/
│   ├── gwark/              # CLI tool
│   │   ├── commands/       # Typer command modules
│   │   ├── core/           # Utilities (config, output, dates)
│   │   └── schemas/        # Pydantic config models
│   └── gmail_mcp/          # Core library (OAuth, API clients, cache)
├── .gwark/                 # Project configuration
├── config/                 # OAuth credentials
├── data/                   # Token storage
└── reports/                # Generated reports
```

## Rate Limits

Optimized for Google Workspace business accounts:

| Limit | Value |
|-------|-------|
| Per-user quota | 15,000 queries/min (250/sec) |
| Project quota | 1,200,000 queries/min |
| Concurrent ops | 10 (configurable to 50) |

## Development

```bash
# Install with dev dependencies
pip install -e ".[dev]"

# Run tests
pytest

# Format code
black src/ tests/
ruff check src/ tests/
```

## Roadmap

- [ ] MCP Server for Claude Desktop integration
- [ ] Summary caching to avoid re-processing
- [ ] Retry logic with exponential backoff
- [ ] Multi-account support

## License

MIT License - see [LICENSE](LICENSE) for details.

---

Built with [Typer](https://typer.tiangolo.com/) and [Rich](https://rich.readthedocs.io/)
