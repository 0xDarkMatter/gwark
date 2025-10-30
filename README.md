# Gmail MCP Server

A robust Model Context Protocol (MCP) server for Gmail integration, designed to handle large email volumes efficiently with smart caching, pagination, and batch operations.

## Features

- **Async Architecture**: Built on asyncio for high performance and concurrent operations
- **Smart Caching**: SQLite-based caching reduces API calls for repeated queries
- **Intelligent Pagination**: Cursor-based pagination management for large result sets
- **Batch Operations**: Process multiple emails efficiently in parallel (up to 50 at a time)
- **Advanced Filtering**: Rich query builder beyond basic Gmail search syntax
- **Multi-Account Support**: Manage multiple Gmail accounts with encrypted token storage
- **Rate Limiting**: Intelligent rate limiting to prevent API quota exhaustion
- **Encrypted Token Storage**: Secure OAuth2 token storage with Fernet encryption

## Quick Start

### 1. Installation

```bash
# Clone the repository
git clone https://github.com/yourusername/gmail-mcp.git
cd gmail-mcp

# Install dependencies
pip install -e .

# Or install with development dependencies
pip install -e ".[dev]"
```

### 2. Google Cloud Setup

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Create a new project or select an existing one
3. Enable the Gmail API
4. Create OAuth2 credentials (Desktop App)
5. Download the credentials JSON file
6. Save it as `config/oauth2_credentials.json`

See [docs/OAUTH_SETUP.md](docs/OAUTH_SETUP.md) for detailed instructions.

### 3. Authentication

```bash
# Run the OAuth2 setup script
python scripts/setup_oauth.py

# Follow the prompts to authenticate
```

### 4. Run the Server

```bash
# Run as a module
python -m gmail_mcp

# Or use the CLI command
gmail-mcp
```

### 5. Configure Your MCP Client

Add to your MCP client configuration (e.g., Claude Desktop):

```json
{
  "mcpServers": {
    "gmail": {
      "command": "python",
      "args": ["-m", "gmail_mcp"],
      "cwd": "/path/to/gmail-mcp"
    }
  }
}
```

## Email Search Utility

A standalone command-line tool for searching and exporting Gmail emails with token-efficient operation.

### Features

- **Token-efficient summary mode** (default) - Uses Gmail API `metadata` format for fast searches
- **Markdown table output** - Compact one-email-per-line format with clickable Gmail links
- **Optional preview snippets** - Show ~100 char email previews in summary tables
- **Full detail mode** - Includes complete email bodies and attachments when needed
- **Multiple export formats** - JSON, CSV, Text, Markdown
- **Smart name extraction** - Automatically parses names from email addresses
- **Flexible filtering** - Search by domain, sender, recipient, subject, or custom query

### Quick Examples

```bash
# Quick summary search (fast, metadata only)
python scripts/email_search.py --domain example.com --format markdown

# Summary with preview snippets
python scripts/email_search.py --domain example.com --format markdown --show-preview

# Full detail search (includes bodies/attachments)
python scripts/email_search.py --domain example.com --detail-level full --format markdown

# Export to CSV for analysis
python scripts/email_search.py --sender john@example.com --format csv --days-back 30

# Custom Gmail query with attachments
python scripts/email_search.py --query "has:attachment larger:5M" --days-back 60
```

### Output Formats

#### Summary Mode (Default - Fast)
- Uses Gmail API `metadata` format
- Includes: subject, from, to, date, Gmail snippet
- No email bodies or attachment details
- **Perfect for quick email scanning**

#### Full Mode (Slower)
- Uses Gmail API `full` format
- Includes: everything from summary + full email body + attachment details
- Use when you need complete email content

#### Markdown Table Format
```markdown
| Date | From → To | Subject | Link |
|------|-----------|---------|------|
| 30/10/2025 | John Doe → Jane Smith | Project Update | [View](gmail-link) |
```

With `--show-preview`:
```markdown
| Date | From → To | Subject | Preview | Link |
|------|-----------|---------|---------|------|
| 30/10/2025 | John Doe → Jane Smith | Project Update | Thanks for the update on the project... | [View](gmail-link) |
```

### All Options

```bash
# Search filters
--domain DOMAIN              # Domain to search (e.g., 'example.com')
--sender EMAIL               # Sender email address
--recipient EMAIL            # Recipient email address
--subject TEXT               # Subject line search term
--query QUERY                # Raw Gmail query (overrides other filters)

# Date range
--days-back N                # Days to look back (default: 180)

# Output options
--max-results N              # Maximum results (default: 500)
--format FORMAT              # json, csv, text, markdown (default: json)
--detail-level LEVEL         # summary (fast) or full (slow) (default: summary)
--show-preview               # Show email snippets in markdown tables

# Account
--account-id ID              # Gmail account ID (default: primary)
```

