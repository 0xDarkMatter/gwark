"""Sheets commands for gwark CLI.

Google Sheets operations using gspread for a clean, Pythonic API.
"""

import csv
import io
import json
import sys
from pathlib import Path
from typing import Optional

import typer
from rich.console import Console
from rich.table import Table

# Add project root for imports
project_root = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(project_root))

from gwark.core.config import load_config
from gwark.core.constants import EXIT_ERROR, EXIT_VALIDATION
from gwark.core.output import (
    OutputFormatter,
    print_success,
    print_info,
    print_error,
    print_header,
    print_warning,
)

console = Console()
app = typer.Typer(no_args_is_help=True)


def _get_client():
    """Get SheetsClient with error handling."""
    try:
        from gwark.core.sheets_client import SheetsClient
        return SheetsClient.from_gwark_auth()
    except Exception as e:
        print_error(f"Failed to authenticate: {e}")
        print_info("Ensure OAuth is configured: gwark config auth setup")
        raise typer.Exit(EXIT_ERROR)


def _format_sheets_list_markdown(sheets: list) -> str:
    """Format spreadsheet list as markdown table."""
    lines = [
        "# Google Spreadsheets",
        "",
        f"Found {len(sheets)} spreadsheets.",
        "",
        "| Title | ID | Modified |",
        "|-------|-----|----------|",
    ]

    for s in sheets:
        title = s.get("name", "Untitled")[:40]
        sheet_id = s.get("id", "")[:12] + "..."
        modified = s.get("modifiedTime", "")[:10]
        lines.append(f"| {title} | {sheet_id} | {modified} |")

    return "\n".join(lines)


def _format_metadata_markdown(meta: dict) -> str:
    """Format spreadsheet metadata as markdown."""
    lines = [
        f"# {meta.get('title', 'Untitled')}",
        "",
        "## Metadata",
        "",
        f"- **ID**: `{meta.get('id')}`",
        f"- **URL**: {meta.get('url')}",
        f"- **Locale**: {meta.get('locale')}",
        f"- **Timezone**: {meta.get('timeZone')}",
        "",
        "## Worksheets",
        "",
        "| Title | Rows | Cols | Index |",
        "|-------|------|------|-------|",
    ]

    for ws in meta.get("sheets", []):
        lines.append(
            f"| {ws['title']} | {ws['rowCount']} | {ws['colCount']} | {ws['index']} |"
        )

    return "\n".join(lines)


def _format_data_markdown(data: list, title: str = "Data") -> str:
    """Format sheet data as markdown table."""
    if not data:
        return f"# {title}\n\nNo data found."

    lines = [f"# {title}", "", f"{len(data)} rows.", ""]

    # Use first row as header
    if len(data) > 0:
        header = data[0]
        lines.append("| " + " | ".join(str(h) for h in header) + " |")
        lines.append("| " + " | ".join("---" for _ in header) + " |")

        for row in data[1:]:
            # Pad row to match header length
            padded = row + [""] * (len(header) - len(row))
            lines.append("| " + " | ".join(str(c)[:30] for c in padded) + " |")

    return "\n".join(lines)


def _data_to_csv(data: list) -> str:
    """Convert data to CSV string."""
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerows(data)
    return output.getvalue()


# =============================================================================
# COMMANDS
# =============================================================================


