---
name: gwark-slides
description: "Google Slides operations with gwark: create, edit, export presentations. Use when: creating presentations from markdown, adding slides, exporting to PDF/markdown, editing slide content. Triggers: google slides, presentation, create slides, export slides, add slide, slide deck."
version: 1.0.0
category: productivity
requires:
  bins: ["gwark"]
allowed-tools: "Read Bash Grep Glob"
---

# gwark Slides

Create, edit, and export Google Slides presentations.

## List & Browse

```bash
gwark slides list                                # All presentations (recent first)
gwark slides list -i                             # Interactive browser
gwark slides get PRES_ID                         # Structure as markdown
gwark slides get PRES_ID -f json                 # Full JSON structure
gwark slides get PRES_ID -i                      # Interactive viewer
```

### Interactive Viewer

| Key | Action |
|-----|--------|
| Up/Down | Navigate slides |
| `n` | Toggle speaker notes |
| `o` | Open in Google Slides |
| `g/G` | Go to top/bottom |
| `q` | Quit |

## Create

```bash
# Empty presentation
gwark slides create "My Deck" --open

# From markdown file
gwark slides create "Q1 Review" --file slides.md

# From template (copies existing presentation)
gwark slides create "Report" --template TEMPLATE_ID

# Pipe from Claude Code
claude "Create Q1 planning outline as markdown slides" | gwark slides create "Q1 Plan" -f -
```

### Markdown Format

Slides separated by `---`. Speaker notes under `## Speaker Notes`:

```markdown
# Slide Title
- Bullet point 1
- Bullet point 2

## Speaker Notes
Hidden notes for presenter.

---

# Next Slide
More content here.

---

# Final Slide
- Key takeaway 1
- Key takeaway 2
```

## Add Slides

```bash
gwark slides add-slide PRES_ID --title "New Slide"
gwark slides add-slide PRES_ID --layout BLANK --position 2
```

## Edit

```bash
# Delete a slide (by position, 1-indexed)
gwark slides edit PRES_ID --delete-slide 3

# Move slide (from:to)
gwark slides edit PRES_ID --move-slide "5:2"

# Replace text across all slides
gwark slides edit PRES_ID --replace "2024::2025"
```

## Export

```bash
gwark slides export PRES_ID -f markdown -o presentation.md
gwark slides export PRES_ID -f json
```

**Note:** PDF export requires the Drive API scope (not just Slides). Use `gwark drive` or export from Google Slides UI.

## Pipe Patterns

| From | To | Pattern |
|------|----|---------|
| claude | slides | `claude "Write deck as markdown" \| gwark slides create "Deck" -f -` |
| slides | markdown | `gwark slides export PRES_ID -f markdown -o deck.md` |

## Gotchas

- **Accepts ID or URL.** Both presentation ID and full Google Slides URL work.
- **Markdown is simplified.** Only headings, bullet lists, and speaker notes. No images or complex formatting.
- **`--replace` uses `old::new` syntax.** Double colon separates old and new text.
- **Slide positions are 1-indexed.** First slide is position 1.
- **Template cloning** uses the Drive API copy endpoint internally.