Results are saved to the `reports/` directory with timestamps.

## Available Tools

### Search & Read

- `search_emails` - Search emails with pagination support
- `read_email` - Read a specific email by ID
- `batch_read` - Read multiple emails in parallel

### Labels & Organization

- `list_labels` - List all Gmail labels
- `apply_labels` - Add/remove labels from an email
- `remove_labels` - Remove labels from an email
- `batch_apply_labels` - Apply/remove labels from multiple emails

### Quick Actions

- `mark_as_read` / `mark_as_unread` - Mark emails as read/unread
- `archive` - Archive emails (remove from INBOX)
- `star` / `unstar` - Star/unstar emails

### Account

- `get_profile` - Get user profile information

## Usage Examples

### Search for Unread Emails

```python
{
  "query": "is:unread",
  "max_results": 100,
  "page_size": 50
}
```

### Search with Advanced Filters

```python
{
  "query": "from:example@gmail.com after:2024/01/01 has:attachment",
  "max_results": 200
}
```

### Read an Email

```python
{
  "message_id": "18c5a1b2f3d4e5f6",
  "format": "full"
}
```

### Batch Read Multiple Emails

```python
{
  "message_ids": ["msg_001", "msg_002", "msg_003"],
  "format": "metadata"
}
```

### Apply Labels

```python
{
  "message_id": "18c5a1b2f3d4e5f6",
  "label_ids": ["Label_123"],
  "remove_labels": ["INBOX"]
}
```

## Architecture

```
GmailMCP/
├── src/gmail_mcp/
│   ├── auth/          # OAuth2 authentication & token management
│   ├── gmail/         # Gmail API client & operations
│   ├── cache/         # SQLite caching & pagination
│   ├── server/        # MCP server implementation
│   ├── utils/         # Utilities (logging, rate limiting, validators)
│   └── config/        # Configuration management
├── tests/             # Test suite
├── docs/              # Documentation
├── scripts/           # Setup & utility scripts
└── examples/          # Usage examples
```

## Configuration

Environment variables (create a `.env` file):

```env
LOG_LEVEL=INFO
CACHE_ENABLED=true
CACHE_TTL_SECONDS=3600
DEFAULT_PAGE_SIZE=100
MAX_BATCH_SIZE=50
RATE_LIMIT_PER_SECOND=10
```

See [.env.example](.env.example) for all available options.

## Performance Optimizations for Large Volumes

### Caching Strategy

- **Metadata Cache**: 1-hour TTL for email metadata
- **Content Cache**: Full email content cached with configurable TTL
- **Search Results Cache**: Query results cached to reduce repeated searches
- **Automatic Cleanup**: Expired entries removed automatically

### Pagination

- **Cursor-Based**: Efficient pagination using Gmail's page tokens
- **State Management**: Pagination state persisted for resumable operations
- **Smart Batching**: Configurable page sizes (10-500 results)

### Batch Operations

- **Parallel Processing**: Up to 50 emails processed concurrently
- **Semaphore Control**: Limits concurrent API calls
- **Fallback Strategy**: Individual operations if batch fails
- **Partial Success**: Returns both successful and failed operations

### Rate Limiting

- **Token Bucket Algorithm**: Respects Gmail API quotas (250 units/user/second)
- **Automatic Throttling**: Backs off on rate limit errors
- **Burst Support**: Allows short bursts within limits

## Development

### Setup Development Environment

```bash
# Install with dev dependencies
pip install -e ".[dev]"

# Install pre-commit hooks
pre-commit install

# Run tests
pytest

# Run tests with coverage
pytest --cov=gmail_mcp --cov-report=html

# Format code
black src/ tests/
ruff check src/ tests/

# Type checking
mypy src/
```

### Project Structure

See [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) for detailed architecture documentation.

## Documentation

- [Setup Guide](docs/SETUP.md) - Detailed installation and configuration
- [OAuth2 Setup](docs/OAUTH_SETUP.md) - Google Cloud Console setup
- [API Documentation](docs/API.md) - Complete tool reference
- [Architecture](docs/ARCHITECTURE.md) - Design decisions and patterns
- [Performance Guide](docs/PERFORMANCE.md) - Optimization tips

## Troubleshooting

See [docs/TROUBLESHOOTING.md](docs/TROUBLESHOOTING.md) for common issues and solutions.

## Contributing

Contributions are welcome! Please read our contributing guidelines before submitting pull requests.

## License

MIT License - see [LICENSE](LICENSE) for details.

## Acknowledgments

- Built with [MCP SDK](https://github.com/anthropics/mcp)
- Gmail API by Google
- Inspired by the need for better email management in large-volume environments

## Support

- Issues: https://github.com/yourusername/gmail-mcp/issues
- Discussions: https://github.com/yourusername/gmail-mcp/discussions
