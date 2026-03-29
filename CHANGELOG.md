# Changelog

All notable changes to this tool are documented here.
Format: [Keep a Changelog](https://keepachangelog.com/)

## [0.3.0] - 2026-03-29

### Added
- `gwark email senders` command — find unique senders by name, domain, or email with deduplication
- Contact enrichment via `--enrich` flag (known/prior/unknown from Google Contacts)
- OAuth scope validation — auto-detects mismatched scopes and re-authenticates

### Fixed
- OAuth re-auth now forces consent prompt only when scopes need upgrading
- Empty contacts cache no longer poisons subsequent enrichment attempts

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
- Add Cloudflare Workers MCP server and project documentation
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
