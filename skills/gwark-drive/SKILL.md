---
name: gwark-drive
description: "Google Drive file operations with gwark: list, search, move, copy, share, activity. Use when: browsing files, searching Drive, managing permissions, moving or copying files, folder operations. Triggers: google drive, drive files, file sharing, drive search, move files, drive activity, list files, copy files, drive permissions."
version: 1.0.0
tool: gwark
category: domain
requires:
  bins: ["gwark"]
allowed-tools: "Read Bash Grep Glob"
---

# gwark Drive

File management for Google Drive — list, search, organize, share.

## List Files

```bash
# List folder contents
gwark drive ls "My Documents"
gwark drive ls "Project Files" --type sheets         # Filter by type
gwark drive ls "Root Folder" --recursive --type docs  # Recursive

# List root (My Drive)
gwark drive ls

# Interactive browser
gwark drive ls "Reports" -i
```

### Type Filters

| Filter | Matches |
|--------|---------|
| `sheets` | Google Sheets |
| `docs` | Google Docs |
| `slides` | Google Slides |
| `forms` | Google Forms |
| `pdf` | PDF files |
| `images` | JPEG, PNG, GIF, etc. |
| `folders` | Folders only |

## Search

```bash
# Text search across all files
gwark drive search "quarterly report"

# Search with type filter
gwark drive search "invoice" --type pdf

# Search within folder
gwark drive search "budget" --in "Finance"

# Interactive results
gwark drive search "meeting notes" -i
```

## File Operations

### Create Folders

```bash
gwark drive mkdir "New Project"
gwark drive mkdir "Subfolder" --parent "New Project"
```

### Rename

```bash
gwark drive rename FILE_ID "New Name"
gwark drive rename "https://docs.google.com/..." "Better Name"
```

### Move

```bash
# Move file to folder
gwark drive move "Report.docx" "Archive" --confirm

# Preview first (no changes)
gwark drive move "Source" "Dest" --type sheets --dry-run

# Cross-drive moves supported
gwark drive move FILE_ID "Shared Drive/Folder" --confirm
```

### Copy

```bash
# Copy file
gwark drive copy "Template" "Projects" --name "Q1 Report"

# Copy folder recursively
gwark drive copy "Shared Folder" "My Drive" --recursive
```

### Delete (Trash)

```bash
# Move to trash (recoverable 30 days)
gwark drive rm "old-file.txt"

# Preview what would be deleted
gwark drive rm "Archive" --type pdf --dry-run
```

**Safety:** `rm` only moves to trash. Permanent delete is disabled by default.

## Sharing & Permissions

```bash
# List who has access
gwark drive share list "Report"

# Share with someone
gwark drive share add "Report" user@example.com --role writer

# Remove access
gwark drive share remove "Report" user@example.com
```

### Roles

| Role | Can Do |
|------|--------|
| `reader` | View only |
| `commenter` | View + comment |
| `writer` | View + edit |
| `owner` | Full control (transfer ownership) |

## Activity

```bash
# Monthly file activity report
gwark drive activity --year 2025 --month 3

# Interactive viewer
gwark drive activity --year 2025 --month 3 -i
```

## ID Resolution

All commands accept Drive file IDs or full URLs:

```bash
# These are equivalent
gwark drive ls 1abc2def3ghi
gwark drive ls "https://drive.google.com/drive/folders/1abc2def3ghi"

# Works with Docs, Sheets, Slides URLs too
gwark drive rename "https://docs.google.com/document/d/1xyz/edit" "New Name"
```

## Pipe Patterns

| From | To | Pattern |
|------|----|---------|
| drive ls | jq | `gwark drive ls "Folder" -f json \| jq '.[] \| .name'` |
| drive search | sheets | `gwark drive search "report" -f csv -o files.csv` |

## Gotchas

- **Folder resolution is name-based.** If multiple folders share a name, gwark shows disambiguation prompt.
- **`--confirm` required** for move/copy/rm. Use `--dry-run` to preview.
- **Shared Drive support:** All API calls use `supportsAllDrives=True`.
- **Recursive operations** can be slow on large folder trees. Use `--dry-run` first.
- **Trash is recoverable** for 30 days. No permanent delete via CLI.

For Drive API query syntax, see [references/drive-queries.md](references/drive-queries.md).
