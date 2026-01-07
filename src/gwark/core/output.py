"""Output formatting utilities for gwark."""

import csv
import json
from datetime import datetime
from io import StringIO
from pathlib import Path
from typing import Any, List, Optional

from rich.console import Console
from rich.table import Table

console = Console()


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

    def to_json(self, data: Any, indent: int = 2) -> str:
        """Convert data to JSON string.

        Args:
            data: Data to serialize
            indent: JSON indentation

        Returns:
            JSON string
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
        """Print a rich table to console.

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


def print_success(message: str) -> None:
    """Print a success message."""
    console.print(f"[green][OK][/green] {message}")


def print_info(message: str) -> None:
    """Print an info message."""
    console.print(f"[blue][INFO][/blue] {message}")


def print_warning(message: str) -> None:
    """Print a warning message."""
    console.print(f"[yellow][WARN][/yellow] {message}")


def print_error(message: str) -> None:
    """Print an error message."""
    console.print(f"[red][ERROR][/red] {message}")


def print_header(title: str) -> None:
    """Print a section header."""
    console.print()
    console.rule(f"[bold]{title}[/bold]")
    console.print()
