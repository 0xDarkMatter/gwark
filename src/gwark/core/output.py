"""Output formatting utilities for gwark - Fabric Protocol compliant."""

import csv
import json
import sys
from datetime import datetime
from io import StringIO
from pathlib import Path
from typing import Any, Dict, List, Optional

from rich.console import Console
from rich.table import Table

# Stream separation per Fabric Protocol:
# - stdout: JSON data, formatted results (machine-readable)
# - stderr: progress, warnings, errors, headers (human-readable)
console = Console(stderr=True)  # Human-readable output to stderr
console_data = Console()  # Data output to stdout


def output_json(data: Any) -> None:
    """Print JSON to stdout only (for piping)."""
    print(json.dumps(data, indent=2, default=str))


def output_list(
    data: List[Any],
    meta: Optional[Dict[str, Any]] = None,
    as_json: bool = False,
) -> None:
    """Output a list with Fabric Protocol wrapper.

    Args:
        data: List of items to output
        meta: Optional metadata (count auto-calculated if not provided)
        as_json: If True, output JSON to stdout
    """
    if as_json:
        result = {
            "data": data,
            "meta": meta or {
                "count": len(data),
                "timestamp": datetime.now().isoformat(),
            },
        }
        output_json(result)


def output_item(data: Dict[str, Any], as_json: bool = False) -> None:
    """Output a single item with Fabric Protocol wrapper.

    Args:
        data: Item to output
        as_json: If True, output JSON to stdout
    """
    if as_json:
        output_json({"data": data})


def output_error(
    message: str,
    code: str = "ERROR",
    details: Optional[Dict[str, Any]] = None,
    as_json: bool = False,
    exit_code: int = 1,
) -> None:
    """Output an error in Fabric Protocol format.

    Args:
        message: Error message
        code: Error code (e.g., "AUTH_REQUIRED", "NOT_FOUND")
        details: Additional error details
        as_json: If True, output JSON to stdout
        exit_code: Exit code to use
    """
    if as_json:
        error_obj = {
            "error": {
                "code": code,
                "message": message,
            }
        }
        if details:
            error_obj["error"]["details"] = details
        output_json(error_obj)
    else:
        print_error(message)

    raise SystemExit(exit_code)


class OutputFormatter:
    """Handles formatting and saving output in various formats."""

    def __init__(self, output_dir: Path = Path("./reports")):
        """Initialize formatter.

        Args:
            output_dir: Directory for saving output files
        """
        self.output_dir = output_dir
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def generate_filename(self, prefix: str, extension: str) -> Path:
        """Generate a timestamped filename.

        Args:
            prefix: Filename prefix
            extension: File extension (without dot)

        Returns:
            Full path to output file
        """
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        return self.output_dir / f"{prefix}_{timestamp}.{extension}"

    def to_json(
        self,
        data: Any,
        meta: Optional[Dict[str, Any]] = None,
        indent: int = 2,
    ) -> str:
        """Convert data to JSON string with Fabric Protocol wrapper.

        Args:
            data: Data to serialize
            meta: Optional metadata
            indent: JSON indentation

        Returns:
            JSON string with {data, meta} wrapper
        """
        wrapper = {
            "data": data,
            "meta": meta or {
                "count": len(data) if isinstance(data, list) else 1,
                "timestamp": datetime.now().isoformat(),
            },
        }
        return json.dumps(wrapper, indent=indent, default=str)

    def to_json_raw(self, data: Any, indent: int = 2) -> str:
        """Convert data to raw JSON string (no wrapper).

        Args:
            data: Data to serialize
            indent: JSON indentation

        Returns:
            JSON string (raw, no wrapper)
        """
        return json.dumps(data, indent=indent, default=str)

    def to_csv(self, data: List[dict], columns: Optional[List[str]] = None) -> str:
        """Convert list of dicts to CSV string.

        Args:
            data: List of dictionaries
            columns: Column names (auto-detected if None)

        Returns:
            CSV string
        """
        if not data:
            return ""

        if columns is None:
            columns = list(data[0].keys())

        output = StringIO()
        writer = csv.DictWriter(output, fieldnames=columns, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(data)
        return output.getvalue()

    def to_markdown_table(
        self,
        data: List[dict],
        columns: List[tuple],  # List of (key, header) tuples
        escape_pipes: bool = True,
    ) -> str:
        """Convert data to markdown table.

        Args:
            data: List of dictionaries
            columns: List of (key, header_name) tuples
            escape_pipes: Whether to escape | in values

        Returns:
            Markdown table string
        """
        if not data:
            return ""

        def escape(value: Any) -> str:
            """Escape value for markdown table."""
            s = str(value) if value is not None else ""
            if escape_pipes:
                s = s.replace("|", "\\|")
            return s

        # Build header
        header = "| " + " | ".join(h for _, h in columns) + " |"
        separator = "|" + "|".join("-" * (len(h) + 2) for _, h in columns) + "|"

        # Build rows
        rows = []
        for item in data:
            row_values = [escape(item.get(key, "")) for key, _ in columns]
            rows.append("| " + " | ".join(row_values) + " |")

        return "\n".join([header, separator] + rows)

    def save(
        self,
        content: str,
        prefix: str,
        extension: str,
        output_path: Optional[Path] = None,
    ) -> Path:
        """Save content to file.

        Args:
            content: Content to save
            prefix: Filename prefix
            extension: File extension
            output_path: Explicit output path (optional)

        Returns:
            Path where file was saved
        """
        if output_path is None:
            output_path = self.generate_filename(prefix, extension)

        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(content, encoding="utf-8")
        return output_path

    def print_table(
        self,
        data: List[dict],
        columns: List[tuple],
        title: Optional[str] = None,
    ) -> None:
        """Print a rich table to console (stderr for human readability).

        Args:
            data: List of dictionaries
            columns: List of (key, header_name) tuples
            title: Optional table title
        """
        table = Table(title=title, show_header=True, header_style="bold")

        for _, header in columns:
            table.add_column(header)

        for item in data:
            row = [str(item.get(key, "")) for key, _ in columns]
            table.add_row(*row)

        console.print(table)


# Human-readable output functions (all go to stderr)
def print_success(message: str) -> None:
    """Print a success message to stderr."""
    console.print(f"[green][OK][/green] {message}")


def print_info(message: str) -> None:
    """Print an info message to stderr."""
    console.print(f"[blue][INFO][/blue] {message}")


def print_warning(message: str) -> None:
    """Print a warning message to stderr."""
    console.print(f"[yellow][WARN][/yellow] {message}")


def print_error(message: str) -> None:
    """Print an error message to stderr."""
    console.print(f"[red][ERROR][/red] {message}")


def print_header(title: str) -> None:
    """Print a section header to stderr."""
    console.print()
    console.rule(f"[bold]{title}[/bold]")
    console.print()