@app.command("list")
def list_sheets(
    max_results: int = typer.Option(50, "--max-results", "-n", help="Maximum results"),
    query: Optional[str] = typer.Option(None, "--query", "-q", help="Filter by name"),
    output_format: str = typer.Option(
        "markdown", "--format", "-f", help="Output format: json, markdown, csv"
    ),
    output: Optional[Path] = typer.Option(None, "--output", "-o", help="Output file"),
    interactive: bool = typer.Option(False, "--interactive", "-i", help="Interactive mode"),
) -> None:
    """List Google Spreadsheets."""
    config = load_config()

    print_header("gwark sheets list")
    print_info("Fetching spreadsheets...")

    client = _get_client()

    try:
        sheets = client.list_spreadsheets(max_results=max_results, query=query)
        print_info(f"Found {len(sheets)} spreadsheets")

        if not sheets:
            print_warning("No spreadsheets found")
            return

        # Interactive mode
        if interactive:
            _interactive_sheets_list(sheets)
            return

        # Format output
        formatter = OutputFormatter(output_dir=config.defaults.output_directory)

        if output_format == "json":
            content = formatter.to_json(sheets)
            ext = "json"
        elif output_format == "csv":
            # Convert to CSV
            rows = [["id", "name", "modifiedTime"]]
            for s in sheets:
                rows.append([s.get("id"), s.get("name"), s.get("modifiedTime", "")])
            content = _data_to_csv(rows)
            ext = "csv"
        else:
            content = _format_sheets_list_markdown(sheets)
            ext = "md"

        prefix = "sheets_list"
        output_path = formatter.save(content, prefix, ext, output)
        print_success(f"Saved to: {output_path}")

    except Exception as e:
        print_error(f"Failed: {e}")
        raise typer.Exit(EXIT_ERROR)


@app.command("get")
def get_sheet(
    sheet_id: str = typer.Argument(..., help="Spreadsheet ID or URL"),
    output_format: str = typer.Option(
        "markdown", "--format", "-f", help="Output format: json, markdown"
    ),
    output: Optional[Path] = typer.Option(None, "--output", "-o", help="Output file"),
) -> None:
    """Get spreadsheet metadata and worksheet list."""
    config = load_config()

    print_header("gwark sheets get")
    print_info(f"Fetching spreadsheet...")

    client = _get_client()

    try:
        meta = client.get_spreadsheet_metadata(sheet_id)
        print_success(f"Retrieved: {meta.get('title')}")
        print_info(f"Worksheets: {len(meta.get('sheets', []))}")

        # Format output
        formatter = OutputFormatter(output_dir=config.defaults.output_directory)

        if output_format == "json":
            content = formatter.to_json(meta)
            ext = "json"
        else:
            content = _format_metadata_markdown(meta)
            ext = "md"

        # Use sheet title for filename
        safe_title = "".join(c if c.isalnum() else "_" for c in meta.get("title", "sheet")[:30])
        prefix = f"sheet_{safe_title}"
        output_path = formatter.save(content, prefix, ext, output)
        print_success(f"Saved to: {output_path}")

    except PermissionError:
        print_error("Permission denied. Check that:")
        print_info("  1. Google Sheets API is enabled in your Cloud project")
        print_info("  2. You have access to this spreadsheet")
        print_info("  Enable at: https://console.cloud.google.com/apis/library/sheets.googleapis.com")
        raise typer.Exit(EXIT_ERROR)
    except Exception as e:
        print_error(f"Failed: {e}")
        raise typer.Exit(EXIT_ERROR)


