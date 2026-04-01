# Google Drive Query Syntax

Drive search queries for `gwark drive search` and `gwark drive ls`.

**Note:** Drive query syntax is different from Gmail query syntax.

## Text Search

```bash
gwark drive search "quarterly report"          # Full-text search
gwark drive search "name contains 'budget'"    # Name only
```

## Type Filters

Use `--type` flag (gwark handles the MIME translation):

| Flag | Matches |
|------|---------|
| `docs` | Google Docs |
| `sheets` | Google Sheets |
| `slides` | Google Slides |
| `forms` | Google Forms |
| `pdf` | PDF files |
| `images` | JPEG, PNG, GIF, BMP, TIFF |
| `folders` | Folders |

## Date Filters

Drive API uses RFC 3339 dates:
- `modifiedTime > '2025-01-01T00:00:00'`
- `createdTime > '2025-01-01T00:00:00'`

gwark's `--year`/`--month` flags on `drive activity` handle this automatically.

## Owner Filters

- `'me' in owners` — Files you own
- `'user@example.com' in writers` — Files shared with write access

## Shared Drive

All gwark Drive commands automatically include `supportsAllDrives=True` and `includeItemsFromAllDrives=True`. No special flags needed.

## MIME Types (internal reference)

| Type | MIME |
|------|------|
| Docs | `application/vnd.google-apps.document` |
| Sheets | `application/vnd.google-apps.spreadsheet` |
| Slides | `application/vnd.google-apps.presentation` |
| Forms | `application/vnd.google-apps.form` |
| Folders | `application/vnd.google-apps.folder` |
| PDF | `application/pdf` |
