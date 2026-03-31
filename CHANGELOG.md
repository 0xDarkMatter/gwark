# Changelog

All notable changes to this tool are documented here.
Format: [Keep a Changelog](https://keepachangelog.com/)

## [0.3.5] - 2026-03-31

### Added
- 8 focused Claude Code skills replacing monolithic gwark-ops:
  gwark-email, gwark-docs, gwark-drive, gwark-sheets, gwark-slides,
  gwark-forms, gwark-triage, plus gwark-ops as lightweight router
- Gmail query syntax reference (references/gmail-query-syntax.md)
- Drive query syntax reference (references/drive-queries.md)
- Doc editing patterns reference (references/editing-patterns.md)
- 73 unit tests and CLI smoke tests

### Changed
- gwark-ops rewritten as router skill (~140 lines, was 324)
- Calendar stays in gwark-ops (only 2 commands)

### Removed
- Monolithic gwark-ops skill (replaced by per-module skills)
- Nested gwark-ops/gwark-ops duplicate
- Legacy standalone scripts (replaced by CLI commands)

## [0.3.1] - 2026-03-31

### Added
- `gwark config auth test --all` — preflight check for all Google APIs with status table and enable URLs
- `has_credentials()` helper to check token existence without triggering OAuth browser flow

### Changed
- Rewrite docs (SETUP, QUICKSTART, OAUTH_SETUP) for gwark CLI
- Update command help strings to reflect all available subcommands
- Add Required APIs table to README with Google Cloud Console enable links

### Removed
- Internal docs not suited for public release (PLAN, ROADMAP, GOOGLE_API_THREADING, TRIAGE_WORKFLOW)

## [0.3.0] - 2026-03-29

### Added
- `gwark email senders` command — find unique senders by name, domain, or email with deduplication
- Contact enrichment via `--enrich` flag (known/prior/unknown from Google Contacts)
- OAuth scope validation — auto-detects mismatched scopes and re-authenticates

### Fixed
- OAuth scope validation: detect mismatched scopes in keyring and legacy tokens, force consent only when needed
- Scope type coercion handles string-format scopes from older OAuth flows
- Name fallback uses email address instead of "Unknown" for senders without display names
- Timestamps use UTC to prevent date shift near midnight in non-UTC timezones
- Markdown table escaping for pipe characters and newlines in sender names
- Deduplicate subjects in sender aggregation (no repeated "Re: Invoice" entries)
- Quote-safe `--name` search strips internal double-quotes before Gmail query
- Empty contacts cache no longer poisons subsequent enrichment attempts

### Removed
- `setup.py` (obsolete — pyproject.toml handles all builds)

## [0.2.0] - 2026-03-17

### Added
- Add comprehensive file management commands
- Add retry_execute() across all modules, harden OAuth and AI checks
- Add Google Slides module
- Add exponential backoff retry for rate limits
- Add Google Sheets module with pivot tables and async optimization
- Add gwark-ops skill for CLI usage patterns
- Add core docs infrastructure (analyzer, converter, themes)
- Register docs module and add supporting infrastructure
- Add editorial workflow with approval-based apply
- register forms command in main app
- upgrade to Fabric Protocol compliance
- Add Gmail HTTP batch API for simpler email fetching
- Add email triage workflow with AI classification
- Dynamic pane width and API retry logic
- Improve list pane layout and selection
- Add glyphs to event details
- Add 'list' command to show available calendars
- Multi-calendar support with colors and Meet links
- Week-based calendar view with Monday at top
- Add polished interactive viewers for email, calendar, and drive
- Add Textual UI components for enhanced CLI experience
- Add gwark CLI for unified Google Workspace operations
- Add API efficiency improvements and code refactoring
- Add AI-powered email summarization using Claude Haiku
- Add --show-preview flag for email snippet display in summary tables
- Add token-efficient summary mode and markdown table output

### Changed
- Split config into templates (config/) and runtime (.gwark/)

### Fixed
- Use dynamic config dir resolution instead of hardcoded paths
- YAML serialization and OAuth auth setup improvements
- Use thread-local Gmail service for parallel fetch
- Add retry logic and reduce concurrency for fetch
- Add pagination to email search command
- Add space after icons before values
- Combine Meet icon with link in single append
- Icons immediately before values (no space)
- Align labels with consistent icon/indent prefix
- Move icons before values, not labels
- Increase wrap threshold to 45 chars for attendee names
- Smart wrap long attendee names and emails
- Indent wrapped location, bold attendee names
- Remove Access column, show full calendar IDs
- Remove unsupported conferenceDataVersion parameter
- Fix week navigation using day_key instead of parsing start
- Constrain navigation to current week view
- Fix markup rendering and improve week view
- Fix title visibility and date truncation
- Polish calendar viewer per user feedback
- Run interactive viewer outside async context
- Update OAuth paths and add pickle token fallback
- Add missing OAuth2Manager and TokenManager exports
