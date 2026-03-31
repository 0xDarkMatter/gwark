# Document Editing Patterns

Complex section editing examples for gwark docs.

## Insert After Section

```bash
# View structure first
gwark docs sections DOC_ID
# Output:
# | # | Heading | Level | Start | End |
# | 1 | Introduction | H1 | 3 | 45 |
# | 2 | Background | H2 | 46 | 120 |
# | 3 | Analysis | H2 | 121 | 200 |

# Insert after "Background"
echo "## New Findings\nContent here" | gwark docs edit DOC_ID --insert-after "Background" -f -

# From file
gwark docs edit DOC_ID --insert-after "Introduction" --file new_section.md
```

## Move Sections

```bash
# Move "Conclusion" before "References"
gwark docs edit DOC_ID --move-section "Conclusion" --before "References"

# Move "Tesla" after "Albanese"
gwark docs edit DOC_ID --move-section "Tesla" --after "Albanese"
```

**Note:** Move extracts paragraph styles and re-applies them. Content formatting is preserved.

## Delete Sections

```bash
# Preview first
gwark docs edit DOC_ID --delete-section "Draft Notes" --dry-run

# Delete with confirmation prompt
gwark docs edit DOC_ID --delete-section "Draft Notes" --confirm
```

## Collaboration Visibility

Make edits visible to collaborators:

```bash
# Highlight inserted content (yellow background)
gwark docs edit DOC_ID --insert-after "Summary" --file update.md --highlight

# Add comment explaining the edit
gwark docs edit DOC_ID --append "## Q4 Update" --comment "Added Q4 section per review feedback"

# Mark revision as permanent
gwark docs edit DOC_ID --insert-after "Summary" --file update.md --keep-revision
```

## Editorial Review Workflow

```bash
# Step 1: In Google Docs UI, add comments like:
#   "gwark: make this more concise"
#   "gwark: rewrite in active voice"
#   "gwark: fact-check this claim"

# Step 2: Generate AI suggestions
gwark docs review DOC_ID

# Step 3: In Google Docs, reply "accept" to suggestions you approve

# Step 4: Apply approved changes
gwark docs apply DOC_ID --dry-run    # Preview
gwark docs apply DOC_ID              # Apply

# Supported instructions:
# - make concise, active voice, clarify, fix grammar
# - suggest wording, expand, simplify
# Approval keywords: accept, approved, yes, apply, ok, confirm
```

## Global Text Replacement

```bash
# Replace text throughout document
gwark docs edit DOC_ID --replace "2024::2025"    # old::new format
gwark docs edit DOC_ID --replace "FY24::FY25"
```

## Batch Operations

```bash
# Create + populate in one pipeline
claude "Write Q4 analysis as markdown" | gwark docs create "Q4 Analysis" -f - --theme professional --open

# Export → edit → re-import
gwark docs get DOC_ID -f markdown -o draft.md
# ... edit draft.md locally ...
gwark docs edit DOC_ID --file draft.md
```
