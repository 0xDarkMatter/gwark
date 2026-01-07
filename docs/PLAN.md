# Current Sprint Plan

**Sprint**: v0.2.0 - gwark CLI
**Updated**: 2026-01-07
**Goal**: Unified Google Workspace CLI tool with profile-based configuration

---

## Completed (v0.1.0 → v0.2.0)

### gwark CLI Implementation
- [x] Create `gwark` package structure (`src/gwark/`)
- [x] Implement Typer-based CLI with subcommands
- [x] Email commands: search, sent, summarize
- [x] Calendar command: meetings
- [x] Drive command: activity
- [x] Config commands: init, show, auth, profile
- [x] Core utilities: config loader, output formatters, date parsing
- [x] YAML-based configuration (`.gwark/config.yaml`)
- [x] Profile system with work/default profiles

### Cleanup
- [x] Delete redundant scripts (sent_emails_simple.py, sent_emails_direct.py, etc.)
- [x] Delete root-level artifacts (NUL files, .coverage, etc.)
- [x] Archive deprecated scripts to `scripts/_deprecated/`
- [x] Optimize rate limits for Google Workspace (250 req/sec, 50 concurrent)

### Infrastructure
- [x] Add Typer and Rich dependencies
- [x] Update pyproject.toml with gwark entry point
- [x] Create `.gwark/` config directory with profiles

---

## In Progress

- [ ] Test gwark CLI with real Gmail account
- [ ] Verify all commands work end-to-end

---

## Pending (v0.2.x)

### Error Handling & Resilience
- [ ] Add retry logic with exponential backoff for rate limits (429)
- [ ] Graceful degradation when AI API key is missing
- [ ] Better error messages for OAuth failures

### Caching
- [ ] Cache AI summaries to avoid re-processing
- [ ] Cache search results with TTL
- [ ] Progress indicators for long operations

### Testing
- [ ] Basic unit tests for config loading
- [ ] Basic tests for date parsing utilities
- [ ] Basic tests for output formatters

### Documentation
- [ ] Update CLAUDE.md with gwark CLI info
- [ ] Create docs/CLI.md with full command reference
- [ ] Add examples to profiles

---

## Deferred (Future)

### MCP Server (v0.3.0+)
- [ ] Complete MCP server implementation
- [ ] Tool registration for Claude Desktop
- [ ] Integration testing with MCP clients

### Advanced Features
- [ ] Email body search (not just metadata)
- [ ] Attachment downloading
- [ ] Label management
- [ ] Email sending
- [ ] Incremental sync

### Distribution
- [ ] PyPI package publishing
- [ ] Shell completion scripts
- [ ] Docker image

---

## Architecture

```
src/
├── gmail_mcp/          # Core library (OAuth, Gmail API client, cache)
└── gwark/              # CLI tool
    ├── commands/       # Typer command modules
    ├── core/           # Utilities (config, output, dates)
    └── schemas/        # Pydantic config models

.gwark/                 # Project-local configuration
├── config.yaml         # Main settings
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
| MCP Server | Deferred | Focus on CLI first |

---

Last Updated: 2026-01-07
