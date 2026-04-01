```
 ██████╗ ██╗    ██╗ █████╗ ██████╗ ██╗  ██╗
██╔════╝ ██║    ██║██╔══██╗██╔══██╗██║ ██╔╝
██║  ███╗██║ █╗ ██║███████║██████╔╝█████╔╝
██║   ██║██║███╗██║██╔══██║██╔══██╗██╔═██╗
╚██████╔╝╚███╔███╔╝██║  ██║██║  ██║██║  ██╗
 ╚═════╝  ╚══╝╚══╝ ╚═╝  ╚═╝╚═╝  ╚═╝╚═╝  ╚═╝
```

[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

Google Workspace from the command line. Built for agentic workflows and Claude Code integration.

gwark gives AI agents and power users direct access to Gmail, Calendar, Drive, Docs, Sheets, Slides, and Forms through composable CLI commands. Every command outputs structured data (JSON, CSV, markdown), accepts stdin, and can be piped into other tools — making it a natural fit for AI-assisted workflows where an agent needs to search emails, create documents, or analyze data without touching a browser.

```bash
# Claude Code can search your email, find contacts, create docs
gwark email senders --name "smith" --enrich
gwark email search --domain client.com --days 90 --summarize
claude "Write Q1 report" | gwark docs create "Q1 Report" -f - --open
gwark forms responses FORM_ID -f csv | gwark sheets write SHEET_ID -f -
```

Includes 8 Claude Code skills (`.claude/skills/gwark-*/`) for automatic context loading when working with Google Workspace tasks.

## What it does

- **Email** — Search, find unique senders with contact enrichment, AI summaries, sent analysis
- **Calendar** — Multi-calendar meeting history with parallel fetching, work-only filtering
- **Drive** — Full file management: list, search, move, copy, share, activity tracking
- **Docs** — Create from markdown, section-aware editing, themes, comments, AI editorial review
- **Sheets** — Read/write via gspread, pivot tables with auto-styling, CSV/JSON export
- **Slides** — Create presentations from markdown, edit, export
- **Forms** — Create surveys, add questions, export responses
- **Interactive viewers** — Terminal UI for emails, calendar, sheets, and slides
- **Profiles** — Filter work/personal content per context
- **API preflight** — `gwark config auth test --all` checks every Google API before you start

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
│   ├── senders     Find unique senders by name/domain/email (--enrich for contacts)
│   ├── sent        Analyze sent emails for a month
│   └── summarize   AI summarize emails from JSON
├── calendar
│   └── meetings    Extract calendar meetings (-i for interactive)
├── drive
│   ├── ls          List folder contents (-i for interactive)
│   ├── activity    Extract file activity (-i for interactive)
│   ├── search      Search files with filters (-i for interactive)
│   ├── mkdir       Create folders
│   ├── rename      Rename files or folders
│   ├── move        Move files/folders (supports cross-drive)
│   ├── copy        Copy files/folders (--recursive for folders)
│   ├── rm          Move files to trash (recoverable 30 days)
│   └── share       Manage permissions (list/add/remove)
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
│   ├── export      Export as CSV/JSON
│   ├── pivot       Create pivot table with auto-styling
│   └── resize      Adjust column widths
├── slides
│   ├── list        List presentations (-i for interactive)
│   ├── get         Get presentation structure (-i for viewer)
│   ├── create      Create from markdown or template
│   ├── add-slide   Add slide to presentation
│   ├── edit        Delete, move, or replace text
│   └── export      Export as markdown/JSON
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

### Unique Senders

```bash
# Find all unique senders matching a name
gwark email senders --name "smith" --days 365

# Search by domain with contact enrichment
gwark email senders --domain example.com --enrich

# Export unique contacts as CSV
gwark email senders --name "jones" -f csv -o contacts.csv

# Complex query (spelling variants)
gwark email senders --query "from:nevill OR from:neville"
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
# List folder contents
gwark drive ls "Project Files" --type sheets
gwark drive ls "Root Folder" --recursive --type docs

# File activity for a month
gwark drive activity --year 2025 --month 1

# Search files
gwark drive search "quarterly report" --type docs
gwark drive search "invoice" --in "Finance" --type pdf

# Create folders
gwark drive mkdir "New Folder"
gwark drive mkdir "Sub Folder" --parent "New Folder"

# Move files (supports cross-drive)
gwark drive move "Report.docx" "Archive" --confirm
gwark drive move "Source" "Dest" --type sheets --dry-run

# Copy files
gwark drive copy "Template" "Projects" --name "Q1 Report"
gwark drive copy "Shared Folder" "My Drive" --recursive

# Trash files (recoverable for 30 days)
gwark drive rm "old-file.txt"
gwark drive rm "Archive" --type pdf --dry-run

# Manage sharing
gwark drive share list "Report"
gwark drive share add "Report" user@example.com --role writer
gwark drive share remove "Report" user@example.com
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

# Pivot tables (auto-styled with Roboto, light blue header, gray totals)
gwark sheets pivot SHEET_ID -s "Data!A1:E100" -r "Category" -v "sum:Sales"
gwark sheets pivot SHEET_ID -s "Sales!A:D" -r "Region,Product" -c "Month" -v "sum:Revenue,avg:Profit"

# Resize columns
gwark sheets resize SHEET_ID -s "Pivot" -w "130,160,150,420,100"
gwark sheets resize SHEET_ID -s "Data" --auto   # Auto-fit content
```

**Pivot table options:**
| Option | Description |
|--------|-------------|
| `-s, --source` | Source data range (e.g., `Data!A1:E100`) |
| `-t, --target` | Target cell for pivot (default: `Sheet1!F1`) |
| `-r, --rows` | Row groupings (comma-separated column names) |
| `-c, --cols` | Column groupings (optional) |
| `-v, --values` | Aggregations: `sum:Sales`, `avg:Profit`, `count:ID` |

**Aggregation functions:** SUM, COUNT, AVERAGE, MAX, MIN, COUNTUNIQUE, MEDIAN, STDEV

**Interactive grid viewer** (`-i` flag):
| Key | Action |
|-----|--------|
| `↑↓←→` | Navigate cells |
| `Enter` | View cell detail (full content, formula) |
| `Tab` | Next worksheet |
| `o` | Open in Google Sheets |
| `q` | Quit |

### Slides

```bash
# List all presentations (most recent first)
gwark slides list
gwark slides list -i                        # Interactive browser

# Get presentation structure
gwark slides get PRES_ID                    # Markdown outline
gwark slides get PRES_ID -f json            # Full JSON structure
gwark slides get PRES_ID -i                 # Interactive viewer

# Create presentation
gwark slides create "My Deck" --open        # Empty, opens in browser
gwark slides create "Report" --file slides.md
gwark slides create "Q1 Review" --template TEMPLATE_ID

# Pipe from Claude Code
claude "Create Q1 planning outline as markdown" | gwark slides create "Q1 Plan" -f -

# Add slides
gwark slides add-slide PRES_ID --title "New Slide"
gwark slides add-slide PRES_ID --layout BLANK --position 2

# Edit operations
gwark slides edit PRES_ID --delete-slide 3
gwark slides edit PRES_ID --move-slide "5:2"
gwark slides edit PRES_ID --replace "2024::2025"

# Export
gwark slides export PRES_ID -f markdown -o presentation.md
gwark slides export PRES_ID -f json
```

**Markdown format for slides:**
```markdown
# Slide Title
- Bullet point 1
- Bullet point 2

## Speaker Notes
Hidden notes for presenter.

---

# Next Slide
More content here.
```

**Interactive viewer** (`-i` flag):
| Key | Action |
|-----|--------|
| `↑↓` | Navigate slides |
| `n` | Toggle speaker notes |
| `o` | Open in Google Slides |
| `g/G` | Go to top/bottom |
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
3. Enable the APIs you need (see table below)
4. Create OAuth2 credentials (Desktop App)
5. Download credentials JSON
6. Save as `.gwark/credentials/oauth2_credentials.json`

### Required APIs

Enable these in **APIs & Services > Library** in your Google Cloud project:

| API | gwark Commands | Enable URL |
|-----|---------------|------------|
| Gmail API | `email search`, `email senders`, `email sent` | [Enable](https://console.cloud.google.com/apis/library/gmail.googleapis.com) |
| Google Calendar API | `calendar meetings` | [Enable](https://console.cloud.google.com/apis/library/calendar-json.googleapis.com) |
| Google Drive API | `drive ls`, `drive search`, `drive move`, etc. | [Enable](https://console.cloud.google.com/apis/library/drive.googleapis.com) |
| Google Docs API | `docs create`, `docs edit`, `docs sections` | [Enable](https://console.cloud.google.com/apis/library/docs.googleapis.com) |
| Google Sheets API | `sheets read`, `sheets write`, `sheets pivot` | [Enable](https://console.cloud.google.com/apis/library/sheets.googleapis.com) |
| Google Slides API | `slides create`, `slides edit`, `slides export` | [Enable](https://console.cloud.google.com/apis/library/slides.googleapis.com) |
| Google Forms API | `forms list`, `forms create`, `forms responses` | [Enable](https://console.cloud.google.com/apis/library/forms.googleapis.com) |
| People API | `email senders --enrich` (optional) | [Enable](https://console.cloud.google.com/apis/library/people.googleapis.com) |

You only need to enable the APIs for features you use. gwark authenticates each service separately on first use.

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

## Recent Changes (v0.3.5)

- **Unique senders** — `gwark email senders` finds unique contacts by name, domain, or email with deduplication and optional Google Contacts enrichment
- **API preflight check** — `gwark config auth test --all` checks every Google API with status table and enable URLs
- **8 Claude Code skills** — focused skills for email, docs, drive, sheets, slides, forms, triage (replaces monolithic gwark-ops)
- **OAuth scope validation** — auto-detects mismatched token scopes and re-authenticates
- **Google Slides** — full presentation management (create, edit, export, interactive viewer)
- **Drive file management** — mkdir, rename, move, copy, rm, share commands
- **73 tests** — unit tests for core modules + CLI smoke tests

See [CHANGELOG.md](CHANGELOG.md) for full history.

## License

MIT License - see [LICENSE](LICENSE) for details.

---

Built with [Typer](https://typer.tiangolo.com/) and [Rich](https://rich.readthedocs.io/)
