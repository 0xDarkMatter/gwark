# Gmail MCP Server for Cloudflare Workers

A Model Context Protocol (MCP) server that provides Gmail integration for Claude Desktop and other MCP clients. Deployed on Cloudflare Workers with Durable Objects for session management.

## Features

- 🔐 OAuth 2.1 authentication with Gmail
- 📧 Search, read, and manage emails
- 🌍 Global edge deployment via Cloudflare Workers
- 💾 Durable Objects for session and token storage
- 🚀 Fast, scalable, and serverless

## Prerequisites

- Node.js 18+ and npm
- Cloudflare account
- Wrangler CLI (`npm install -g wrangler`)
- Google Cloud project with Gmail API enabled
- Google OAuth 2.0 credentials (Client ID and Secret)

## Setup

### 1. Install Dependencies

```bash
npm install
```

### 2. Configure Google OAuth

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Create a new project or select existing one
3. Enable Gmail API
4. Create OAuth 2.0 credentials (Web application)
5. Add authorized redirect URI: `https://gmail-mcp.your-subdomain.workers.dev/oauth/callback`

### 3. Set up Secrets

For local development, create `.dev.vars`:

```bash
cp .dev.vars.example .dev.vars
# Edit .dev.vars with your credentials
```

For production deployment:

```bash
wrangler secret put GOOGLE_CLIENT_ID
wrangler secret put GOOGLE_CLIENT_SECRET
```

### 4. Create KV Namespace

```bash
# Create KV namespace for caching
wrangler kv:namespace create GMAIL_CACHE

# Update wrangler.toml with the returned ID
```

## Development

### Run Locally

```bash
npm run dev
```

This starts a local development server at `http://localhost:8787`

### Test MCP Endpoint

```bash
# Health check
curl http://localhost:8787/health

# MCP initialize (requires MCP client)
curl -X POST http://localhost:8787/mcp \
  -H "Content-Type: application/json" \
  -d '{"method":"initialize","params":{}}'
```

### Type Checking

```bash
npm run type-check
```

## Deployment

### Deploy to Cloudflare Workers

```bash
npm run deploy
```

Your MCP server will be live at: `https://gmail-mcp.your-subdomain.workers.dev`

### Monitor Logs

```bash
npm run tail
```

## Configure Claude Desktop

Add to your Claude Desktop config (`~/Library/Application Support/Claude/config.json` on macOS):

```json
{
  "mcpServers": {
    "gmail": {
      "url": "https://gmail-mcp.your-subdomain.workers.dev/mcp",
      "transport": {
        "type": "sse"
      }
    }
  }
}
```

## Available MCP Tools

### `search_emails`

Search Gmail emails with filters and pagination.

**Parameters:**
- `query` (string, required): Gmail search query (e.g., "from:user@example.com")
- `maxResults` (number, optional): Maximum results to return (default: 10)

### `read_email`

Read a specific email by ID.

**Parameters:**
- `emailId` (string, required): Gmail message ID

### `get_profile`

Get Gmail user profile information.

**Parameters:** None

## Architecture

```
Cloudflare Worker (Edge)
├── Main Handler (index.ts)
│   ├── /health - Health check
│   ├── /mcp - MCP protocol endpoint
│   └── Session routing
└── Durable Object (GmailSession)
    ├── OAuth token storage
    ├── Email caching
    └── MCP tool execution
```

## Project Structure

```
cloudflare-mcp/
├── src/
│   ├── index.ts                  # Main worker entry point
│   └── durable-objects/
│       └── session.ts            # Session Durable Object
├── wrangler.toml                 # Cloudflare configuration
├── package.json                  # Dependencies and scripts
├── tsconfig.json                 # TypeScript configuration
└── README.md                     # This file
```

## Development Roadmap

- [x] Basic MCP server structure
- [x] Durable Objects for sessions
- [ ] OAuth 2.1 authentication flow
- [ ] Gmail API client implementation
- [ ] Email search functionality
- [ ] Email read functionality
- [ ] Label management
- [ ] Batch operations
- [ ] AI-powered summarization (Workers AI)
- [ ] Comprehensive error handling
- [ ] Rate limiting and caching

## Resources

- [Model Context Protocol Spec](https://spec.modelcontextprotocol.io/)
- [Cloudflare Workers Docs](https://developers.cloudflare.com/workers/)
- [Durable Objects Guide](https://developers.cloudflare.com/durable-objects/)
- [Gmail API Reference](https://developers.google.com/gmail/api)
- [Wrangler CLI Docs](https://developers.cloudflare.com/workers/wrangler/)

## License

MIT