@app.command("read")
def read_sheet(
    sheet_id: str = typer.Argument(..., help="Spreadsheet ID or URL"),
    range: str = typer.Option(
        "Sheet1", "--range", "-r", help="Range in A1 notation (e.g., Sheet1!A1:D10)"
    ),
    sheet_name: Optional[str] = typer.Option(
        None, "--sheet", "-s", help="Worksheet name (alternative to range)"
    ),
    output_format: str = typer.Option(
        "csv", "--format", "-f", help="Output format: json, csv, markdown"
    ),
    as_records: bool = typer.Option(
        False, "--records", help="JSON as list of dicts (header as keys)"
    ),
    output: Optional[Path] = typer.Option(None, "--output", "-o", help="Output file"),
    interactive: bool = typer.Option(False, "--interactive", "-i", help="Interactive mode"),
) -> None:
    """Read data from a spreadsheet.

    Examples:
        gwark sheets read SHEET_ID
        gwark sheets read SHEET_ID -r "Sheet1!A1:D10"
        gwark sheets read SHEET_ID -s "Sales Data" -f json
        gwark sheets read SHEET_ID --records -f json
    """
    config = load_config()

    print_header("gwark sheets read")

    # Determine range
    if sheet_name:
        range = f"{sheet_name}!A:ZZ"
    elif "!" not in range:
        # Check if it's a cell range (contains : and starts with letter) vs sheet name
        import re
        if re.match(r'^[A-Za-z]+\d*:[A-Za-z]+\d*$', range):
            # It's a cell range like "A1:E5" or "A:E", prepend default sheet
            range = f"Sheet1!{range}"
        else:
            # Just a sheet name provided, read all
            range = f"{range}!A:ZZ"

    print_info(f"Reading range: {range}")

    client = _get_client()

    try:
        data = client.read_range(sheet_id, range)
        print_info(f"Read {len(data)} rows")

        if not data:
            print_warning("No data found in range")
            return

        # Interactive mode
        if interactive:
            _interactive_data_view(data, range)
            return

        # Format output
        formatter = OutputFormatter(output_dir=config.defaults.output_directory)

        if output_format == "json":
            if as_records and len(data) > 1:
                # Convert to list of dicts
                headers = data[0]
                records = []
                for row in data[1:]:
                    record = {}
                    for i, header in enumerate(headers):
                        record[header] = row[i] if i < len(row) else ""
                    records.append(record)
                content = formatter.to_json(records)
            else:
                content = formatter.to_json(data)
            ext = "json"
        elif output_format == "csv":
            content = _data_to_csv(data)
            ext = "csv"
        else:
            content = _format_data_markdown(data, title=range)
            ext = "md"

        # Generate filename from range
        safe_range = "".join(c if c.isalnum() else "_" for c in range[:20])
        prefix = f"sheet_data_{safe_range}"
        output_path = formatter.save(content, prefix, ext, output)
        print_success(f"Saved to: {output_path}")

    except PermissionError:
        print_error("Permission denied. Check that:")
        print_info("  1. Google Sheets API is enabled in your Cloud project")
        print_info("  2. You have access to this spreadsheet")
        print_info("  Enable at: https://console.cloud.google.com/apis/library/sheets.googleapis.com")
        raise typer.Exit(EXIT_ERROR)
    except Exception as e:
        print_error(f"Failed: {e}")
        raise typer.Exit(EXIT_ERROR)


@app.command("write")
def write_sheet(
    sheet_id: str = typer.Argument(..., help="Spreadsheet ID or URL"),
    file: Optional[Path] = typer.Option(
        None, "--file", "-f", help="Input file (CSV/JSON) or '-' for stdin"
    ),
    range: str = typer.Option(
        "Sheet1!A1", "--range", "-r", help="Starting cell in A1 notation"
    ),
    input_mode: str = typer.Option(
        "USER_ENTERED", "--input-mode", "-m",
        help="Input mode: USER_ENTERED (parse formulas) or RAW"
    ),
    dry_run: bool = typer.Option(False, "--dry-run", help="Preview without writing"),
) -> None:
    """Write data to a spreadsheet from file or stdin.

    Examples:
        gwark sheets write SHEET_ID -f data.csv
        gwark sheets write SHEET_ID -f data.json -r "Sheet2!A1"
        cat data.csv | gwark sheets write SHEET_ID -f -
        echo "A,B,C\\n1,2,3" | gwark sheets write SHEET_ID -f -
    """
    print_header("gwark sheets write")

    # Read input data
    if file is None:
        print_error("Input file required. Use -f <file> or -f - for stdin")
        raise typer.Exit(EXIT_VALIDATION)

    try:
        if str(file) == "-":
            # Read from stdin
            import sys as _sys
            content = _sys.stdin.read()
            print_info("Reading from stdin...")
        else:
            if not file.exists():
                print_error(f"File not found: {file}")
                raise typer.Exit(EXIT_VALIDATION)
            content = file.read_text()
            print_info(f"Reading from: {file}")

        # Parse content (auto-detect CSV or JSON)
        data = _parse_input_data(content)
        print_info(f"Parsed {len(data)} rows")

        if not data:
            print_warning("No data to write")
            return

        if dry_run:
            print_info("[DRY RUN] Would write:")
            for i, row in enumerate(data[:5]):
                console.print(f"  Row {i+1}: {row[:5]}{'...' if len(row) > 5 else ''}")
            if len(data) > 5:
                console.print(f"  ... and {len(data) - 5} more rows")
            return

        client = _get_client()
        result = client.write_range(sheet_id, data, range, value_input_option=input_mode)

        print_success(f"Wrote {len(data)} rows to {range}")

    except PermissionError:
        print_error("Permission denied. Enable Sheets API and check access.")
        raise typer.Exit(EXIT_ERROR)
    except Exception as e:
        print_error(f"Failed: {e}")
        raise typer.Exit(EXIT_ERROR)


