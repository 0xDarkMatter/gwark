# Configuration Templates

This directory contains **examples and templates only**.

Runtime configuration lives in `.gwark/` (gitignored).

## Setup

1. Copy templates to `.gwark/`:
   ```bash
   gwark config init
   ```
   Or manually:
   ```bash
   cp config/config.example.yaml .gwark/config.yaml
   cp -r config/profiles.example .gwark/profiles
   ```

2. Get OAuth credentials:
   - Go to [Google Cloud Console](https://console.cloud.google.com/)
   - Create OAuth2 Desktop App credentials
   - Download JSON → save as `.gwark/credentials/oauth2_credentials.json`

3. Authenticate:
   ```bash
   gwark config auth setup
   ```

## Directory Structure

```
config/                          # Templates (checked in)
├── config.example.yaml          # Main config template
├── profiles.example/            # Profile templates
│   ├── default.yaml
│   └── work.yaml
└── README.md                    # This file

.gwark/                          # Runtime (gitignored)
├── config.yaml                  # Active config
├── profiles/                    # Active profiles
├── credentials/                 # OAuth client secrets
│   └── oauth2_credentials.json
├── tokens/                      # Refresh tokens
└── cache/                       # Email cache
```
