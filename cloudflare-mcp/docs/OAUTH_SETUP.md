# OAuth 2.1 Setup Guide

This guide walks you through setting up Google OAuth 2.1 authentication for the Gmail MCP Server.

## Prerequisites

- Google Cloud account
- Cloudflare Workers account
- Gmail MCP Server deployed (or running locally)

## Step 1: Create Google Cloud Project

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Click **Select a project** → **New Project**
3. Enter project name: `Gmail MCP Server`
4. Click **Create**

## Step 2: Enable Gmail API

1. In your project, go to **APIs & Services** → **Library**
2. Search for "Gmail API"
3. Click **Gmail API**
4. Click **Enable**

## Step 3: Configure OAuth Consent Screen

1. Go to **APIs & Services** → **OAuth consent screen**
2. Select **External** (unless you have Google Workspace)
3. Click **Create**

### Fill in Application Information:

- **App name**: Gmail MCP Server
- **User support email**: Your email
- **Developer contact email**: Your email
- Click **Save and Continue**

### Add Scopes:

Click **Add or Remove Scopes** and add:
- `https://www.googleapis.com/auth/gmail.readonly` - Read emails
- `https://www.googleapis.com/auth/gmail.modify` - Modify emails (labels, etc.)
- `https://www.googleapis.com/auth/gmail.labels` - Manage labels
- `https://www.googleapis.com/auth/userinfo.email` - User email
- `https://www.googleapis.com/auth/userinfo.profile` - User profile

Click **Update** → **Save and Continue**

### Add Test Users (if using External):

1. Click **Add Users**
2. Enter your Gmail address
3. Click **Add** → **Save and Continue**

## Step 4: Create OAuth 2.0 Credentials

1. Go to **APIs & Services** → **Credentials**
2. Click **Create Credentials** → **OAuth client ID**
3. Select **Application type**: Web application
4. **Name**: Gmail MCP Server

### Add Authorized Redirect URIs:

For local development:
```
http://localhost:8787/oauth/callback
```

For production:
```
https://gmail-mcp.your-account.workers.dev/oauth/callback
```

(Replace `your-account` with your actual Cloudflare Workers subdomain)

5. Click **Create**
6. **Save the Client ID and Client Secret** - you'll need these!

## Step 5: Configure Worker Secrets

### For Local Development:

Create `.dev.vars` file:

```bash
cd cloudflare-mcp
cp .dev.vars.example .dev.vars
```

Edit `.dev.vars`:

```env
GOOGLE_CLIENT_ID=your_client_id_here.apps.googleusercontent.com
GOOGLE_CLIENT_SECRET=your_client_secret_here
```

### For Production:

Set secrets using Wrangler:

```bash
wrangler secret put GOOGLE_CLIENT_ID
# Paste your Client ID

wrangler secret put GOOGLE_CLIENT_SECRET
# Paste your Client Secret
```

## Step 6: Update Redirect URI in Code

Edit `src\durable-objects\session.ts` and update the redirect URI:

```typescript
this.oauthManager = new OAuthManager({
  clientId: env.GOOGLE_CLIENT_ID,
  clientSecret: env.GOOGLE_CLIENT_SECRET,
  redirectUri: `https://gmail-mcp.YOUR-ACCOUNT.workers.dev/oauth/callback`, // UPDATE THIS
});
```

Or for dynamic configuration, update based on environment:

```typescript
const baseUrl = env.ENVIRONMENT === 'development'
  ? 'http://localhost:8787'
  : 'https://gmail-mcp.YOUR-ACCOUNT.workers.dev';

redirectUri: `${baseUrl}/oauth/callback`,
```

## Step 7: Test OAuth Flow

### Local Testing:

```bash
npm run dev
```

Visit: `http://localhost:8787/oauth/authorize`

This will redirect you to Google's OAuth consent screen.

### Production Testing:

```bash
npm run deploy
```

Visit: `https://gmail-mcp.your-account.workers.dev/oauth/authorize`

## OAuth Flow Diagram

```
User                  Worker                  Google OAuth
 |                       |                         |
 |---(1) /oauth/authorize-->                       |
 |                       |---(2) Redirect to------>|
 |<--(3) Consent Screen--|                         |
 |                       |                         |
 |---(4) Approve-------------------------------> |
 |                       |<--(5) Authorization code-|
 |                       |                         |
 |<--(6) /oauth/callback-|                         |
 |                       |---(7) Exchange code---->|
 |                       |<--(8) Access + Refresh--|
 |<--(9) Success page----|                         |
```

## OAuth 2.1 Features

This implementation uses OAuth 2.1 with the following security features:

### PKCE (Proof Key for Code Exchange)

- Generates random `code_verifier` (43-128 characters)
- Creates SHA-256 hash as `code_challenge`
- Prevents authorization code interception attacks

### State Parameter

- Random 32-byte state for CSRF protection
- Validated on callback
- 10-minute expiration

### Refresh Tokens

- Stored securely in Durable Object storage
- Automatic token refresh when expired
- 5-minute buffer before expiration

## Troubleshooting

### "redirect_uri_mismatch" Error

**Problem**: The redirect URI doesn't match what's configured in Google Cloud Console.

**Solution**:
1. Check the redirect URI in Google Cloud Console matches exactly
2. Include protocol (`http://` or `https://`)
3. No trailing slash
4. Update `src/durable-objects/session.ts` with correct URI

### "access_denied" Error

**Problem**: User denied consent or not in test users list.

**Solution**:
1. Add user to test users in OAuth consent screen
2. User must approve all requested scopes

### Token Refresh Fails

**Problem**: Refresh token is invalid or expired.

**Solution**:
1. Re-authenticate to get new refresh token
2. Ensure `access_type=offline` and `prompt=consent` in auth URL
3. Check that refresh token is being stored correctly

### "Invalid client" Error

**Problem**: Client ID or Secret is incorrect.

**Solution**:
1. Verify secrets are set correctly: `wrangler secret list`
2. Check for extra spaces or newlines in secrets
3. Regenerate OAuth credentials if needed

## Security Best Practices

1. **Never commit secrets** - Use `.dev.vars` (gitignored) or Wrangler secrets
2. **Use HTTPS in production** - Required for OAuth 2.1
3. **Validate state parameter** - Prevents CSRF attacks
4. **Use PKCE** - Prevents authorization code interception
5. **Set token expiration** - Refresh tokens before they expire
6. **Revoke tokens** - When user logs out or deletes account

## Next Steps

After OAuth is set up:

1. Test authentication flow
2. Implement Gmail API client
3. Wire up MCP tools to use OAuth tokens
4. Test email search, read, and modify operations

## Resources

- [Google OAuth 2.0 Documentation](https://developers.google.com/identity/protocols/oauth2)
- [OAuth 2.1 Specification](https://oauth.net/2.1/)
- [Gmail API Scopes](https://developers.google.com/gmail/api/auth/scopes)
- [PKCE RFC 7636](https://tools.ietf.org/html/rfc7636)
