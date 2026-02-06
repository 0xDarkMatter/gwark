# Current Sprint Plan

**Sprint**: v0.3.0 - Google Sheets Integration
**Updated**: 2026-02-05
**Goal**: Integrate Google Sheets into Gwark using gspread, deprecate standalone GSheets project

---

## Current Sprint: Google Sheets Integration

### Design Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| API Library | **gspread exclusively** | Cleaner API than raw google-api-python-client |
| Auth Bridge | `gspread.authorize(creds)` | Accepts google-auth Credentials directly |
| Pandas Support | Optional dependency | Power feature via `--df` flag |
| Interactive Mode | Grid-based viewer | Navigate cells with arrow keys |

### Command Structure

```
gwark sheets
├── list                 # List all spreadsheets
├── get <id>             # Get spreadsheet metadata + sheet list
├── read <id> [range]    # Read data (default: Sheet1!A:Z)
├── write <id> [range]   # Write data from file/stdin
├── create <title>       # Create new spreadsheet
├── append <id>          # Append rows to sheet
├── clear <id> <range>   # Clear cells in range
└── export <id>          # Export as CSV/JSON/Excel
```

### Implementation Phases

#### Phase 1: Auth Bridge ✅
- [x] Add `get_sheets_credentials()` to `oauth.py`
- [x] Add `get_sheets_client()` to `oauth.py`
- [x] Update `__init__.py` exports
- [x] Test: `python -c "from gmail_mcp.auth import get_sheets_client; print(get_sheets_client())"`

#### Phase 2: Core Client ✅
- [x] Create `src/gwark/core/sheets_client.py`
- [x] Implement `SheetsClient` class with gspread
- [x] Test: List spreadsheets via client

#### Phase 3: Commands (MVP) ✅
- [x] Create `src/gwark/commands/sheets.py`
- [x] Implement: `list`, `get`, `read`
- [x] Register in `main.py`
- [x] Test: `gwark sheets list`, `gwark sheets read <id>`

#### Phase 4: Full Commands ✅
- [x] Add: `write`, `create`, `append`, `clear`, `export`
- [x] Add `--df` flag with optional pandas import
- [x] Test: Full CRUD operations

#### Phase 5: Interactive Mode ✅
- [x] Add `TerminalSheetsViewer` to `viewer.py`
- [x] Wire `-i` flag on `list` and `read` commands
- [x] Test: `gwark sheets list -i`

#### Phase 6: Deprecate GSheets ✅
- [x] Update `X:\Fabric\GSheets\README.md` with deprecation notice
- [x] Point users to `gwark sheets` commands
- [x] Archive GSheets project

### Critical Files

| File | Action |
|------|--------|
| `src/gmail_mcp/auth/oauth.py` | Add `get_sheets_client()` |
| `src/gmail_mcp/auth/__init__.py` | Export new functions |
| `src/gwark/core/sheets_client.py` | NEW - gspread wrapper |
| `src/gwark/commands/sheets.py` | NEW - CLI commands |
| `src/gwark/main.py` | Register sheets app |
| `src/gwark/ui/viewer.py` | Add sheets viewer |
| `pyproject.toml` | Add gspread dependency |

---

## Completed (v0.1.0 → v0.2.0)

### gwark CLI Implementation
- [x] Create `gwark` package structure (`src/gwark/`)
- [x] Implement Typer-based CLI with subcommands
- [x] Email commands: search, sent, summarize
- [x] Calendar command: meetings
- [x] Drive command: activity
- [x] Config commands: init, show, auth, profile
- [x] Forms commands: list, get, responses, create, add-question
- [x] Docs commands: create, get, edit, sections, theme, summarize, comment, review, apply
- [x] Core utilities: config loader, output formatters, date parsing
- [x] YAML-based configuration (`.gwark/config.yaml`)
- [x] Profile system with work/default profiles

### Cleanup
- [x] Delete redundant scripts
- [x] Archive deprecated scripts to `scripts/_deprecated/`
- [x] Optimize rate limits for Google Workspace (250 req/sec, 50 concurrent)

### Infrastructure
- [x] Add Typer and Rich dependencies
- [x] Update pyproject.toml with gwark entry point
- [x] Create `.gwark/` config directory with profiles

---

## Pending (v0.3.x)

### Error Handling & Resilience ✅
- [x] Add retry logic with exponential backoff for rate limits (429)
- [x] Graceful degradation when AI API key is missing
- [x] Better error messages for OAuth failures

### Testing
- [ ] Basic unit tests for config loading
- [ ] Basic tests for sheets operations
- [ ] Integration tests with real Google Sheets

---

## Deferred (Future)

### MCP Server (v0.4.0+)
- [ ] Complete MCP server implementation
- [ ] Tool registration for Claude Desktop
- [ ] Integration testing with MCP clients

### Advanced Features
- [ ] Email body search (not just metadata)
- [ ] Attachment downloading
- [ ] Label management
- [ ] Email sending

### Distribution
- [ ] PyPI package publishing
- [ ] Shell completion scripts
- [ ] Docker image

---

## Architecture

```
src/
├── gmail_mcp/          # Core library (OAuth, API clients, cache)
│   └── auth/           # OAuth2 + service getters (gmail, calendar, drive, sheets)
└── gwark/              # CLI tool
    ├── commands/       # Typer command modules (email, calendar, drive, forms, docs, sheets)
    ├── core/           # Utilities (config, output, dates, sheets_client)
    ├── ui/             # Interactive viewers
    └── schemas/        # Pydantic config models

.gwark/                 # Project-local configuration
├── config.yaml         # Main settings
├── credentials/        # OAuth2 credentials
├── tokens/             # Cached auth tokens
└── profiles/           # Filter profiles
```

---

## Key Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| CLI Framework | Typer | Modern, type-hint based, auto-generates help |
| Config Format | YAML | Human-readable, supports comments |
| Config Location | `.gwark/` (project-local) | Per-project customization |
| Rate Limits | 250/sec, 50 concurrent | Google Workspace defaults |
| Sheets Library | gspread | Pythonic API, easier than raw google-api-python-client |
| MCP Server | Deferred | Focus on CLI first |

---

Last Updated: 2026-02-05