@app.command("create")
def create_sheet(
    title: str = typer.Argument(..., help="Title for new spreadsheet"),
    folder: Optional[str] = typer.Option(None, "--folder", help="Drive folder ID"),
    open_browser: bool = typer.Option(False, "--open", "-o", help="Open in browser"),
) -> None:
    """Create a new spreadsheet.

    Examples:
        gwark sheets create "Q1 Report"
        gwark sheets create "Sales Data" --open
    """
    print_header("gwark sheets create")
    print_info(f"Creating spreadsheet: {title}")

    client = _get_client()

    try:
        spreadsheet = client.create_spreadsheet(title, folder_id=folder)

        print_success(f"Created: {spreadsheet.title}")
        print_info(f"ID: {spreadsheet.id}")
        print_info(f"URL: {spreadsheet.url}")

        if open_browser:
            import webbrowser
            webbrowser.open(spreadsheet.url)
            print_info("Opened in browser")

    except Exception as e:
        print_error(f"Failed: {e}")
        raise typer.Exit(EXIT_ERROR)


@app.command("append")
def append_sheet(
    sheet_id: str = typer.Argument(..., help="Spreadsheet ID or URL"),
    file: Optional[Path] = typer.Option(
        None, "--file", "-f", help="Input file (CSV/JSON) or '-' for stdin"
    ),
    sheet_name: str = typer.Option("Sheet1", "--sheet", "-s", help="Worksheet name"),
    dry_run: bool = typer.Option(False, "--dry-run", help="Preview without appending"),
) -> None:
    """Append rows to a spreadsheet.

    Examples:
        gwark sheets append SHEET_ID -f newdata.csv
        gwark sheets append SHEET_ID -f data.json -s "Sales"
        echo "A,B,C" | gwark sheets append SHEET_ID -f -
    """
    print_header("gwark sheets append")

    if file is None:
        print_error("Input file required. Use -f <file> or -f - for stdin")
        raise typer.Exit(EXIT_VALIDATION)

    try:
        if str(file) == "-":
            import sys as _sys
            content = _sys.stdin.read()
            print_info("Reading from stdin...")
        else:
            if not file.exists():
                print_error(f"File not found: {file}")
                raise typer.Exit(EXIT_VALIDATION)
            content = file.read_text()
            print_info(f"Reading from: {file}")

        data = _parse_input_data(content)
        print_info(f"Parsed {len(data)} rows to append")

        if not data:
            print_warning("No data to append")
            return

        if dry_run:
            print_info("[DRY RUN] Would append:")
            for i, row in enumerate(data[:5]):
                console.print(f"  Row {i+1}: {row[:5]}{'...' if len(row) > 5 else ''}")
            if len(data) > 5:
                console.print(f"  ... and {len(data) - 5} more rows")
            return

        client = _get_client()
        result = client.append_rows(sheet_id, data, sheet_name=sheet_name)

        print_success(f"Appended {len(data)} rows to {sheet_name}")

    except PermissionError:
        print_error("Permission denied. Enable Sheets API and check access.")
        raise typer.Exit(EXIT_ERROR)
    except Exception as e:
        print_error(f"Failed: {e}")
        raise typer.Exit(EXIT_ERROR)


