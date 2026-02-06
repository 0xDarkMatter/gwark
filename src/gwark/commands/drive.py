"""Drive commands for gwark CLI."""

import sys
from datetime import datetime
from pathlib import Path
from typing import Optional

import typer
from rich.console import Console

# Add project root for imports
project_root = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(project_root))

from gwark.core.config import load_config, get_profile
from gwark.core.constants import EXIT_ERROR
from gwark.core.output import (
    OutputFormatter,
    print_success,
    print_info,
    print_error,
    print_header,
)
from gwark.core.async_utils import retry_execute

console = Console()
app = typer.Typer(no_args_is_help=True)


# File type mapping
FILE_TYPE_MAP = {
    "application/vnd.google-apps.document": "Google Doc",
    "application/vnd.google-apps.spreadsheet": "Google Sheet",
    "application/vnd.google-apps.presentation": "Google Slides",
    "application/vnd.google-apps.form": "Google Form",
    "application/vnd.google-apps.folder": "Folder",
    "application/pdf": "PDF",
    "image/jpeg": "Image",
    "image/png": "Image",
    "application/zip": "Archive",
}


@app.command()
def activity(
    year: int = typer.Option(datetime.now().year, "--year", "-y", help="Year to search"),
    month: int = typer.Option(datetime.now().month, "--month", "-m", help="Month to search"),
    include_shared: bool = typer.Option(True, "--include-shared", help="Include shared drives"),
    owned_only: bool = typer.Option(False, "--owned-only", help="Only files you own"),
    output_format: str = typer.Option("markdown", "--format", "-f", help="Output format: json, markdown"),
    interactive: bool = typer.Option(False, "--interactive", "-i", help="Launch interactive viewer"),
    profile: Optional[str] = typer.Option(None, "--profile", "-p", help="Use named profile"),
    output: Optional[Path] = typer.Option(None, "--output", "-o", help="Output file path"),
) -> None:
    """Extract Google Drive file activity for a specific month."""
    config = load_config()

    if profile:
        prof = get_profile(profile)
        include_shared = prof.filters.get("drive", {}).get("include_shared_drives", include_shared)
        owned_only = prof.filters.get("drive", {}).get("owned_only", owned_only)

    print_header("gwark drive activity")
    print_info(f"Fetching activity for {year}-{month:02d}")

    try:
        from gmail_mcp.auth import get_drive_service

        service = get_drive_service()

        # Calculate date range
        start_date = datetime(year, month, 1)
        if month == 12:
            end_date = datetime(year + 1, 1, 1)
        else:
            end_date = datetime(year, month + 1, 1)

        # Build query
        query_parts = [
            f"modifiedTime >= '{start_date.isoformat()}Z'",
            f"modifiedTime < '{end_date.isoformat()}Z'",
            "trashed = false",
        ]

        if owned_only:
            query_parts.append("'me' in owners")

        query = " and ".join(query_parts)
        print_info(f"Query: {query[:80]}...")

        # Fetch files
        files_data = []
        page_token = None

        while True:
            results = retry_execute(
                service.files().list(
                    q=query,
                    pageSize=100,
                    fields="nextPageToken, files(id, name, mimeType, modifiedTime, owners, parents, webViewLink)",
                    includeItemsFromAllDrives=include_shared,
                    supportsAllDrives=include_shared,
                    pageToken=page_token,
                ),
                operation="List Drive files",
            )

            files = results.get("files", [])
            files_data.extend(files)

            page_token = results.get("nextPageToken")
            if not page_token:
                break

        print_info(f"Found {len(files_data)} files")

        # Process files
        processed_files = []
        for file in files_data:
            file_type = FILE_TYPE_MAP.get(file.get("mimeType", ""), file.get("mimeType", "Unknown"))
            owners = file.get("owners", [])
            owner_email = owners[0].get("emailAddress", "Unknown") if owners else "Unknown"

            processed_files.append({
                "id": file.get("id"),
                "name": file.get("name", "Untitled"),
                "type": file_type,
                "mimeType": file.get("mimeType"),
                "modifiedTime": file.get("modifiedTime", ""),
                "owner": owner_email,
                "link": file.get("webViewLink", ""),
            })

        # Sort by modified time (newest first)
        processed_files.sort(key=lambda x: x.get("modifiedTime", ""), reverse=True)

        print_success(f"Processed {len(processed_files)} files")

        # Format output
        formatter = OutputFormatter(output_dir=config.defaults.output_directory)

        if output_format == "json":
            content = formatter.to_json(processed_files)
            ext = "json"
        else:
            content = _format_drive_markdown(processed_files, year, month)
            ext = "md"

        prefix = f"drive_activity_{year}{month:02d}"
        output_path = formatter.save(content, prefix, ext, output)
        print_success(f"Saved to: {output_path}")

        # Launch interactive viewer
        if interactive and processed_files:
            from gwark.ui.viewer import view_files
            view_files(processed_files, title=f"Drive Activity: {year}-{month:02d}")

    except ImportError as e:
        print_error(f"Missing dependency: {e}")
        print_info("Run: pip install -e . and ensure OAuth is configured")
        raise typer.Exit(EXIT_ERROR)
    except Exception as e:
        print_error(f"Failed: {e}")
        raise typer.Exit(EXIT_ERROR)


def _format_drive_markdown(files: list, year: int, month: int) -> str:
    """Format drive activity as markdown."""
    lines = []
    lines.append(f"# Google Drive Activity - {year}-{month:02d}\n")
    lines.append(f"*Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}*\n")
    lines.append(f"*Total: {len(files)} files modified*\n")

    # Group by type
    by_type = {}
    for f in files:
        t = f.get("type", "Unknown")
        by_type[t] = by_type.get(t, 0) + 1

    lines.append("## Summary by Type\n")
    for t, count in sorted(by_type.items(), key=lambda x: x[1], reverse=True):
        lines.append(f"- {t}: {count}")
    lines.append("")

    lines.append("## Files\n")
    lines.append("| Modified | Type | Name | Owner |")
    lines.append("|----------|------|------|-------|")

    for file in files:
        try:
            mod_time = datetime.fromisoformat(file["modifiedTime"].replace("Z", "+00:00"))
            date_str = mod_time.strftime("%d/%m/%Y %H:%M")
        except Exception:
            date_str = file.get("modifiedTime", "")[:16]

        file_type = file.get("type", "Unknown")
        name = file.get("name", "Untitled").replace("|", "\\|")[:40]
        owner = file.get("owner", "").split("@")[0]

        lines.append(f"| {date_str} | {file_type} | {name} | {owner} |")

    return "\n".join(lines)
