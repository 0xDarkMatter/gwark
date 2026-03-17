# AGENTS.md - AI Assistant Guide for gwark

This document provides context for AI assistants working on the gwark codebase.

## Project Overview

**gwark** is a Google Workspace CLI tool built with Python/Typer for Gmail, Calendar, Drive, Forms, Docs, and **Sheets** operations. It uses OAuth2 for authentication and supports AI-powered summarization via Claude.

## Architecture

```
src/
├── gwark/                  # CLI application (Typer)
│   ├── main.py             # Entry point, subcommand registration
│   ├── commands/           # Command modules (email, calendar, drive, config, forms, docs, sheets)
│   ├── core/               # Utilities (config, output, dates, markdown_converter, docs_analyzer, sheets_client)
│   ├── ui/                 # Interactive viewers (email, calendar, sheets grid)
│   └── schemas/            # Pydantic models (config, themes)
│
└── gmail_mcp/              # Core library (reusable)
    ├── auth/               # OAuth2 management (oauth.py has service getters)
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
| gspread | Google Sheets (cleaner API than raw client) |
| anthropic | AI summarization |
| mistune | Markdown parsing (for docs module) |

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
| Add doc theme | `src/gwark/schemas/themes.py` + `.gwark/themes/*.yaml` |
| Add doc section operation | `src/gwark/core/docs_analyzer.py` + `commands/docs.py` |
| Add sheets operation | `src/gwark/core/sheets_client.py` + `commands/sheets.py` |
| Add Google API service | `src/gmail_mcp/auth/oauth.py` (add get_*_service function) |

## Current Status

- **Working**: CLI, email search, config, forms, docs (v2 with section-aware editing), **sheets** (full CRUD + pivot tables), **drive** (full file management + sharing)
- **Optimized**: Calendar (parallel multi-calendar fetching), Sheets (parallel range reads)
- **Planned**: MCP server, summary caching

## Async Utilities

Located in `src/gwark/core/async_utils.py`:

| Class/Function | Purpose |
|----------------|---------|
| `AsyncFetcher` | Bounded parallel execution with rate limiting |
| `SyncRateLimiter` | Token bucket rate limiter |
| `run_async()` | Sync wrapper for async code in CLI |
| `parallel_map()` | Convenience function for parallel mapping |

**Usage pattern:**
```python
from gwark.core.async_utils import AsyncFetcher, run_async

async def fetch_all_items():
    fetcher = AsyncFetcher(max_concurrent=10, rate_per_second=50)
    return await fetcher.fetch_all(items, api_call_func)

results = run_async(fetch_all_items())
```

## Sheets Module

Uses **gspread** library (not raw google-api-python-client) for cleaner, more Pythonic API.

| File | Purpose |
|------|---------|
| `core/sheets_client.py` | High-level gspread wrapper (`SheetsClient` class) |
| `commands/sheets.py` | CLI commands (list, get, read, write, create, append, clear, export, pivot, resize) |
| `ui/viewer.py` | `TerminalSheetsViewer` for interactive grid navigation |
| `auth/oauth.py` | `get_sheets_client()` returns authenticated gspread client |

**Key classes:**
- `SheetsClient` - Wraps gspread with methods for common operations
- `TerminalSheetsViewer` - Grid viewer with cursor navigation and cell detail

**OAuth Scopes:**
- `spreadsheets` - Full read/write access to Sheets
- `drive.file` - Create files (required for `create` command)
- `drive.metadata.readonly` - List files (required for `list` command)

**Features:**
- Accepts both spreadsheet ID and full URL (auto-extracts ID)
- Stdin support: `echo "A,B\n1,2" | gwark sheets write ID -f -`
- Auto-detects CSV vs JSON input format
- Interactive grid viewer with arrow key navigation
- **Pivot tables** via `gwark sheets pivot` command (auto-styled by default)
- **Parallel range reads** via `batch_read_parallel()` method
- **Column resizing** via `set_column_widths()` and `auto_resize_columns()`

**Pivot Table Default Style:**
Pivot tables are automatically styled when created via `create_pivot_table()`:
- Font: Roboto 10pt, dark grey text (#424242)
- Header: Light blue background (#e3f2fd), bold
- Data rows: White background
- Subtotal rows: Light gray (#f5f5f5), bold
- Grand Total: Medium gray (#e0e0e0), bold

To disable auto-styling: `create_pivot_table(..., apply_style=False)`

## Drive Module

Full file management using Google Drive API v3.

| File | Purpose |
|------|---------|
| `commands/drive.py` | All commands: ls, activity, search, mkdir, rename, move, copy, rm, share |

**Key helpers (private, in drive.py):**
- `_extract_file_id(value)` — Parse URL/ID from any Google Drive/Docs/Sheets/Slides URL
- `_resolve_target(service, value, require_folder)` — Unified resolver: ID/URL → metadata, or name search with disambiguation
- `_resolve_file(service, name, mime_filter)` — Search by name with optional MIME filter
- `_get_parents(service, file_id)` — Fetch parent folder IDs (needed for move)
- `_list_folder_files(service, folder_id, type_filter, recursive)` — BFS folder listing
- `_display_file_preview(files, action, destination)` — Preview for destructive operations

**Shared drive support:** Every API call uses `supportsAllDrives=True` and `includeItemsFromAllDrives=True`.

**Safety pattern:** Destructive commands (move, copy, rm) support `--dry-run` and `--confirm` flags. Each prints a warning before execution explaining what will happen.

**Permanent delete is disabled.** The `rm` command only moves files to trash (recoverable 30 days). The `--permanent` option is commented out in the code — uncomment to re-enable hard deletes.

**Share subcommands:** `gwark drive share list/add/remove` — Typer sub-app for permission management.

## Forms Module

- Uses Forms API for read/write and Drive API for listing (Forms API has no list)
- Supports all question types: text, paragraph, choice, checkbox, dropdown, scale, date, time

## Docs Module

- Creates/edits docs via batchUpdate API
- Converts markdown to Docs API requests using mistune AST parser
- Theme system in `src/gwark/schemas/themes.py` (YAML themes in `.gwark/themes/`)
- Supports stdin input for Fabric/Claude Code pipeline integration
- No direct API calls - AI features work via piping to/from Claude Code

### Docs v2 - Collaborative-Friendly Editing

Section-aware operations that don't destroy collaborators' work:

| File | Purpose |
|------|---------|
| `core/docs_analyzer.py` | Document structure analysis (heading hierarchy, indices) |
| `commands/docs.py` | `sections` command + enhanced `edit` with section ops |

**Key classes:**
- `Section` - Represents heading + content with start/end indices
- `DocumentStructure` - Parsed document with section list and lookup methods
- `DocsStructureAnalyzer` - Parses Google Docs API response to extract sections

**Edit operations:**
- `--insert-after <heading>` - Insert content after a specific section
- `--move-section <heading> --before/--after <target>` - Reorder sections
- `--delete-section <heading>` - Remove specific section only
- `--dry-run` - Preview changes without applying
- `--confirm` - Require confirmation before apply

**Collaboration visibility:**
- `--highlight` - Yellow background on inserted content (helps collaborators see changes)
- `--comment "note"` - Add file-level comment explaining the edit
- `--keep-revision` - Mark revision as permanent in version history

**Implementation notes:**
- Operations ordered by descending index to prevent cascade issues
- Move extracts paragraph styles and re-applies them after insertion
- Sections command outputs table/tree/json formats

## Configuration Schema (CRITICAL)

When adding Path fields to Pydantic models in `schemas/config.py`, **always use `PathAsStr`** instead of `Path` to ensure YAML serialization works correctly:

```python
from gwark.schemas.config import PathAsStr  # Import the custom type

class MyConfig(BaseModel):
    # CORRECT - serializes to string in YAML
    output_dir: PathAsStr = Field(default=Path("./output"))

    # WRONG - causes YAML parsing errors with Python-specific tags
    # output_dir: Path = Field(default=Path("./output"))
```

**Why?** Raw `Path` objects serialize to YAML as `!!python/object/apply:pathlib._local.WindowsPath` which can't be loaded by safe YAML parsers. The `PathAsStr` type uses Pydantic's `PlainSerializer` to convert paths to strings automatically.

## Slides Module

Uses **Google Slides API** directly (like Docs, unlike Sheets which uses gspread).

| File | Purpose |
|------|---------|
| `core/slides_client.py` | High-level Slides API wrapper (`SlidesClient` class) |
| `commands/slides.py` | CLI commands (list, get, create, add-slide, edit, export) |
| `auth/oauth.py` | `get_slides_service()` returns authenticated API service |

**Key classes:**
- `SlidesClient` - Wraps Slides API with methods for common operations
- `SlideInfo` - Dataclass representing a slide with title, notes, elements
- `PresentationStructure` - Parsed presentation with slide list and lookup methods

**OAuth Scopes:**
- `presentations` - Full read/write access to Slides

**Features:**
- Accepts both presentation ID and full URL (auto-extracts ID)
- Stdin support: `echo "# Title\n- Point" | gwark slides create "Deck" -f -`
- Markdown format for slide creation (--- separates slides)
- Speaker notes via `## Speaker Notes` section
- Interactive viewer with split-pane layout
- Template cloning via Drive API copy
- Text replacement across all slides
- Slide reordering and deletion

**Markdown Format:**
```markdown
# Slide Title
- Bullet point 1
- Bullet point 2

## Speaker Notes
Notes here (not shown on slide)

---

# Next Slide
More content
```

**Note: PDF Export Limitation**
Google Slides API does not support direct PDF export.
Workaround: Use Drive API export (requires `drive` scope).

## Don't

- Don't use async batch operations for Gmail (causes SSL errors)
- Don't commit `.env` or `.gwark/credentials/oauth2_credentials.json`
- Don't commit `.gwark/tokens/` (contains OAuth tokens)
- Don't hardcode API keys
- Don't use raw `Path` type in Pydantic models that get YAML-serialized (use `PathAsStr`)