@app.command("clear")
def clear_sheet(
    sheet_id: str = typer.Argument(..., help="Spreadsheet ID or URL"),
    range: str = typer.Argument(..., help="Range to clear in A1 notation"),
    confirm: bool = typer.Option(False, "--confirm", "-y", help="Skip confirmation"),
) -> None:
    """Clear cells in a range.

    Examples:
        gwark sheets clear SHEET_ID "Sheet1!A1:D10" --confirm
        gwark sheets clear SHEET_ID "Sheet1!A:Z" -y
    """
    print_header("gwark sheets clear")
    print_warning(f"Will clear range: {range}")

    if not confirm:
        try:
            response = console.input("[yellow]Type 'yes' to confirm: [/yellow]").strip()
            if response.lower() != "yes":
                print_info("Cancelled")
                return
        except (KeyboardInterrupt, EOFError):
            print_info("Cancelled")
            return

    client = _get_client()

    try:
        client.clear_range(sheet_id, range)
        print_success(f"Cleared: {range}")

    except PermissionError:
        print_error("Permission denied. Enable Sheets API and check access.")
        raise typer.Exit(EXIT_ERROR)
    except Exception as e:
        print_error(f"Failed: {e}")
        raise typer.Exit(EXIT_ERROR)


@app.command("export")
def export_sheet(
    sheet_id: str = typer.Argument(..., help="Spreadsheet ID or URL"),
    output_format: str = typer.Option(
        "csv", "--format", "-f", help="Export format: csv, json"
    ),
    sheet_name: str = typer.Option("Sheet1", "--sheet", "-s", help="Worksheet name"),
    as_records: bool = typer.Option(
        True, "--records/--raw", help="JSON as records (header as keys) or raw arrays"
    ),
    output: Optional[Path] = typer.Option(None, "--output", "-o", help="Output file"),
) -> None:
    """Export spreadsheet data.

    Examples:
        gwark sheets export SHEET_ID
        gwark sheets export SHEET_ID -f json -s "Sales"
        gwark sheets export SHEET_ID -f csv -o data.csv
    """
    config = load_config()

    print_header("gwark sheets export")
    print_info(f"Exporting {sheet_name}...")

    client = _get_client()

    try:
        if output_format == "json":
            data = client.export_json(sheet_id, sheet_name, as_records=as_records)
            content = json.dumps(data, indent=2, default=str)
            ext = "json"
        else:  # csv
            content = client.export_csv(sheet_id, sheet_name)
            ext = "csv"

        # Save output
        formatter = OutputFormatter(output_dir=config.defaults.output_directory)
        safe_name = "".join(c if c.isalnum() else "_" for c in sheet_name[:20])
        prefix = f"export_{safe_name}"
        output_path = formatter.save(content, prefix, ext, output)

        print_success(f"Exported to: {output_path}")

    except PermissionError:
        print_error("Permission denied. Enable Sheets API and check access.")
        raise typer.Exit(EXIT_ERROR)
    except Exception as e:
        print_error(f"Failed: {e}")
        raise typer.Exit(EXIT_ERROR)


@app.command("resize")
def resize_columns(
    sheet_id: str = typer.Argument(..., help="Spreadsheet ID or URL"),
    sheet_name: str = typer.Option("Sheet1", "--sheet", "-s", help="Worksheet name"),
    widths: Optional[str] = typer.Option(None, "--widths", "-w", help="Column widths in pixels (comma-separated)"),
    auto: bool = typer.Option(False, "--auto", "-a", help="Auto-resize to fit content"),
    total_width: Optional[int] = typer.Option(None, "--total", "-t", help="Distribute width evenly across columns"),
    columns: int = typer.Option(5, "--columns", "-c", help="Number of columns (for --total)"),
) -> None:
    """Resize columns in a worksheet.

    Examples:
        gwark sheets resize SHEET_ID -s "Pivot" -w "120,150,140,200,90"
        gwark sheets resize SHEET_ID -s "Data" --auto
        gwark sheets resize SHEET_ID -s "Report" --total 800 --columns 5
    """
    print_header("gwark sheets resize")

    client = _get_client()

    try:
        if auto:
            print_info(f"Auto-resizing columns in {sheet_name}...")
            client.auto_resize_columns(sheet_id, sheet_name)
            print_success("Columns auto-resized to fit content")

        elif widths:
            width_list = [int(w.strip()) for w in widths.split(",")]
            total = sum(width_list)
            print_info(f"Setting {len(width_list)} column widths: {width_list}")
            print_info(f"Total width: {total}px")
            client.set_column_widths(sheet_id, sheet_name, width_list)
            print_success(f"Column widths updated ({total}px total)")

        elif total_width:
            # Distribute evenly
            per_col = total_width // columns
            width_list = [per_col] * columns
            print_info(f"Distributing {total_width}px across {columns} columns ({per_col}px each)")
            client.set_column_widths(sheet_id, sheet_name, width_list)
            print_success(f"Column widths set to {per_col}px each")

        else:
            print_error("Specify --widths, --auto, or --total")
            raise typer.Exit(EXIT_VALIDATION)

    except Exception as e:
        print_error(f"Failed: {e}")
        raise typer.Exit(EXIT_ERROR)


