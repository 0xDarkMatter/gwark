# OAuth2 Setup Guide

Step-by-step guide to creating Google Cloud credentials for gwark.

## Overview

gwark uses OAuth2 to access Google Workspace APIs on your behalf. You create credentials once in the Google Cloud Console, then gwark handles authentication and token refresh automatically.

## Step 1: Create a Google Cloud Project

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Click "Select a project" dropdown at the top
3. Click "NEW PROJECT"
4. Enter project name (e.g., "gwark")
5. Click "CREATE"
6. Select your new project from the dropdown

## Step 2: Enable APIs

Navigate to **APIs & Services > Library** and enable these APIs:

### Required (core functionality)

| API | Used By |
|-----|---------|
| Gmail API | `gwark email` commands |
| Google Calendar API | `gwark calendar` commands |
| Google Drive API | `gwark drive` commands |

### Optional (enable as needed)

| API | Used By |
|-----|---------|
| Google Docs API | `gwark docs` commands |
| Google Sheets API | `gwark sheets` commands |
| Google Slides API | `gwark slides` commands |
| Google Forms API | `gwark forms` commands |
| People API | `gwark email senders --enrich` (contact status) |

Search for each API name, click it, then click **ENABLE**. You can always enable more later — gwark will tell you if an API needs to be enabled.

## Step 3: Configure OAuth Consent Screen

1. Navigate to **APIs & Services > OAuth consent screen**
2. Select **External** user type (or Internal for Workspace accounts)
3. Click "CREATE"

### App Information

- **App name**: gwark
- **User support email**: Your email address
- **Developer contact**: Your email address

Click "SAVE AND CONTINUE"

### Scopes

Click "ADD OR REMOVE SCOPES" and add:

**Core scopes** (always needed):

| Scope | Purpose |
|-------|---------|
| `gmail.readonly` | Read emails |
| `calendar.readonly` | Read calendar events |
| `drive` | Access Drive files |

**Additional scopes** (add if using those features):

| Scope | Purpose |
|-------|---------|
| `documents` | Read/write Google Docs |
| `spreadsheets` | Read/write Google Sheets |
| `presentations` | Read/write Google Slides |
| `forms.body` | Read/write Google Forms |
| `forms.responses.readonly` | Read form responses |
| `contacts.readonly` | Contact enrichment (`--enrich` flag) |
| `contacts.other.readonly` | Other Contacts lookup |

You don't need to add every scope now. gwark authenticates each service separately with its own token. When you first use a new command (e.g., `gwark sheets list`), gwark opens a browser to authorize that specific service.

Click "UPDATE" then "SAVE AND CONTINUE"

### Test Users

1. Click "ADD USERS"
2. Enter your Google account email
3. Click "ADD" then "SAVE AND CONTINUE"
4. Review summary, click "BACK TO DASHBOARD"

## Step 4: Create OAuth2 Credentials

1. Navigate to **APIs & Services > Credentials**
2. Click **CREATE CREDENTIALS > OAuth client ID**
3. Application type: **Desktop app**
4. Name: "gwark" (or anything you like)
5. Click "CREATE"

### Download Credentials

1. Click "DOWNLOAD JSON" in the popup
2. Save the file to your gwark project:

```bash
# Create the directory if it doesn't exist
gwark config init

# Move the downloaded file
mv ~/Downloads/client_secret_*.json .gwark/credentials/oauth2_credentials.json
```

**Important**: This file contains secrets — never commit it to git. It's already in `.gitignore`.

## Step 5: Authenticate

```bash
# Initial authentication (opens browser)
gwark config auth setup

# This will:
# 1. Open your browser
# 2. Ask you to sign in with your Google account
# 3. Request the Gmail API permissions
# 4. Save tokens securely (OS keyring or encrypted file)
```

Other services authenticate on first use. For example, running `gwark calendar meetings` for the first time will open a browser to authorize Calendar access.

## Step 6: Verify

```bash
# Test authentication
gwark config auth test

# List authenticated services
gwark config auth list

# Quick functional test
gwark email search --domain gmail.com --days 1 --max-results 3
```

## Credential Verification

Your `.gwark/credentials/oauth2_credentials.json` should look like:

```json
{
  "installed": {
    "client_id": "123456789-abc.apps.googleusercontent.com",
    "project_id": "your-project-id",
    "auth_uri": "https://accounts.google.com/o/oauth2/auth",
    "token_uri": "https://oauth2.googleapis.com/token",
    "auth_provider_x509_cert_url": "https://www.googleapis.com/oauth2/v1/certs",
    "client_secret": "GOCSPX-...",
    "redirect_uris": ["http://localhost"]
  }
}
```

## Token Storage

gwark stores OAuth tokens using this priority:

1. **OS Keyring** (primary) — encrypted by your OS
2. **Legacy pickle files** (auto-migrated to keyring on first use)

Tokens auto-refresh when expired. You shouldn't need to re-authenticate unless you revoke access or change scopes.

### Scope Upgrades

gwark automatically detects when a stored token is missing required scopes. It will delete the old token and prompt for re-authentication with the correct scopes. No manual intervention needed.

## Security

### Protecting Credentials

| File | Contains | Gitignored |
|------|----------|------------|
| `.gwark/credentials/oauth2_credentials.json` | OAuth client secret | Yes |
| `.gwark/tokens/` | Refresh tokens | Yes |
| OS Keyring | Encrypted tokens | N/A (system) |

### Revoking Access

If you need to revoke gwark's access:

1. Go to [Google Account Permissions](https://myaccount.google.com/permissions)
2. Find your gwark app name
3. Click "Remove Access"
4. Remove local tokens:

```bash
# Remove specific service
gwark config auth remove gmail

# Or remove all
gwark config auth remove all
```

## Publishing Your App (Optional)

For personal use, keep the app in "Testing" mode — up to 100 test users.

To share with others without adding test users:

1. Navigate to OAuth consent screen
2. Click "PUBLISH APP"
3. Complete Google's verification process (may take days)

## Troubleshooting

### "Access blocked: This app's request is invalid"

- Add your email as a test user in the OAuth consent screen
- Verify the consent screen is fully configured (all required fields)

### "The OAuth client was not found"

- Re-download credentials from Google Cloud Console
- Verify the file is at `.gwark/credentials/oauth2_credentials.json`
- Check the file contains `"installed"` (not `"web"` — must be Desktop App type)

### "invalid_grant" Error

Token expired or revoked:

```bash
gwark config auth remove gmail
gwark config auth setup
```

### "insufficient_scope" Error

gwark v0.3.0+ auto-detects and re-authenticates with the correct scopes. If this persists:

```bash
# Remove the token for the affected service and retry
gwark config auth remove people
```

### "API has not been used in project"

Enable the API in Google Cloud Console:
1. Go to APIs & Services > Library
2. Search for the API name from the error message
3. Click Enable
4. Wait 1-2 minutes for propagation

## Next Steps

- [QUICKSTART.md](QUICKSTART.md) — Start using gwark
- [SETUP.md](SETUP.md) — Full configuration guide
