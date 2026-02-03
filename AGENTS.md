# AGENTS.md - AI Assistant Guide for gwark

This document provides context for AI assistants working on the gwark codebase.

## Project Overview

**gwark** is a Google Workspace CLI tool built with Python/Typer for Gmail, Calendar, Drive, Forms, and Docs operations. It uses OAuth2 for authentication and supports AI-powered summarization via Claude.

## Architecture

```
src/
├── gwark/                  # CLI application (Typer)
│   ├── main.py             # Entry point, subcommand registration
│   ├── commands/           # Command modules (email, calendar, drive, config, forms, docs)
│   ├── core/               # Utilities (config, output, dates, markdown_converter, docs_analyzer)
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
| Add Google API service | `src/gmail_mcp/auth/oauth.py` (add get_*_service function) |

## Current Status

- **Working**: CLI, email search, config, forms, docs (v2 with section-aware editing)
- **Needs Testing**: Calendar meetings, Drive activity
- **Planned**: MCP server, summary caching, retry logic

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

## Don't

- Don't use async batch operations for Gmail (causes SSL errors)
- Don't commit `.env` or `.gwark/credentials/oauth2_credentials.json`
- Don't commit `.gwark/tokens/` (contains OAuth tokens)
- Don't hardcode API keys
- Don't use raw `Path` type in Pydantic models that get YAML-serialized (use `PathAsStr`)