# Display type mapping: short names -> API enum values
_DISPLAY_MAP = {
    "pct-row": "PERCENT_OF_ROW_TOTAL",
    "pct-col": "PERCENT_OF_COLUMN_TOTAL",
    "pct-total": "PERCENT_OF_GRAND_TOTAL",
}

# Date grouping mapping: friendly names -> API enum values
_DATE_GROUP_MAP = {
    "year": "YEAR",
    "quarter": "QUARTER",
    "month": "MONTH",
    "year_month": "YEAR_MONTH",
    "year_quarter": "YEAR_QUARTER",
    "year_month_day": "YEAR_MONTH_DAY",
    "day_of_week": "DAY_OF_WEEK",
    "day_of_month": "DAY_OF_MONTH",
    "day_of_year": "DAY_OF_YEAR",
    "hour": "HOUR_OF_DAY",
}


def _normalize_sort(val: str) -> str:
    """Normalize sort direction shorthand to API enum."""
    val = val.upper()
    if val in ("DESC", "DESCENDING"):
        return "DESCENDING"
    return "ASCENDING"


def _parse_fields_with_sort(raw: str) -> tuple:
    """Parse comma-separated fields with optional :asc/:desc suffix.

    Returns (field_names, sort_orders_dict).
    """
    fields = []
    sort_orders = {}
    for part in raw.split(","):
        part = part.strip()
        if not part:
            continue
        # Check for trailing :asc or :desc (case-insensitive)
        lower = part.lower()
        if lower.endswith(":desc") or lower.endswith(":descending"):
            name = part[:part.rfind(":")].strip()
            fields.append(name)
            sort_orders[name] = "DESCENDING"
        elif lower.endswith(":asc") or lower.endswith(":ascending"):
            name = part[:part.rfind(":")].strip()
            fields.append(name)
            sort_orders[name] = "ASCENDING"
        else:
            fields.append(part)
    return fields, sort_orders


