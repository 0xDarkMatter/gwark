# Gmail MCP Server - Claude Code Development Guide

This document provides comprehensive information about the Gmail MCP Server project for Claude Code and other AI assistants.

## Project Overview

The Gmail MCP Server is a Model Context Protocol (MCP) server that provides robust Gmail integration with advanced features for handling large email volumes efficiently. It includes smart caching, pagination, batch operations, and AI-powered email summarization.

## Current Project Status

**Branch:** `feature/email-summarization`
**Last Updated:** October 31, 2025

### Recent Development

We recently implemented AI-powered email summarization using Claude Haiku API:
- Batch processing (10 emails per API call)
- Comprehensive summaries (overview + 2-4 key bullet points)
- Markdown table output with merged column format
- Token-efficient operation using Claude Haiku

## Project Structure

```
GmailMCP/
├── src/gmail_mcp/          # Main MCP server code (not yet implemented)
│   ├── auth/               # OAuth2 authentication
│   ├── gmail/              # Gmail API client
│   ├── cache/              # SQLite caching
│   ├── server/             # MCP server
│   └── utils/              # Utilities
├── scripts/                # Standalone utility scripts
│   ├── setup_oauth.py      # OAuth2 setup script
│   ├── email_search.py     # Email search & export utility
│   ├── email_summarizer.py # AI email summarization module
│   └── test_connection.py  # Connection test script
├── config/                 # Configuration files
│   └── oauth2_credentials.json  # Google OAuth2 credentials
├── data/                   # Data storage
│   ├── tokens/             # Encrypted OAuth2 tokens
│   └── cache/              # Email cache database
├── reports/                # Email search export reports
├── tests/                  # Test suite
├── docs/                   # Documentation
├── .env                    # Environment variables (gitignored)
└── README.md               # Main documentation
```

## Key Features Implemented

### 1. Email Search Utility (`scripts/email_search.py`)

A standalone command-line tool for searching and exporting Gmail emails.

**Features:**
- Token-efficient metadata searches
- Full detail mode with bodies and attachments
- AI-powered summarization using Claude Haiku
- Multiple export formats (JSON, CSV, Text, Markdown)
- Smart name extraction from email addresses
- Flexible filtering (domain, sender, recipient, subject, custom query)
- Markdown table output with clickable Gmail links

**Usage Examples:**
```bash
# AI-powered summaries
python scripts/email_search.py --domain example.com --format markdown --summarize

# Quick metadata search
python scripts/email_search.py --domain example.com --format markdown

# Full detail with attachments
python scripts/email_search.py --domain example.com --detail-level full --format markdown

# Export to CSV
python scripts/email_search.py --sender john@example.com --format csv --days-back 30
```

### 2. AI Email Summarization (`scripts/email_summarizer.py`)

Batch email summarization using Claude Haiku API.

**Features:**
- Batch processing (10 emails per API call for efficiency)
- Comprehensive summaries (1-2 sentence overview + 2-4 key points)
- Uses Claude Haiku (claude-3-haiku-20240307) for cost-effectiveness
- Smart parsing of numbered email responses
- Processes up to 2500 characters per email body
- 4000 max tokens for comprehensive summaries

**Output Format:**
```markdown
| Date | From → To | Subject | Link |
|------|-----------|---------|------|
| 30/10/2025 | John Doe → Jane Smith | Project Update | [View](link) |
|               - *Overview*: Status update on Q4 project timeline and budget allocation.|
|               - Project is 80% complete with Friday delivery                            |
|               - Database migration issue resolved                                       |
|               - Requesting financial projections for meeting                            |
|                                                                                         |
```

### 3. OAuth2 Authentication (`scripts/setup_oauth.py`)

Handles Google OAuth2 authentication flow for Gmail API access.

**Features:**
- Desktop application OAuth2 flow
- Token storage and management
- Automatic token refresh
- Encrypted token storage

## Environment Configuration

### Required Environment Variables

The `.env` file contains the following configuration:

```env
# Server Configuration
SERVER_NAME="Gmail MCP Server"
SERVER_VERSION="0.1.0"
LOG_LEVEL="INFO"

# OAuth2 Configuration
OAUTH2_CREDENTIALS_PATH="config/oauth2_credentials.json"
TOKEN_STORAGE_PATH="data/tokens"
ENCRYPTION_KEY=""  # Auto-generated

# Cache Configuration
CACHE_ENABLED="true"
CACHE_DB_PATH="data/cache/email_cache.db"
CACHE_TTL_SECONDS="3600"
MAX_CACHE_SIZE_MB="500"

# Gmail API Configuration
DEFAULT_PAGE_SIZE="100"
MAX_BATCH_SIZE="50"
MAX_RESULTS_PER_SEARCH="500"

# Rate Limiting
RATE_LIMIT_ENABLED="true"
RATE_LIMIT_PER_SECOND="10"
RATE_LIMIT_BURST="20"

# AI Summarization (Claude API)
ANTHROPIC_API_KEY="your-api-key-here"
```

### Setting up ANTHROPIC_API_KEY

