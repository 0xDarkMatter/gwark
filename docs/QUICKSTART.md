# Quick Start Guide - OAuth2 Setup

## Prerequisites
✓ Python dependencies installed
✓ Gmail account

## Google Cloud Console Setup (5 minutes)

### 1. Create Google Cloud Project

1. Go to: https://console.cloud.google.com/
2. Click "Select a project" → "NEW PROJECT"
3. Name: **Gmail MCP Server**
4. Click "CREATE"

### 2. Enable Gmail API

1. In search bar, type "Gmail API"
2. Click "Gmail API" → "ENABLE"
3. Wait ~10 seconds for activation

### 3. Configure OAuth Consent Screen

1. Go to: APIs & Services → OAuth consent screen
2. Select **"External"** user type → CREATE
3. Fill in:
   - App name: **Gmail MCP Server**
   - User support email: **your email**
   - Developer contact: **your email**
4. Click "SAVE AND CONTINUE"

#### Add Scopes:
1. Click "ADD OR REMOVE SCOPES"
2. Filter/search for these scopes:
   - ✓ `.../auth/gmail.readonly` - View email messages and settings
   - ✓ `.../auth/gmail.modify` - Read, compose, and send emails
   - ✓ `.../auth/gmail.labels` - Manage labels
3. Click "UPDATE" → "SAVE AND CONTINUE"

#### Add Test Users:
1. Click "ADD USERS"
2. Enter your Gmail address
3. Click "ADD" → "SAVE AND CONTINUE"
4. Review summary → "BACK TO DASHBOARD"

### 4. Create OAuth2 Credentials

1. Go to: APIs & Services → Credentials
2. Click "CREATE CREDENTIALS" → "OAuth client ID"
3. Application type: **Desktop app**
4. Name: **Gmail MCP Desktop Client**
5. Click "CREATE"

### 5. Download Credentials

1. In the popup, click "DOWNLOAD JSON"
2. Save file as: `E:\Projects\Coding\GmailMCP\config\oauth2_credentials.json`

**Important:** This file contains secrets - never commit to git!

## Next Step: Authenticate

Once you have `.gwark/credentials/oauth2_credentials.json`, run:

```bash
python scripts/setup_oauth.py
```

This will:
1. Open your browser
2. Ask you to sign in to Gmail
3. Request permissions
4. Save encrypted tokens locally

## Test It!

```bash
# Test connection
python scripts/test_connection.py

# Search emails from grandprix.com.au
python scripts/email_search.py --domain grandprix.com.au --days-back 180
```

## Troubleshooting

**"OAuth client was not found"**
- Make sure credentials file is in `.gwark/credentials/oauth2_credentials.json`
- Verify file is named exactly `oauth2_credentials.json`

**"Access blocked: This app's request is invalid"**
- Add your email as a test user in OAuth consent screen
- Make sure all 3 scopes are added

**"invalid_grant"**
- Delete `.gwark/tokens/primary.token`
- Re-run `python scripts/setup_oauth.py`

## Need Help?

See detailed guide: `docs/OAUTH_SETUP.md`
