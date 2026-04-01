---
name: gwark-sheets
description: "Google Sheets operations with gwark via gspread: read, write, pivot tables, export. Use when: reading spreadsheet data, writing CSV/JSON, creating pivot tables, exporting sheets, interactive grid. Triggers: google sheets, spreadsheet, read sheet, write data, pivot table, export csv, sheet data, gspread."
version: 1.0.0
category: productivity
requires:
  bins: ["gwark"]
allowed-tools: "Read Bash Grep Glob"
---

# gwark Sheets

Read, write, and analyze Google Sheets data. Uses gspread under the hood.

## List & Browse

```bash
gwark sheets list                                # All spreadsheets (recent first)
gwark sheets list -i                             # Interactive browser
gwark sheets get SHEET_ID                        # Metadata + worksheet list
```

## Read Data

```bash
# Entire first sheet
gwark sheets read SHEET_ID

# Specific range (A1 notation)
gwark sheets read SHEET_ID -r "A1:D10"

# By sheet name
gwark sheets read SHEET_ID -s "Sales Data"

# Interactive grid viewer
gwark sheets read SHEET_ID -i

# Export formats
gwark sheets read SHEET_ID -f json               # JSON array
gwark sheets read SHEET_ID -f csv -o data.csv    # CSV file
```

### A1 Notation

| Pattern | Meaning |
|---------|---------|
| `A1:D10` | Rectangle from A1 to D10 |
| `A:D` | Full columns A through D |
| `1:5` | Full rows 1 through 5 |
| `Sheet1!A1:D10` | Specific sheet + range |
| `'Sheet Name'!A:Z` | Sheet name with spaces (quote it) |

### Interactive Grid

| Key | Action |
|-----|--------|
| Arrow keys | Navigate cells |
| `Enter` | View cell detail (full content, formula) |
| `Tab` | Next worksheet |
| `o` | Open in Google Sheets |
| `q` | Quit |

## Write Data

```bash
# From CSV file
gwark sheets write SHEET_ID -f data.csv

# From stdin
echo "Name,Score\nAlice,95\nBob,87" | gwark sheets write SHEET_ID -f -

# To specific sheet
gwark sheets write SHEET_ID -f data.csv -s "Import"
```

**Input formats:** CSV and JSON auto-detected.

## Create

```bash
gwark sheets create "Q1 Report" --open           # Opens in browser
```

## Append Rows

```bash
# Append from file
gwark sheets append SHEET_ID -f new_rows.csv

# Append from stdin
cat updates.csv | gwark sheets append SHEET_ID -f -
```

## Clear

```bash
gwark sheets clear SHEET_ID "Sheet1!A10:D20" --confirm
```

## Export

```bash
gwark sheets export SHEET_ID --format csv
gwark sheets export SHEET_ID --sheet "Summary" -o summary.csv
```

## Pivot Tables

Create pivot tables with auto-styling (Roboto font, blue headers, gray totals):

```bash
# Basic: group by Category, sum Sales
gwark sheets pivot SHEET_ID -s "Data!A1:E100" -r "Category" -v "sum:Sales"

# Multi-row grouping with column pivot
gwark sheets pivot SHEET_ID -s "Sales!A:D" \
  -r "Region,Product" -c "Month" -v "sum:Revenue,avg:Profit"

# Target a specific cell
gwark sheets pivot SHEET_ID -s "Data!A:E" -r "Team" -v "count:ID" -t "Sheet2!A1"
```

### Pivot Options

| Option | Purpose | Example |
|--------|---------|---------|
| `-s/--source` | Source data range | `Data!A1:E100` |
| `-t/--target` | Where to place pivot | `Sheet1!F1` (default) |
| `-r/--rows` | Row groupings | `Category,Region` |
| `-c/--cols` | Column groupings | `Month` |
| `-v/--values` | Aggregations | `sum:Sales,avg:Profit` |

### Aggregation Functions

`SUM`, `COUNT`, `AVERAGE`, `MAX`, `MIN`, `COUNTUNIQUE`, `MEDIAN`, `STDEV`

Syntax: `function:ColumnName` (e.g., `sum:Revenue`, `avg:Score`, `count:ID`)

## Column Resize

```bash
# Manual widths (comma-separated pixels)
gwark sheets resize SHEET_ID -s "Pivot" -w "130,160,150,420,100"

# Auto-fit content
gwark sheets resize SHEET_ID -s "Data" --auto
```

## Pipe Patterns

| From | To | Pattern |
|------|----|---------|
| email | sheets | `gwark email senders -d example.com -f csv -o s.csv && gwark sheets write ID -f s.csv` |
| forms | sheets | `gwark forms responses FORM_ID -f csv -o r.csv && gwark sheets write ID -f r.csv` |
| sheets | docs | `gwark sheets export ID -f csv -o data.csv` |
| stdin | sheets | `echo "A,B\n1,2" \| gwark sheets write ID -f -` |

## Gotchas

- **Accepts ID or URL.** Both spreadsheet ID and full Google Sheets URL work.
- **gspread auth** uses its own token (`sheets_token.pickle`). First use triggers browser OAuth.
- **A1 notation requires sheet name** for multi-sheet spreadsheets: `'Sales Data'!A:D`.
- **Clear requires `--confirm`.** No `--dry-run` — confirm is the safety net.
- **Pivot auto-styling** is on by default. Creates Roboto-styled headers and totals.
- **Rate limits apply.** gspread makes multiple API calls per operation. Large writes may hit quotas.
