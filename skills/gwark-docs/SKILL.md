---
name: gwark-docs
description: "Google Docs operations with gwark: create from markdown, section editing, themes, AI review. Use when: creating documents, editing doc content, applying themes, managing comments, editorial review. Triggers: google docs, create document, edit doc, doc theme, doc review, markdown to docs, document sections."
version: 1.0.0
category: productivity
requires:
  bins: ["gwark"]
allowed-tools: "Read Bash Grep Glob"
---

# gwark Docs

Create, edit, and manage Google Docs with section-aware operations, themes, and AI review.

## Create

```bash
# From markdown file
gwark docs create "Q4 Report" --file report.md --theme professional --open

# From stdin (pipe from Claude Code or any tool)
echo "# Meeting Notes\n- Item 1\n- Item 2" | gwark docs create "Notes" -f -

# Claude Code pipeline
claude "Write a project brief as markdown" | gwark docs create "Brief" -f - --open

# From template (copies existing doc)
gwark docs create "New Report" --template TEMPLATE_DOC_ID

# Into specific folder
gwark docs create "Report" --file report.md --folder FOLDER_ID
```

### Themes

Apply consistent formatting on creation or after:

```bash
gwark docs theme --list                          # Available themes
gwark docs theme --show professional             # Preview theme
gwark docs theme --apply professional --doc DOC_ID
gwark docs create "Report" --file r.md --theme evolution7
```

Built-in: `professional`, `report`, `proposal`, `minimal`, `academic`. Custom themes go in `.gwark/themes/<name>.yaml`.

For theme YAML spec, see [references/themes.md](references/themes.md).

## Read & Export

```bash
gwark docs get DOC_ID --format markdown          # Export as markdown
gwark docs get DOC_ID --format json              # Full API structure
gwark docs get DOC_ID --format text              # Plain text
gwark docs list                                  # List all docs
gwark docs list --query "report" --format json   # Filter by name
```

## Section-Aware Editing

View structure first, then edit by section name:

```bash
# 1. View document structure (heading hierarchy with indices)
gwark docs sections DOC_ID
gwark docs sections DOC_ID --format tree         # Tree view

# 2. Append content at end
gwark docs edit DOC_ID --append "## New Section\nContent here"

# 3. Insert after a specific heading
echo "New content" | gwark docs edit DOC_ID --insert-after "Introduction" -f -

# 4. Move a section
gwark docs edit DOC_ID --move-section "Conclusion" --before "References"
gwark docs edit DOC_ID --move-section "Tesla" --after "Albanese"

# 5. Delete a section
gwark docs edit DOC_ID --delete-section "Draft Notes" --confirm

# 6. Preview without applying
gwark docs edit DOC_ID --append "## Test" --dry-run
```

### Edit Options

| Option | Purpose |
|--------|---------|
| `--append` | Add content at document end |
| `--prepend` | Add content at start |
| `--replace "old::new"` | Global text replacement |
| `--insert-after "Heading"` | Insert after named section |
| `--move-section "Heading"` | Move section (use with `--before`/`--after`) |
| `--delete-section "Heading"` | Remove section by heading |
| `--dry-run` | Preview changes |
| `--confirm` | Require confirmation |
| `--highlight` | Yellow background on inserted content |
| `--comment "note"` | Add file comment explaining edit |
| `--keep-revision` | Mark as permanent revision |

For complex editing patterns, see [references/editing-patterns.md](references/editing-patterns.md).

## Comments

```bash
gwark docs comment DOC_ID --list                 # List all comments
gwark docs comment DOC_ID --text "Please review" # Add file-level comment
gwark docs comment DOC_ID --reply COMMENT_ID --text "Done"
gwark docs comment DOC_ID --resolve COMMENT_ID
gwark docs comment DOC_ID --unresolve COMMENT_ID
```

**Note:** gwark can only create file-level comments. Anchored comments (on specific text) must be created in Google Docs UI.

## AI Editorial Review

Three-step workflow for AI-assisted document editing:

```bash
# 1. Add editorial comments in Google Docs UI:
#    Select text, add comment like:
#    "gwark: make this more concise"
#    "gwark: rewrite in active voice"

# 2. Generate AI suggestions (posts as comment replies)
gwark docs review DOC_ID

# 3. In Google Docs, reply "accept" to approve suggestions

# 4. Apply approved changes
gwark docs apply DOC_ID --dry-run                # Preview first
gwark docs apply DOC_ID                          # Apply changes
```

**Supported instructions:** make concise, active voice, clarify, fix grammar, suggest wording, expand, simplify.

**Approval keywords:** reply "accept", "approved", "yes", "apply", "ok", or "confirm".

## Summarize

```bash
gwark docs summarize DOC_ID                      # AI summary
gwark docs summarize DOC_ID | claude "Key takeaways as bullets"
```

## Pipe Patterns

| From | To | Pattern |
|------|----|---------|
| claude | docs | `claude "Write brief" \| gwark docs create "Brief" -f -` |
| docs | claude | `gwark docs get DOC_ID -f markdown \| claude "Summarize"` |
| email | docs | `gwark email search -d example.com -f markdown -o r.md && gwark docs create "Report" -f r.md` |
| docs | sheets | `gwark docs get DOC_ID -f text -o content.txt` |

## Gotchas

- Section names in `--insert-after` and `--delete-section` must match heading text exactly.
- `--dry-run` before any destructive edit (`--delete-section`, `--move-section`).
- Theme application doesn't change existing content formatting — only new content.
- All commands accept document ID or full Google Docs URL.
- `--highlight` adds yellow background — useful for collaborators to see changes.