For AI email summarization:
1. Get your API key from Claude Code or the Anthropic Console
2. Add it to `.env`: `ANTHROPIC_API_KEY="sk-ant-..."`
3. If using Claude Code's API key, it's tied to your Max plan (no extra cost)

## Development Workflow

### Git Branches

- `master` - Main stable branch
- `feature/email-summarization` - Current development branch with AI summarization

### Recent Commits

```
f581182 feat: Add AI-powered email summarization using Claude Haiku
20fecd0 docs: Add email search utility documentation to README
578ec33 feat: Add --show-preview flag for email snippet display in summary tables
```

### Commit Message Format

We use conventional commits:
```
feat: Add new feature
fix: Bug fix
docs: Documentation changes
refactor: Code refactoring
test: Add tests
chore: Maintenance tasks
```

All commits include:
```
🤖 Generated with [Claude Code](https://claude.com/claude-code)

Co-Authored-By: Claude <noreply@anthropic.com>
```

## Technical Implementation Details

### Email Search Architecture

1. **Gmail API Integration**
   - Uses Google's Gmail API v1
   - Supports two detail levels: `metadata` (fast) and `full` (complete)
   - Async/await pattern for concurrent operations

2. **Markdown Output Format**
   - Compact table format with one email per row
   - Clickable Gmail links (`https://mail.google.com/mail/u/0/#all/{id}`)
   - Smart name extraction (e.g., "John Doe <john@example.com>" → "John Doe")
   - AI summaries as merged table rows for clean formatting

3. **AI Summarization Pipeline**
   ```
   Gmail API → Fetch Full Emails → Batch (10) → Claude Haiku → Parse Summaries → Markdown Output
   ```

### Error Handling

- Rate limit detection with backoff strategy
- Partial success handling for batch operations
- Graceful degradation when API key is missing
- Error placeholders for failed summarizations

### Performance Optimizations

- Batch processing (10 emails per API call)
- Uses Claude Haiku (fastest/cheapest model)
- Limits email body to 2500 characters
- Async operations for Gmail API calls

## Testing

### Manual Testing Process

1. **Quick Test (7 days)**
   ```bash
   python scripts/email_search.py --domain example.com --days-back 7 --format markdown --summarize
   ```

2. **Full Test (180 days)**
   ```bash
   python scripts/email_search.py --domain example.com --days-back 180 --max-results 100 --format markdown --summarize
   ```

3. **Verify Output**
   - Check `reports/` directory for generated markdown
   - Verify summaries are comprehensive and accurate
   - Ensure table formatting is correct

### Test Results

Successfully tested with:
- 61 real emails from grandprix.com.au domain
- 7 API call batches (6x10 emails + 1x1 email)
- Generated comprehensive summaries with overview + bullets
- Clean markdown table output

## Known Issues & Limitations

### Rate Limiting

- **Issue:** Anthropic API has rate limits for new accounts
- **Symptom:** Error 429 when making rapid API calls
- **Workaround:** Add delays between batches or reduce batch frequency
- **Future Fix:** Implement automatic retry with exponential backoff

### API Key Management

- **Current:** API key stored in `.env` (gitignored)
- **Security:** Never commit `.env` to version control
- **Note:** `.env` is already in `.gitignore`

### Email Body Truncation

- **Limitation:** Email bodies limited to 2500 characters
- **Reason:** Token efficiency and API cost management
- **Impact:** Very long emails may have incomplete summaries

## Future Development

### Planned Features

1. **MCP Server Implementation**
   - Complete MCP protocol server
   - Tool registration for Claude Desktop
   - Real-time email operations

2. **Enhanced Summarization**
   - Automatic rate limit handling with retries
   - Configurable summary length
   - Multi-language support
   - Summary caching to avoid re-processing

3. **Additional Tools**
   - Email sending functionality
   - Draft management
   - Calendar integration
   - Contact management

4. **Performance Improvements**
   - Persistent cache for summaries
   - Incremental updates
   - Background processing

## Claude Code Integration

### Using with Claude Code

Claude Code can assist with:
1. Understanding the codebase
2. Implementing new features
3. Debugging issues
4. Writing tests
5. Updating documentation

### Example Prompts

```
"Add rate limiting to the email summarizer"
"Create unit tests for email_search.py"
"Implement summary caching to avoid re-processing"
"Add support for multiple languages in summaries"
"Create a web interface for email search"
```

## Dependencies

### Python Packages

```
google-auth
google-auth-oauthlib
google-auth-httplib2
google-api-python-client
anthropic
python-dotenv
aiohttp
asyncio
```

### Installation

```bash
pip install -e .
# Or with dev dependencies
pip install -e ".[dev]"
```

## Resources

- [Gmail API Documentation](https://developers.google.com/gmail/api)
- [Anthropic API Documentation](https://docs.anthropic.com/)
- [MCP Protocol](https://github.com/anthropics/mcp)
- [OAuth2 Setup Guide](docs/OAUTH_SETUP.md)

## Contact & Support

This project was developed with assistance from Claude Code.

For issues and questions:
- Check existing documentation in `docs/`
- Review the README.md
- Examine code comments for implementation details

---

**Last Updated:** October 31, 2025
**Version:** 0.1.0
**Status:** Active Development (feature/email-summarization branch)