@app.command("pivot")
def pivot_table(
    sheet_id: str = typer.Argument(..., help="Spreadsheet ID or URL"),
    source: str = typer.Option(..., "--source", "-s", help="Source range (e.g., Sheet1!A1:D100)"),
    target: str = typer.Option("Sheet1!F1", "--target", "-t", help="Target cell for pivot"),
    rows: str = typer.Option(..., "--rows", "-r", help="Row fields (name or name:asc/desc, comma-separated)"),
    cols: Optional[str] = typer.Option(None, "--cols", "-c", help="Column fields (name or name:asc/desc)"),
    values: str = typer.Option(..., "--values", "-v", help="Value fields (func:field, e.g., sum:Sales,avg:Profit)"),
    sort_by: Optional[str] = typer.Option(None, "--sort-by", help="Sort rows by value (func:field from --values)"),
    filter_spec: Optional[str] = typer.Option(None, "--filter", help="Filter source data (Field:val1;val2, comma-separated)"),
    display: Optional[str] = typer.Option(None, "--display", help="Value display: pct-row, pct-col, pct-total"),
    layout: Optional[str] = typer.Option(None, "--layout", help="Value layout: horizontal or vertical"),
    no_totals: bool = typer.Option(False, "--no-totals", help="Hide subtotals"),
    date_group: Optional[str] = typer.Option(None, "--date-group", help="Date grouping (Field:type, e.g., Date:year_month)"),
    limit: Optional[int] = typer.Option(None, "--limit", help="Max rows/columns in pivot groups"),
) -> None:
    """Create a pivot table from source data.

    Aggregation functions: SUM, COUNT, AVERAGE, MAX, MIN, COUNTUNIQUE, MEDIAN, STDEV

    Examples:
        gwark sheets pivot ID -s "Data!A1:E100" -r "Category" -v "sum:Sales"
        gwark sheets pivot ID -s "Data!A:D" -r "Region:desc" -v "sum:Sales" --sort-by "sum:Sales"
        gwark sheets pivot ID -s "Data!A:E" -r "Category" -v "sum:Sales" --filter "Region:East;West"
        gwark sheets pivot ID -s "Data!A:E" -r "Category" -v "sum:Sales" --display pct-row
        gwark sheets pivot ID -s "Data!A:E" -r "Category" -v "sum:Sales,avg:Profit" --layout vertical
        gwark sheets pivot ID -s "Data!A:E" -r "Category" -v "sum:Sales" --no-totals --limit 10
        gwark sheets pivot ID -s "Data!A:E" -r "Date" -v "sum:Sales" --date-group "Date:year_month"
    """
    print_header("gwark sheets pivot")
    print_info(f"Source: {source}")
    print_info(f"Target: {target}")

    # Parse row fields with optional sort direction
    row_fields, row_sort_orders = _parse_fields_with_sort(rows)
    print_info(f"Row groupings: {', '.join(row_fields)}")

    # Parse column fields with optional sort direction
    col_fields = None
    col_sort_orders = {}
    if cols:
        col_fields, col_sort_orders = _parse_fields_with_sort(cols)
        print_info(f"Column groupings: {', '.join(col_fields)}")

    # Parse value fields (format: func:field)
    value_specs = []
    for v in values.split(","):
        v = v.strip()
        if ":" in v:
            func, field = v.split(":", 1)
            value_specs.append({"field": field.strip(), "function": func.strip().upper()})
        else:
            value_specs.append({"field": v, "function": "SUM"})

    value_strs = [f"{v['function']}({v['field']})" for v in value_specs]
    print_info(f"Values: {', '.join(value_strs)}")

    # Parse --sort-by: match against value_specs
    sort_by_value_idx = None
    if sort_by:
        sort_by_lower = sort_by.strip().lower()
        for idx, vs in enumerate(value_specs):
            candidate = f"{vs['function'].lower()}:{vs['field'].lower()}"
            if sort_by_lower == candidate or sort_by_lower == vs["field"].lower():
                sort_by_value_idx = idx
                break
        if sort_by_value_idx is None:
            print_error(f"--sort-by '{sort_by}' does not match any --values entry")
            available = ", ".join(f"{v['function'].lower()}:{v['field']}" for v in value_specs)
            print_info(f"Available: {available}")
            raise typer.Exit(EXIT_VALIDATION)
        print_info(f"Sort by: {value_strs[sort_by_value_idx]}")

    # Parse --filter
    filters = None
    if filter_spec:
        filters = {}
        for part in filter_spec.split(","):
            part = part.strip()
            if ":" not in part:
                print_error(f"Invalid filter format: '{part}' (expected Field:val1;val2)")
                raise typer.Exit(EXIT_VALIDATION)
            field, vals = part.split(":", 1)
            filters[field.strip()] = [v.strip() for v in vals.split(";")]
        for f, vs in filters.items():
            print_info(f"Filter: {f} = {', '.join(vs)}")

    # Parse --display
    value_display = None
    if display:
        value_display = _DISPLAY_MAP.get(display.lower())
        if not value_display:
            print_error(f"Invalid --display: '{display}'")
            print_info(f"Options: {', '.join(_DISPLAY_MAP.keys())}")
            raise typer.Exit(EXIT_VALIDATION)
        print_info(f"Display: {display}")

    # Parse --layout
    value_layout = None
    if layout:
        layout_upper = layout.upper()
        if layout_upper not in ("HORIZONTAL", "VERTICAL"):
            print_error(f"Invalid --layout: '{layout}'. Use: horizontal, vertical")
            raise typer.Exit(EXIT_VALIDATION)
        value_layout = layout_upper
        print_info(f"Layout: {layout}")

    # Parse --date-group
    date_groups = None
    if date_group:
        date_groups = {}
        for part in date_group.split(","):
            part = part.strip()
            if ":" not in part:
                print_error(f"Invalid --date-group: '{part}' (expected Field:type)")
                raise typer.Exit(EXIT_VALIDATION)
            field, dtype = part.split(":", 1)
            mapped = _DATE_GROUP_MAP.get(dtype.strip().lower())
            if not mapped:
                print_error(f"Unknown date group type: '{dtype}'")
                print_info(f"Options: {', '.join(_DATE_GROUP_MAP.keys())}")
                raise typer.Exit(EXIT_VALIDATION)
            date_groups[field.strip()] = mapped
        for f, d in date_groups.items():
            print_info(f"Date group: {f} by {d}")

    if no_totals:
        print_info("Subtotals: hidden")
    if limit:
        print_info(f"Group limit: {limit}")

    client = _get_client()

    try:
        result = client.create_pivot_table(
            sheet_id=sheet_id,
            source_range=source,
            target_cell=target,
            rows=row_fields,
            columns=col_fields,
            values=value_specs,
            row_sort_orders=row_sort_orders or None,
            col_sort_orders=col_sort_orders or None,
            sort_by_value=sort_by_value_idx,
            filters=filters,
            value_display=value_display,
            value_layout=value_layout,
            show_totals=not no_totals,
            date_groups=date_groups,
            group_limit=limit,
        )

        print_success(f"Created pivot table at {target}")
        print_info("Refresh the spreadsheet to see the pivot table")

    except PermissionError:
        print_error("Permission denied. Enable Sheets API and check access.")
        raise typer.Exit(EXIT_ERROR)
    except Exception as e:
        print_error(f"Failed: {e}")
        raise typer.Exit(EXIT_ERROR)


