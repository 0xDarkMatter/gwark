---
name: gwark-forms
description: "Google Forms operations with gwark: create surveys, add questions, export responses. Use when: creating forms, adding questions, analyzing responses, building quizzes. Triggers: google forms, survey, form responses, create form, add question, quiz, form results."
version: 1.0.0
tool: gwark
category: domain
requires:
  bins: ["gwark"]
allowed-tools: "Read Bash Grep Glob"
---

# gwark Forms

Create forms, add questions, and export responses.

## List Forms

```bash
gwark forms list                                 # All forms
gwark forms list --format json                   # JSON output
```

## Get Form Structure

```bash
gwark forms get FORM_ID                          # Show all questions
gwark forms get FORM_ID --format json            # Full API structure
```

## Export Responses

```bash
gwark forms responses FORM_ID                    # Markdown table
gwark forms responses FORM_ID --format csv       # CSV export
gwark forms responses FORM_ID --format json      # JSON array
gwark forms responses FORM_ID -f csv -o results.csv
```

## Create Form

```bash
gwark forms create "Feedback Survey" --description "Customer feedback"
gwark forms create "Q4 Quiz" --description "Team knowledge check" --quiz
```

`--quiz` enables quiz mode with scoring.

## Add Questions

```bash
# Text input
gwark forms add-question FORM_ID --title "Your name" --type text --required

# Paragraph (long text)
gwark forms add-question FORM_ID --title "Describe your experience" --type paragraph

# Multiple choice
gwark forms add-question FORM_ID --title "Rating" \
  --type choice --choices "Excellent,Good,Fair,Poor" --required

# Checkboxes (multi-select)
gwark forms add-question FORM_ID --title "Select all that apply" \
  --type checkbox --choices "Speed,Quality,Price,Support"

# Dropdown
gwark forms add-question FORM_ID --title "Department" \
  --type dropdown --choices "Engineering,Sales,Marketing,HR"

# Linear scale (1-10)
gwark forms add-question FORM_ID --title "How likely to recommend?" \
  --type scale --low 1 --high 10

# Date picker
gwark forms add-question FORM_ID --title "Preferred date" --type date

# Time picker
gwark forms add-question FORM_ID --title "Preferred time" --type time
```

### Question Types

| Type | Use Case | Extra Options |
|------|----------|---------------|
| `text` | Short answer | `--required` |
| `paragraph` | Long answer | `--required` |
| `choice` | Single select | `--choices "A,B,C"` |
| `checkbox` | Multi select | `--choices "A,B,C"` |
| `dropdown` | Single select (compact) | `--choices "A,B,C"` |
| `scale` | Rating scale | `--low N --high N` |
| `date` | Date picker | |
| `time` | Time picker | |

## Pipe Patterns

| From | To | Pattern |
|------|----|---------|
| forms responses | sheets | `gwark forms responses FORM_ID -f csv -o r.csv && gwark sheets write ID -f r.csv` |
| forms responses | docs | `gwark forms responses FORM_ID -f markdown -o r.md && gwark docs create "Results" -f r.md` |

## Gotchas

- **Forms API has no list endpoint.** `gwark forms list` uses Drive API to find forms.
- **Form ID or URL accepted.** Both work for all commands.
- **Quiz mode** must be set at creation. Can't convert a regular form to quiz later.
- **Responses are read-only.** gwark can export but not modify responses.
- **`--choices` is comma-separated.** Use quotes if choices contain special characters.
