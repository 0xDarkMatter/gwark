# OAuth2 Setup Guide

Step-by-step guide to setting up OAuth2 credentials for Gmail API access.

## Overview

The Gmail MCP server uses OAuth2 to authenticate with Gmail on behalf of the user. This guide walks through creating the necessary credentials in Google Cloud Console.

## Step 1: Create a Google Cloud Project

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Click "Select a project" dropdown at the top
3. Click "NEW PROJECT"
4. Enter project name (e.g., "Gmail MCP Server")
5. Click "CREATE"
6. Wait for the project to be created
7. Select your new project from the dropdown

## Step 2: Enable Required APIs

### Gmail API

1. In the Google Cloud Console, navigate to "APIs & Services" > "Library"
2. Search for "Gmail API"
3. Click on "Gmail API"
4. Click "ENABLE"

### People API (for Triage Workflow)

1. Search for "People API"
2. Click on "People API"
3. Click "ENABLE"

This is required for sender quality signals in the triage workflow.

## Step 3: Configure OAuth Consent Screen

1. Navigate to "APIs & Services" > "OAuth consent screen"
2. Select "External" user type (unless you have a Google Workspace account)
3. Click "CREATE"

### App Information

- **App name**: Gmail MCP Server
- **User support email**: Your email address
- **Developer contact information**: Your email address

Click "SAVE AND CONTINUE"

### Scopes

1. Click "ADD OR REMOVE SCOPES"
2. Add the following scopes:

   **Gmail API:**
   - `https://www.googleapis.com/auth/gmail.readonly` - View email messages and settings
   - `https://www.googleapis.com/auth/gmail.modify` - Read, compose, and send emails
   - `https://www.googleapis.com/auth/gmail.labels` - Manage labels on emails

   **People API (for triage workflow):**
   - `https://www.googleapis.com/auth/contacts.readonly` - View My Contacts
   - `https://www.googleapis.com/auth/contacts.other.readonly` - View Other Contacts (auto-saved)

3. Click "UPDATE"
4. Click "SAVE AND CONTINUE"

### Test Users

1. Click "ADD USERS"
2. Enter your Gmail address
3. Click "ADD"
4. Click "SAVE AND CONTINUE"

### Summary

Review the summary and click "BACK TO DASHBOARD"

## Step 4: Create OAuth2 Credentials

1. Navigate to "APIs & Services" > "Credentials"
2. Click "CREATE CREDENTIALS" > "OAuth client ID"
3. Select "Desktop app" as the application type
4. Enter name: "Gmail MCP Desktop Client"
5. Click "CREATE"

### Download Credentials

1. A dialog will appear with your Client ID and Client Secret
2. Click "DOWNLOAD JSON"
3. Save the file as `oauth2_credentials.json`
4. Move this file to `.gwark/credentials/oauth2_credentials.json` in your Gmail MCP project directory

**Important**: Keep this file secure! It contains sensitive credentials.

## Step 5: Verify Credentials File

Your `.gwark/credentials/oauth2_credentials.json` should look like this:

```json
{
  "installed": {
    "client_id": "YOUR_CLIENT_ID.apps.googleusercontent.com",
    "project_id": "your-project-id",
    "auth_uri": "https://accounts.google.com/o/oauth2/auth",
    "token_uri": "https://oauth2.googleapis.com/token",
    "auth_provider_x509_cert_url": "https://www.googleapis.com/oauth2/v1/certs",
    "client_secret": "YOUR_CLIENT_SECRET",
    "redirect_uris": [
      "http://localhost",
      "urn:ietf:wg:oauth:2.0:oob"
    ]
  }
}
```

## Step 6: Run OAuth2 Setup

```bash
# Run the setup script
python scripts/setup_oauth.py

# Follow the prompts:
# 1. A browser window will open
# 2. Sign in with your Gmail account
# 3. Grant the requested permissions
# 4. The script will save your tokens
```

