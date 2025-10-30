# Setup Guide

Complete guide to installing and configuring the Gmail MCP Server.

## Prerequisites

- Python 3.10 or higher
- Gmail account
- Google Cloud Platform account (free tier is sufficient)

## Installation Steps

### 1. Clone the Repository

```bash
git clone https://github.com/yourusername/gmail-mcp.git
cd gmail-mcp
```

### 2. Create Virtual Environment (Recommended)

```bash
# Create virtual environment
python -m venv venv

# Activate (Windows)
venv\Scripts\activate

# Activate (macOS/Linux)
source venv/bin/activate
```

### 3. Install Dependencies

```bash
# Install in editable mode
pip install -e .

# Or with development dependencies
pip install -e ".[dev]"
```

### 4. Google Cloud Setup

See [OAUTH_SETUP.md](OAUTH_SETUP.md) for detailed Google Cloud Console configuration.

Quick steps:
1. Create a Google Cloud project
2. Enable Gmail API
3. Create OAuth2 credentials (Desktop App)
4. Download credentials JSON
5. Save as `config/oauth2_credentials.json`

### 5. Configure Environment

```bash
# Copy example environment file
cp .env.example .env

# Edit .env with your preferred settings
# Most defaults work well for typical usage
```

### 6. Authenticate

```bash
# Run OAuth2 setup script
python scripts/setup_oauth.py

# This will:
# 1. Open a browser for Google authentication
# 2. Request necessary permissions
# 3. Save encrypted tokens to data/tokens/
```

### 7. Test the Setup

```bash
# Test Gmail API connection
python scripts/test_connection.py

# This verifies:
# - OAuth2 credentials are valid
# - Gmail API is accessible
# - Basic operations work
```

### 8. Run the Server

```bash
# Run as a module
python -m gmail_mcp

# Or use the installed command
gmail-mcp
```

## Configuration Options

### Environment Variables

Create a `.env` file in the project root:

```env
# Logging
LOG_LEVEL=INFO

# Cache
CACHE_ENABLED=true
CACHE_TTL_SECONDS=3600
MAX_CACHE_SIZE_MB=500

# Gmail API
DEFAULT_PAGE_SIZE=100
MAX_BATCH_SIZE=50
MAX_RESULTS_PER_SEARCH=500

# Rate Limiting
RATE_LIMIT_ENABLED=true
RATE_LIMIT_PER_SECOND=10
RATE_LIMIT_BURST=20

# Multi-Account
DEFAULT_ACCOUNT_ID=primary
MAX_ACCOUNTS=5
```

### YAML Configuration

For advanced configuration, edit `config/server_config.yaml`:

```yaml
server:
  name: "Gmail MCP Server"
  version: "0.1.0"

logging:
  level: "INFO"
  file: "logs/gmail_mcp.log"

oauth2:
  credentials_path: "config/oauth2_credentials.json"
  scopes:
    - "https://www.googleapis.com/auth/gmail.readonly"
    - "https://www.googleapis.com/auth/gmail.modify"
    - "https://www.googleapis.com/auth/gmail.labels"

cache:
  enabled: true
  database_path: "data/cache/email_cache.db"
  ttl_seconds: 3600
```

## MCP Client Integration

### Claude Desktop

Add to your Claude Desktop configuration:

**Windows**: `%APPDATA%\Claude\claude_desktop_config.json`
**macOS**: `~/Library/Application Support/Claude/claude_desktop_config.json`

```json
{
  "mcpServers": {
    "gmail": {
      "command": "python",
      "args": ["-m", "gmail_mcp"],
      "cwd": "E:\\Projects\\Coding\\GmailMCP"
    }
  }
}
```

### Other MCP Clients

The server uses stdio transport and follows the MCP specification. Any compliant MCP client should work.

## Multi-Account Setup

### Add Additional Accounts

```bash
# Run OAuth2 setup with account ID
python scripts/setup_oauth.py --account-id work

# This creates a separate token for "work" account
# You can have up to 5 accounts (configurable)
```

### Use in Requests

```json
{
  "query": "is:unread",
  "account_id": "work"
}
```

## Directory Structure

After setup, your directory should look like:

```
GmailMCP/
├── config/
│   ├── oauth2_credentials.json  # Your OAuth2 credentials
│   └── server_config.yaml       # Optional custom config
├── data/
│   ├── tokens/
│   │   └── primary.token        # Encrypted OAuth2 tokens
│   └── cache/
│       └── email_cache.db       # SQLite cache
├── logs/
│   └── gmail_mcp.log            # Server logs
└── .env                         # Environment variables
```

## Verification

### Check Authentication

```bash
python -c "from gmail_mcp.auth import TokenManager; tm = TokenManager(); print('Accounts:', tm.list_accounts())"
```

### Check Cache

```bash
python -c "import asyncio; from gmail_mcp.cache import EmailCache; ec = EmailCache(); asyncio.run(ec.initialize()); asyncio.run(ec.get_stats()).then(print)"
```

### View Logs

```bash
tail -f logs/gmail_mcp.log
```

## Troubleshooting

### Authentication Issues

**Problem**: "No credentials found"
- Run `python scripts/setup_oauth.py` again
- Check `config/oauth2_credentials.json` exists
- Verify file permissions

**Problem**: "Invalid credentials"
- Token may have expired
- Re-run OAuth2 setup
- Check Google Cloud Console for API issues

### Permission Issues

**Problem**: "Insufficient permissions"
- Verify OAuth2 scopes in config
- Re-authenticate with correct scopes
- Check Google Cloud Console OAuth consent screen

### Cache Issues

**Problem**: "Cache database locked"
- Only one server instance can run at a time
- Close other instances
- Delete `data/cache/email_cache.db` and restart

### API Quota Issues

**Problem**: "Rate limit exceeded"
- Reduce `RATE_LIMIT_PER_SECOND` in .env
- Increase `DEFAULT_PAGE_SIZE` to fetch more per request
- Enable caching to reduce API calls

## Next Steps

- Read [API.md](API.md) for available tools
- Check [ARCHITECTURE.md](ARCHITECTURE.md) for design details
- Review [PERFORMANCE.md](PERFORMANCE.md) for optimization tips
- See [examples/](../examples/) for usage examples

## Getting Help

- Check [TROUBLESHOOTING.md](TROUBLESHOOTING.md)
- Open an issue on GitHub
- Join our discussions