# =============================================================================
# HELPERS
# =============================================================================


def _parse_input_data(content: str) -> list:
    """Parse input content as CSV or JSON."""
    content = content.strip()

    # Try JSON first
    if content.startswith("[") or content.startswith("{"):
        try:
            data = json.loads(content)
            # If list of dicts, convert to list of lists
            if isinstance(data, list) and len(data) > 0 and isinstance(data[0], dict):
                headers = list(data[0].keys())
                rows = [headers]
                for item in data:
                    rows.append([item.get(h, "") for h in headers])
                return rows
            # If already list of lists, return as-is
            if isinstance(data, list):
                return data
        except json.JSONDecodeError:
            pass

    # Fall back to CSV
    reader = csv.reader(io.StringIO(content))
    return list(reader)


# =============================================================================
# INTERACTIVE MODE (BASIC)
# =============================================================================


def _interactive_sheets_list(sheets: list) -> None:
    """Simple interactive list of spreadsheets."""
    import webbrowser

    console.print("\n[bold]Spreadsheets[/bold] (press number to open, q to quit)\n")

    # Show numbered list
    for i, s in enumerate(sheets[:20], 1):
        title = s.get("name", "Untitled")[:50]
        modified = s.get("modifiedTime", "")[:10]
        console.print(f"  [cyan]{i:2}[/cyan]. {title} [dim]({modified})[/dim]")

    console.print("\n[dim]Enter number to open in browser, or 'q' to quit[/dim]")

    while True:
        try:
            choice = console.input("\n> ").strip().lower()
            if choice == "q":
                break
            num = int(choice)
            if 1 <= num <= len(sheets):
                sheet = sheets[num - 1]
                url = f"https://docs.google.com/spreadsheets/d/{sheet['id']}/edit"
                console.print(f"[green]Opening:[/green] {sheet['name']}")
                webbrowser.open(url)
            else:
                console.print("[yellow]Invalid number[/yellow]")
        except ValueError:
            console.print("[yellow]Enter a number or 'q'[/yellow]")
        except (KeyboardInterrupt, EOFError):
            break


def _interactive_data_view(data: list, title: str = "Data", sheet_url: str = "") -> None:
    """Interactive spreadsheet grid viewer."""
    if not data:
        console.print("[yellow]No data to display[/yellow]")
        return

    from gwark.ui.viewer import view_spreadsheet
    view_spreadsheet(data, title=title, sheet_url=sheet_url)