### Alternative: Manual Authorization

If the browser doesn't open automatically:

```bash
python scripts/setup_oauth.py --manual

# This will:
# 1. Display an authorization URL
# 2. You copy and paste it into your browser
# 3. After authorizing, you'll get an authorization code
# 4. Paste the code back into the terminal
```

## Step 7: Verify Authentication

```bash
# Test the connection
python scripts/test_connection.py

# Expected output:
# ✓ OAuth2 credentials loaded
# ✓ Token is valid
# ✓ Gmail API connection successful
# ✓ Profile: your.email@gmail.com
```

## Security Best Practices

### Protect Your Credentials

1. **Never commit credentials to version control**
   - `.gwark/credentials/oauth2_credentials.json` is in `.gitignore`
   - `.gwark/tokens/` is in `.gitignore`

2. **File Permissions**
   - The setup script automatically sets restrictive permissions
   - Tokens are encrypted with Fernet

3. **Token Storage**
   - Tokens are stored in `.gwark/tokens/`
   - Each account has a separate encrypted token file
   - Refresh tokens allow automatic re-authentication

### Revoke Access

If you need to revoke access:

1. Go to [Google Account Permissions](https://myaccount.google.com/permissions)
2. Find "Gmail MCP Server"
3. Click "Remove Access"
4. Delete local tokens: `rm -rf .gwark/tokens/*`

## Scope Explanations

### Gmail Scopes

#### gmail.readonly
- Read email messages and metadata
- Search emails
- List labels
- Cannot modify, delete, or send emails

#### gmail.modify
- All readonly permissions, plus:
- Modify labels (mark read/unread, star, archive)
- Move to trash
- Cannot send new emails

#### gmail.labels
- Manage labels (create, update, delete)
- Assign labels to messages

### People API Scopes

#### contacts.readonly
- Read contacts from "My Contacts"
- Used to identify known senders in triage workflow

#### contacts.other.readonly
- Read contacts from "Other Contacts"
- These are auto-saved contacts from email interactions
- Used to identify prior senders in triage workflow

## Publishing Your App (Optional)

If you want to use this with multiple accounts without adding each as a test user:

1. Navigate to "OAuth consent screen"
2. Click "PUBLISH APP"
3. Submit for Google verification (if needed)
4. Wait for approval (can take several days)

**Note**: For personal use or small teams, keeping it in "Testing" mode is recommended.

## Troubleshooting

### "Access blocked: This app's request is invalid"

**Cause**: OAuth consent screen not configured properly

**Solution**:
1. Verify all required fields in OAuth consent screen
2. Ensure test users are added
3. Check that all scopes are saved

### "The OAuth client was not found"

**Cause**: Incorrect credentials file or project ID

**Solution**:
1. Re-download credentials from Google Cloud Console
2. Verify the file is named `oauth2_credentials.json`
3. Check that it's in the `config/` directory

### "invalid_grant" Error

**Cause**: Refresh token expired or revoked

**Solution**:
1. Delete existing tokens: `rm .gwark/tokens/primary.token`
2. Re-run setup: `python scripts/setup_oauth.py`

### "insufficient_scope" Error

**Cause**: Missing required scopes

**Solution**:
1. Go to OAuth consent screen in Google Cloud Console
2. Add missing scopes
3. Re-run OAuth setup
4. User must re-authorize with new scopes

## Multi-Account Setup

### Add Additional Accounts

```bash
# Setup with custom account ID
python scripts/setup_oauth.py --account-id work

# Setup another account
python scripts/setup_oauth.py --account-id personal
```

### List Configured Accounts

```bash
python scripts/setup_oauth.py --list
```

### Remove an Account

```bash
python scripts/setup_oauth.py --remove personal
```

## Next Steps

- Return to [SETUP.md](SETUP.md) to continue configuration
- Read [API.md](API.md) for available operations
- Check [examples/](../examples/) for usage examples
