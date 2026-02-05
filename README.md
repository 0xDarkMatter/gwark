# gwark

[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Rich](https://img.shields.io/badge/Rich-Terminal%20UI-green.svg)](https://rich.readthedocs.io/)
[![Anthropic](https://img.shields.io/badge/AI-Claude%20Haiku-orange.svg)](https://anthropic.com/)

**Your inbox, calendar, and drive — tamed from the terminal.**

Ever tried to find that one email from six months ago? The one with the attachment? From someone whose name you *almost* remember? Yeah, Gmail search isn't it.

gwark is the command-line power tool Google Workspace desperately needed. Search thousands of emails in seconds with actual query syntax, not whatever algorithm Google thinks you meant. Get AI-powered summaries that cut through corporate reply-all chains. Browse your calendar without opening seventeen Chrome tabs. Export everything to formats that actually work with other tools.

Built for devs, PMs, and anyone else who's sick of clicking through UI to answer "what did I even work on last quarter?" Your terminal is faster than your browser — let's use it.

## Why gwark?

- **Blazing Fast Email Search** — Query by domain, sender, or raw Gmail syntax. Export to markdown, JSON, or CSV. Done.
- **Interactive Terminal Viewers** — Browse emails, calendar, and drive with keyboard navigation. No browser needed.
- **AI Summaries That Don't Suck** — Claude Haiku distills email threads into bullet points you'll actually read
- **Calendar Forensics** — Pull meeting history, filter out the noise, see where your time *really* went
- **Drive Activity Tracking** — What changed? When? Finally, answers.
- **Work/Life Separation** — Profile system filters out personal stuff when you need to focus (or vice versa)
- **Google Workspace Native** — Built for business accounts with 250 req/sec throughput

## Quick Start

```bash
# Install (using uv - recommended, 10-100x faster)
uv pip install -e .

# Or with standard pip
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
│   ├── search      Search emails by domain/sender/query (-i for interactive)
│   ├── sent        Analyze sent emails for a month
│   └── summarize   AI summarize emails from JSON
├── calendar
│   └── meetings    Extract calendar meetings (-i for interactive)
├── drive
│   └── activity    Extract file activity (-i for interactive)
├── forms
│   ├── list        List Google Forms (via Drive)
│   ├── get         Get form structure and questions
│   ├── responses   Export form responses
│   ├── create      Create new form
│   └── add-question Add question to existing form
├── docs
│   ├── create      Create doc from prompt, markdown, or template
│   ├── get         Export doc as markdown/JSON/text
│   ├── edit        Section-aware editing (append, insert-after, move, delete)
│   ├── sections    Analyze document structure (heading hierarchy)
│   ├── theme       List, show, or apply themes
│   ├── summarize   AI summarize document
│   ├── comment     Manage comments (list, reply, resolve)
│   ├── review      Process editorial comments with AI suggestions
│   ├── apply       Apply approved gwark suggestions to document
│   └── list        List Google Docs from Drive
├── sheets
│   ├── list        List spreadsheets (-i for interactive)
│   ├── get         Get spreadsheet metadata + worksheets
│   ├── read        Read data from range (-i for grid viewer)
│   ├── write       Write data from file/stdin
│   ├── create      Create new spreadsheet
│   ├── append      Append rows to sheet
│   ├── clear       Clear cells in range
│   └── export      Export as CSV/JSON
└── config
    ├── init        Initialize .gwark/ directory
    ├── show        Display configuration
    ├── auth        OAuth management (setup/test/list/remove)
    └── profile     Profile management (list/create/delete)
```

## Interactive Mode

Add `-i` to any search command for an interactive terminal viewer:

```bash
# Browse emails interactively
gwark email search --domain example.com -i

# Navigate calendar with split-pane view
gwark calendar meetings --days 60 -i

# Browse drive files
gwark drive activity --year 2025 --month 1 -i
```

**Keyboard shortcuts:**
| Key | Action |
|-----|--------|
| `↑↓` | Navigate list |
| `Enter` | View details / Open in browser |
| `o` | Open in Gmail/Calendar |
| `PgUp/PgDn` | Jump by week (calendar) |
| `g/G` | Go to top/bottom |
| `q` | Quit |

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

### Forms

```bash
# List all forms
gwark forms list

# Get form structure
gwark forms get FORM_ID

# Export responses as CSV
gwark forms responses FORM_ID --format csv

# Create form with questions
gwark forms create "Feedback Survey" --description "Customer feedback"
gwark forms add-question FORM_ID --title "Rating" --type scale --high 10
```

### Docs

```bash
# Create from markdown file
gwark docs create "Report" --file report.md --theme professional --open

# Pipe from stdin (great for Fabric/Claude Code workflows)
echo "# Hello" | gwark docs create "Quick Doc" -f -

# AI-generated content via Claude Code
claude "Write Q1 planning agenda as markdown" | gwark docs create "Meeting Notes" -f -

# Export doc as markdown
gwark docs get DOC_ID --format markdown

# Append content to existing doc
gwark docs edit DOC_ID --append "## New Section"

# Summarize via Claude Code
gwark docs summarize DOC_ID | claude "Summarize as bullet points"
```

#### Section-Aware Editing (v2)

Collaborate safely without destroying others' work:

```bash
# View document structure (heading hierarchy with indices)
gwark docs sections DOC_ID
gwark docs sections DOC_ID --format tree

# Preview changes before applying
gwark docs edit DOC_ID --append "## New Section" --dry-run

# Insert content after a specific section
echo "New content here" | gwark docs edit DOC_ID --insert-after "Introduction" -f -

# Move sections (reorder without destroying content)
gwark docs edit DOC_ID --move-section "Conclusion" --before "References"
gwark docs edit DOC_ID --move-section "Tesla" --after "Albanese"

# Delete a specific section only
gwark docs edit DOC_ID --delete-section "Draft Notes" --confirm
```

#### Editorial Workflow

AI-powered editorial assistant that reviews your document and suggests improvements:

```bash
# Step 1: Add editorial comments in Google Docs UI
# Select text and add comments like:
#   "gwark: make this more concise"
#   "gwark: rewrite in active voice"
#   "gwark: fact-check this claim"

# Step 2: Generate AI suggestions (posts as comment replies)
gwark docs review DOC_ID

# Step 3: Review suggestions in Google Docs, reply "accept" to approve

# Step 4: Apply approved changes (modifies document)
gwark docs apply DOC_ID --dry-run   # Preview first
gwark docs apply DOC_ID              # Apply changes
```

**Supported instructions:**
- Make this more concise
- Rewrite in active voice
- Clarify this section
- Fix grammar
- Suggest better wording
- Expand with details
- Simplify for beginners

**Approval keywords:** Reply "accept", "approved", "yes", "apply", "ok", or "confirm" to any gwark suggestion to approve it for application.

### Sheets

```bash
# List all spreadsheets (most recent first)
gwark sheets list
gwark sheets list -i                      # Interactive browser

# Get spreadsheet info (worksheets, metadata)
gwark sheets get SHEET_ID

# Read data from sheet
gwark sheets read SHEET_ID                      # Entire first sheet
gwark sheets read SHEET_ID -r "A1:D10"          # Specific range
gwark sheets read SHEET_ID -s "Sales Data"      # By sheet name
gwark sheets read SHEET_ID -i                   # Interactive grid viewer

# Write data (CSV/JSON from file or stdin)
gwark sheets write SHEET_ID -f data.csv
echo "A,B,C\n1,2,3" | gwark sheets write SHEET_ID -f -

# Create new spreadsheet
gwark sheets create "Q1 Report" --open          # Opens in browser

# Append rows to existing sheet
cat new_rows.csv | gwark sheets append SHEET_ID -f -

# Clear a range
gwark sheets clear SHEET_ID "Sheet1!A10:D20" --confirm

# Export
gwark sheets export SHEET_ID --format csv
gwark sheets export SHEET_ID --sheet "Summary" -o summary.csv
```

**Interactive grid viewer** (`-i` flag):
| Key | Action |
|-----|--------|
| `↑↓←→` | Navigate cells |
| `Enter` | View cell detail (full content, formula) |
| `Tab` | Next worksheet |
| `o` | Open in Google Sheets |
| `q` | Quit |

#### Comment Management

Manage comments on Google Docs (list, reply, resolve):

```bash
# Create file-level comment
gwark docs comment DOC_ID --text "Please review this section"

# List all comments (includes anchored ones created in UI)
gwark docs comment DOC_ID --list

# Reply to a comment
gwark docs comment DOC_ID --reply COMMENT_ID --text "Updated, see v2"

# Resolve/reopen comments
gwark docs comment DOC_ID --resolve COMMENT_ID
gwark docs comment DOC_ID --unresolve COMMENT_ID
```

**Note**: Due to Google API limitations, gwark can only create file-level comments. To create anchored comments (attached to specific text), use the Google Docs UI. However, gwark can list, reply to, and resolve all comment types.

**Edit options:**
| Option | Description |
|--------|-------------|
| `--append` | Append content at document end |
| `--prepend` | Prepend content at document start |
| `--replace` | Replace text globally (`old::new`) |
| `--insert-after` | Insert after a heading (section-aware) |
| `--move-section` | Move section to new position |
| `--before/--after` | Target position for move |
| `--delete-section` | Delete section by heading |
| `--dry-run` | Preview changes without applying |
| `--confirm` | Require confirmation before apply |
| `--highlight` | Yellow background on inserted content |
| `--comment` | Add file comment explaining the edit |
| `--keep-revision` | Mark revision as permanent |

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
3. Enable APIs: Gmail, Calendar, Drive, Forms, Docs, **Sheets**
4. Create OAuth2 credentials (Desktop App)
5. Download credentials JSON
6. Save as `.gwark/credentials/oauth2_credentials.json`

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
├── .gwark/                 # Runtime config & secrets (gitignored)
├── config/                 # Templates & examples
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
# Install with dev dependencies (uv recommended)
uv pip install -e ".[dev]"

# Or with standard pip
pip install -e ".[dev]"

# Run tests
pytest

# Format code (or use uvx to run without installing)
uvx black src/ tests/
uvx ruff check src/ tests/
```

## Roadmap

- [x] Interactive terminal viewers for email, calendar, drive
- [x] Parallel email fetching (50 threads)
- [ ] MCP Server for Claude Desktop integration
- [ ] Summary caching to avoid re-processing
- [ ] Retry logic with exponential backoff
- [ ] Multi-account support

## License

MIT License - see [LICENSE](LICENSE) for details.

---

Built with [Typer](https://typer.tiangolo.com/) and [Rich](https://rich.readthedocs.io/)
