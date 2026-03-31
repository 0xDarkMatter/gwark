# Quick Start Guide

Get gwark running in 5 minutes.

## Prerequisites

- Python 3.10+
- Google account
- Google Cloud project with OAuth2 credentials ([setup guide](OAUTH_SETUP.md))

## Install

```bash
# Clone and install
git clone https://github.com/yourusername/gwark.git
cd gwark
uv pip install -e .       # or: pip install -e .
```

## Configure

```bash
# Create config directory
gwark config init

# Place your OAuth2 credentials file at:
#   .gwark/credentials/oauth2_credentials.json

# Authenticate (opens browser)
gwark config auth setup

# Verify
gwark config auth test
```

## Try It

### Email

```bash
# Search emails from a domain
gwark email search --domain example.com --days 30

# Find unique senders by name
gwark email senders --name "smith" --days 365

# Interactive email browser
gwark email search --domain example.com -i
```

### Calendar

```bash
# Meetings from last 30 days
gwark calendar meetings --days 30

# Interactive calendar viewer
gwark calendar meetings --days 60 -i
```

### Drive

```bash
# List files in a folder
gwark drive ls "My Documents"

# Search for files
gwark drive search "quarterly report" --type docs
```

### Sheets

```bash
# List spreadsheets
gwark sheets list

# Read data with interactive grid
gwark sheets read SPREADSHEET_ID -i

# Create a pivot table
gwark sheets pivot SPREADSHEET_ID -s "Data!A:E" -r "Category" -v "sum:Sales"
```

### Docs

```bash
# Create a doc from markdown
gwark docs create "Meeting Notes" --file notes.md --open

# Pipe from Claude Code
claude "Write a project brief" | gwark docs create "Brief" -f -
```

### Slides

```bash
# Create a presentation from markdown
gwark slides create "Q1 Review" --file slides.md --open
```

### Forms

```bash
# List forms and export responses
gwark forms list
gwark forms responses FORM_ID --format csv
```

## Output Formats

All search commands support:

```bash
--format markdown   # Default — Rich tables
--format json       # Structured data
--format csv        # Spreadsheet-compatible
```

## Profiles

Filter content for different contexts:

```bash
# Use work profile (excludes personal items)
gwark email search --domain company.com --profile work
gwark calendar meetings --profile work
```

Edit `.gwark/profiles/work.yaml` to customize filters.

## AI Features

For AI-powered summarization, set your Anthropic API key:

```bash
export ANTHROPIC_API_KEY=sk-ant-...

# Summarize emails
gwark email search --domain example.com --summarize

# Summarize a document
gwark docs summarize DOC_ID
```

## What's Next

- Full command reference: see `gwark --help` and `gwark <command> --help`
- Detailed setup: [SETUP.md](SETUP.md)
- OAuth configuration: [OAUTH_SETUP.md](OAUTH_SETUP.md)
- Email triage workflow: [TRIAGE_WORKFLOW.md](TRIAGE_WORKFLOW.md)
