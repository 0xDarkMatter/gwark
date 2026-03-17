"""Drive commands for gwark CLI."""

import re
import sys
import webbrowser
from collections import deque
from datetime import datetime
from pathlib import Path
from typing import Optional, Any, Dict, List

import typer
from rich.console import Console

# Add project root for imports
project_root = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(project_root))

from gwark.core.config import load_config, get_profile
from gwark.core.constants import EXIT_ERROR, EXIT_NOT_FOUND, EXIT_VALIDATION
from gwark.core.output import (
    OutputFormatter,
    print_success,
    print_info,
    print_error,
    print_header,
    print_warning,
)
from gwark.core.async_utils import retry_execute

console = Console()
app = typer.Typer(no_args_is_help=True)

# Sub-app for share subcommands
share_app = typer.Typer(no_args_is_help=True, help="Manage file/folder sharing permissions")
app.add_typer(share_app, name="share")


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
    "image/gif": "Image",
    "image/webp": "Image",
    "application/zip": "Archive",
}

# User-friendly type aliases -> Drive MIME types
TYPE_ALIASES = {
    "sheets": ["application/vnd.google-apps.spreadsheet"],
    "docs": ["application/vnd.google-apps.document"],
    "slides": ["application/vnd.google-apps.presentation"],
    "forms": ["application/vnd.google-apps.form"],
    "pdf": ["application/pdf"],
    "images": ["image/jpeg", "image/png", "image/gif", "image/webp"],
    "folders": ["application/vnd.google-apps.folder"],
}

FOLDER_MIME = "application/vnd.google-apps.folder"

# Fields requested from Drive API for file listings
_LS_FIELDS = "nextPageToken, files(id, name, mimeType, size, modifiedTime, owners, webViewLink)"


def _extract_file_id(value: str) -> Optional[str]:
    """Extract a Drive file/folder ID from a URL or raw ID.

    Supports:
    - https://drive.google.com/drive/folders/ID
    - https://drive.google.com/drive/u/0/folders/ID
    - https://drive.google.com/file/d/ID/...
    - https://docs.google.com/document/d/ID/...
    - https://docs.google.com/spreadsheets/d/ID/...
    - https://docs.google.com/presentation/d/ID/...
    - Raw ID (15+ alphanumeric with - and _)

    Returns None for plain names (contain spaces or are short).
    """
    # Folder URL
    m = re.search(r"drive\.google\.com/drive(?:/u/\d+)?/folders/([a-zA-Z0-9_-]+)", value)
    if m:
        return m.group(1)

    # File URL: /file/d/ID or /document/d/ID or /spreadsheets/d/ID or /presentation/d/ID
    m = re.search(r"(?:file|document|spreadsheets|presentation)/d/([a-zA-Z0-9_-]+)", value)
    if m:
        return m.group(1)

    # Raw ID heuristic: alphanumeric with - and _, no spaces, 15+ chars.
    # Real Drive IDs are mostly alphanumeric with occasional - and _.
    # Reject strings that look like human names (contain only lowercase + dashes).
    if re.fullmatch(r"[a-zA-Z0-9_-]{15,}", value):
        # If it contains at least one uppercase or digit, likely an ID
        if re.search(r"[A-Z0-9]", value):
            return value

    return None


def _extract_folder_id(value: str) -> Optional[str]:
    """Extract a Drive folder ID from a URL or raw ID. Delegates to _extract_file_id."""
    return _extract_file_id(value)


def _escape_query(value: str) -> str:
    """Escape a string for use in Drive API query."""
    return value.replace("\\", "\\\\").replace("'", "\\'")


def _resolve_file(
    service: Any,
    name: str,
    mime_filter: Optional[str] = None,
) -> List[dict]:
    """Find Drive files matching the given name.

    Args:
        service: Authenticated Drive API service
        name: File name to search for
        mime_filter: Optional MIME type to filter by

    Returns:
        List of matching file dicts with id, name, mimeType, parents, owners, webViewLink.
    """
    query = f"name = '{_escape_query(name)}' and trashed = false"
    if mime_filter:
        query += f" and mimeType = '{mime_filter}'"

    results = retry_execute(
        service.files().list(
            q=query,
            pageSize=20,
            fields="files(id, name, mimeType, parents, owners, webViewLink)",
            includeItemsFromAllDrives=True,
            supportsAllDrives=True,
        ),
        operation="Search for file",
    )
    return results.get("files", [])


def _resolve_target(
    service: Any,
    value: str,
    require_folder: bool = False,
) -> Dict[str, Any]:
    """Resolve a file/folder from a URL, ID, or name.

    Tries ID/URL extraction first, then falls back to name search.
    Prints disambiguation if multiple matches found.

    Args:
        service: Authenticated Drive API service
        value: URL, file ID, or file name
        require_folder: If True, only match folders

    Returns:
        File metadata dict with id, name, mimeType, parents, owners, webViewLink.

    Raises:
        typer.Exit(EXIT_NOT_FOUND) if no match found.
    """
    direct_id = _extract_file_id(value)

    if direct_id:
        try:
            meta = retry_execute(
                service.files().get(
                    fileId=direct_id,
                    fields="id, name, mimeType, parents, owners, webViewLink",
                    supportsAllDrives=True,
                ),
                operation="Get file metadata",
            )
            if require_folder and meta.get("mimeType") != FOLDER_MIME:
                print_error(f"'{meta.get('name', direct_id)}' is not a folder")
                raise typer.Exit(EXIT_VALIDATION)
            return meta
        except typer.Exit:
            raise
        except Exception as e:
            print_error(f"Could not access file ID {direct_id[:20]}: {e}")
            raise typer.Exit(EXIT_NOT_FOUND)

    # Name search
    mime = FOLDER_MIME if require_folder else None
    matches = _resolve_file(service, value, mime_filter=mime)

    if not matches:
        kind = "folder" if require_folder else "file"
        print_error(f"No {kind} found with name: {value}")
        raise typer.Exit(EXIT_NOT_FOUND)

    if len(matches) > 1:
        print_warning(f"Found {len(matches)} items named '{value}':")
        for i, f in enumerate(matches, 1):
            owners = f.get("owners", [])
            owner = owners[0].get("emailAddress", "?") if owners else "?"
            file_type = FILE_TYPE_MAP.get(f.get("mimeType", ""), "File")
            console.print(f"  {i}. [cyan]{f['name']}[/cyan] ({file_type}, owner: {owner})")
        print_info("Using the first match.")

    return matches[0]


def _get_parents(service: Any, file_id: str) -> List[str]:
    """Fetch parent folder IDs for a file."""
    meta = retry_execute(
        service.files().get(
            fileId=file_id,
            fields="parents",
            supportsAllDrives=True,
        ),
        operation="Get file parents",
    )
    return meta.get("parents", [])


def _format_size(size_bytes: Optional[str]) -> str:
    """Format byte count to human-readable size."""
    if not size_bytes:
        return "---"
    try:
        b = int(size_bytes)
    except (ValueError, TypeError):
        return "---"
    for unit in ("B", "KB", "MB", "GB"):
        if b < 1024:
            return f"{b:.0f} {unit}" if unit == "B" else f"{b:.1f} {unit}"
        b /= 1024
    return f"{b:.1f} TB"


def _resolve_folder(service: Any, folder_name: str) -> List[dict]:
    """Find Drive folders matching the given name.

    Returns list of matching folder dicts with id, name, owners.
    """
    query = (
        f"name = '{_escape_query(folder_name)}' "
        f"and mimeType = '{FOLDER_MIME}' and trashed = false"
    )
    results = retry_execute(
        service.files().list(
            q=query,
            pageSize=20,
            fields="files(id, name, owners, parents)",
            includeItemsFromAllDrives=True,
            supportsAllDrives=True,
        ),
        operation="Search for folder",
    )
    return results.get("files", [])


def _build_type_query(type_filter: Optional[str]) -> str:
    """Build MIME type query clause from a type alias.

    Returns empty string if no filter, or a query fragment like:
    "and (mimeType = 'x' or mimeType = 'y')"
    """
    if not type_filter:
        return ""
    mime_types = TYPE_ALIASES.get(type_filter, [])
    if not mime_types:
        return ""
    clauses = " or ".join(f"mimeType = '{m}'" for m in mime_types)
    return f" and ({clauses})"


def _list_folder_files(
    service: Any,
    folder_id: str,
    type_filter: Optional[str] = None,
    recursive: bool = False,
) -> List[dict]:
    """List files in a Drive folder, optionally recursively.

    Args:
        service: Authenticated Drive API service
        folder_id: Google Drive folder ID
        type_filter: Optional type alias (sheets, docs, etc.)
        recursive: Whether to descend into subfolders

    Returns:
        List of processed file dicts
    """
    type_clause = _build_type_query(type_filter)
    files: List[dict] = []

    # BFS queue: (folder_id, path_prefix)
    queue: deque = deque()
    queue.append((folder_id, ""))

    while queue:
        current_id, path_prefix = queue.popleft()

        # When recursive + type filter, we need ALL children (including folders
        # for traversal), so fetch unfiltered and apply type filter to results.
        if recursive and type_filter:
            query = f"'{current_id}' in parents and trashed = false"
        else:
            query = f"'{current_id}' in parents and trashed = false{type_clause}"

        page_token = None
        while True:
            results = retry_execute(
                service.files().list(
                    q=query,
                    pageSize=100,
                    fields=_LS_FIELDS,
                    includeItemsFromAllDrives=True,
                    supportsAllDrives=True,
                    pageToken=page_token,
                ),
                operation="List folder contents",
            )

            for f in results.get("files", []):
                mime = f.get("mimeType", "")
                is_folder = mime == FOLDER_MIME

                # Queue subfolders for recursive traversal
                if recursive and is_folder:
                    child_path = f"{path_prefix}{f['name']}/"
                    queue.append((f["id"], child_path))

                # Apply type filter for recursive+filtered case
                if recursive and type_filter and not is_folder:
                    allowed = TYPE_ALIASES.get(type_filter, [])
                    if mime not in allowed:
                        continue

                file_type = FILE_TYPE_MAP.get(mime, mime.split("/")[-1] if "/" in mime else "Unknown")
                owners = f.get("owners", [])
                owner = owners[0].get("emailAddress", "Unknown") if owners else "Unknown"

                files.append({
                    "id": f.get("id"),
                    "name": f.get("name", "Untitled"),
                    "type": file_type,
                    "mimeType": mime,
                    "size": _format_size(f.get("size")),
                    "modifiedTime": f.get("modifiedTime", ""),
                    "owner": owner,
                    "link": f.get("webViewLink", ""),
                    "path": path_prefix if recursive else "",
                })

            page_token = results.get("nextPageToken")
            if not page_token:
                break

    # Sort by path (for recursive) then name
    if recursive:
        files.sort(key=lambda x: (x.get("path", ""), x.get("name", "")))
    else:
        files.sort(key=lambda x: x.get("name", ""))

    return files


def _format_ls_markdown(files: list, folder_name: str, recursive: bool = False) -> str:
    """Format folder listing as markdown."""
    lines = []
    lines.append(f"# Folder: {folder_name}\n")
    lines.append(f"*Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}*\n")
    lines.append(f"*Total: {len(files)} items*\n")

    # Summary by type
    by_type: dict = {}
    for f in files:
        t = f.get("type", "Unknown")
        by_type[t] = by_type.get(t, 0) + 1

    if by_type:
        lines.append("## Summary\n")
        for t, count in sorted(by_type.items(), key=lambda x: x[1], reverse=True):
            lines.append(f"- {t}: {count}")
        lines.append("")

    # File table
    lines.append("## Files\n")
    if recursive:
        lines.append("| Path | Name | Type | Size | Modified | Owner |")
        lines.append("|------|------|------|------|----------|-------|")
    else:
        lines.append("| Name | Type | Size | Modified | Owner |")
        lines.append("|------|------|------|----------|-------|")

    for f in files:
        try:
            mod_time = datetime.fromisoformat(f["modifiedTime"].replace("Z", "+00:00"))
            date_str = mod_time.strftime("%d/%m/%Y %H:%M")
        except Exception:
            date_str = f.get("modifiedTime", "")[:16]

        name = f.get("name", "Untitled").replace("|", "\\|")
        file_type = f.get("type", "Unknown")
        size = f.get("size", "---")
        owner = f.get("owner", "").split("@")[0]

        if recursive:
            path = f.get("path", "").replace("|", "\\|") or "/"
            lines.append(f"| {path} | {name} | {file_type} | {size} | {date_str} | {owner} |")
        else:
            lines.append(f"| {name} | {file_type} | {size} | {date_str} | {owner} |")

    return "\n".join(lines)


@app.command()
def ls(
    folder_name: str = typer.Argument(..., help="Folder name to list"),
    type_filter: Optional[str] = typer.Option(None, "--type", "-t", help="Filter by type: sheets, docs, slides, forms, pdf, images, folders"),
    recursive: bool = typer.Option(False, "--recursive", "-r", help="List contents recursively"),
    output_format: str = typer.Option("markdown", "--format", "-f", help="Output format: json, markdown, csv"),
    interactive: bool = typer.Option(False, "--interactive", "-i", help="Launch interactive viewer"),
    profile: Optional[str] = typer.Option(None, "--profile", "-p", help="Use named profile"),
    output: Optional[Path] = typer.Option(None, "--output", "-o", help="Output file path"),
) -> None:
    """List files in a Google Drive folder by name.

    Examples:
        gwark drive ls "My Folder"
        gwark drive ls "Project Files" --type sheets
        gwark drive ls "Root Folder" --recursive --type docs
        gwark drive ls "https://drive.google.com/drive/folders/FOLDER_ID"
    """
    print_header("gwark drive ls")

    # Validate type filter
    if type_filter and type_filter not in TYPE_ALIASES:
        print_error(f"Unknown type: {type_filter}")
        print_info(f"Valid types: {', '.join(TYPE_ALIASES.keys())}")
        raise typer.Exit(EXIT_VALIDATION)

    config = load_config()

    try:
        from gmail_mcp.auth import get_drive_service

        service = get_drive_service()

        # Check if input is a URL or ID, otherwise search by name
        direct_id = _extract_file_id(folder_name)

        if direct_id:
            folder_id = direct_id
            # Fetch folder metadata for display name
            try:
                folder_meta = retry_execute(
                    service.files().get(
                        fileId=folder_id,
                        fields="id, name",
                        supportsAllDrives=True,
                    ),
                    operation="Get folder metadata",
                )
                display_name = folder_meta.get("name", folder_name)
            except Exception:
                display_name = folder_id[:20]
            print_info(f"Folder: {display_name} ({folder_id[:12]}...)")
        else:
            # Resolve folder name to ID
            print_info(f"Searching for folder: {folder_name}")
            folders = _resolve_folder(service, folder_name)

            if not folders:
                print_error(f"No folder found with name: {folder_name}")
                raise typer.Exit(EXIT_ERROR)

            if len(folders) > 1:
                print_warning(f"Found {len(folders)} folders named '{folder_name}':")
                for i, f in enumerate(folders, 1):
                    owners = f.get("owners", [])
                    owner = owners[0].get("emailAddress", "?") if owners else "?"
                    console.print(f"  {i}. [cyan]{f['name']}[/cyan] (id: {f['id'][:12]}..., owner: {owner})")
                print_info("Using the first match. Use a more specific folder name if needed.")

            folder = folders[0]
            folder_id = folder["id"]
            display_name = folder["name"]
            print_info(f"Folder: {display_name} ({folder_id[:12]}...)")

        # List contents
        desc = f"{'Recursively listing' if recursive else 'Listing'} contents"
        if type_filter:
            desc += f" (type: {type_filter})"
        print_info(desc)

        files = _list_folder_files(service, folder_id, type_filter, recursive)

        if not files:
            print_info("Folder is empty" + (f" (no {type_filter} files)" if type_filter else ""))
            return

        print_success(f"Found {len(files)} items")

        # Format output
        formatter = OutputFormatter(output_dir=config.defaults.output_directory)

        if output_format == "json":
            content = formatter.to_json(files)
            ext = "json"
        elif output_format == "csv":
            content = formatter.to_csv(files)
            ext = "csv"
        else:
            content = _format_ls_markdown(files, display_name, recursive)
            ext = "md"

        prefix = f"drive_ls_{display_name.replace(' ', '_')[:30]}"
        output_path = formatter.save(content, prefix, ext, output)
        print_success(f"Saved to: {output_path}")

        # Interactive viewer
        if interactive and files:
            from gwark.ui.viewer import view_files
            view_files(files, title=f"Folder: {display_name}")

    except ImportError as e:
        print_error(f"Missing dependency: {e}")
        raise typer.Exit(EXIT_ERROR)
    except typer.Exit:
        raise
    except Exception as e:
        print_error(f"Failed: {e}")
        raise typer.Exit(EXIT_ERROR)


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


# ---------------------------------------------------------------------------
# Phase 2: Non-destructive commands (mkdir, rename, search)
# ---------------------------------------------------------------------------


@app.command()
def mkdir(
    name: str = typer.Argument(..., help="Name for the new folder"),
    parent: str = typer.Option("root", "--parent", "-p", help="Parent folder (name, URL, or ID)"),
    open_browser: bool = typer.Option(False, "--open", help="Open folder in browser after creation"),
) -> None:
    """Create a new folder in Google Drive.

    Examples:
        gwark drive mkdir "Project Files"
        gwark drive mkdir "Sub Folder" --parent "Project Files"
        gwark drive mkdir "Team Docs" --parent "https://drive.google.com/drive/folders/ID" --open
    """
    print_header("gwark drive mkdir")

    try:
        from gmail_mcp.auth import get_drive_service

        service = get_drive_service()

        # Resolve parent
        if parent == "root":
            parent_id = "root"
            print_info(f"Creating folder '{name}' in My Drive root")
        else:
            parent_meta = _resolve_target(service, parent, require_folder=True)
            parent_id = parent_meta["id"]
            print_info(f"Creating folder '{name}' in '{parent_meta.get('name', parent_id)}'")

        result = retry_execute(
            service.files().create(
                body={
                    "name": name,
                    "mimeType": FOLDER_MIME,
                    "parents": [parent_id],
                },
                supportsAllDrives=True,
                fields="id, name, webViewLink",
            ),
            operation="Create folder",
        )

        print_success(f"Created folder: {result['name']}")
        link = result.get("webViewLink", "")
        if link:
            print_info(f"Link: {link}")
            if open_browser:
                webbrowser.open(link)

    except typer.Exit:
        raise
    except Exception as e:
        print_error(f"Failed: {e}")
        raise typer.Exit(EXIT_ERROR)


@app.command()
def rename(
    file: str = typer.Argument(..., help="File or folder to rename (name, URL, or ID)"),
    new_name: str = typer.Argument(..., help="New name"),
    confirm: bool = typer.Option(False, "--confirm", "-c", help="Prompt before renaming"),
) -> None:
    """Rename a file or folder in Google Drive.

    Examples:
        gwark drive rename "Old Name" "New Name"
        gwark drive rename "Report Draft" "Report Final" --confirm
    """
    print_header("gwark drive rename")

    try:
        from gmail_mcp.auth import get_drive_service

        service = get_drive_service()
        meta = _resolve_target(service, file)

        old_name = meta.get("name", "Unknown")
        file_type = FILE_TYPE_MAP.get(meta.get("mimeType", ""), "File")
        print_info(f"{file_type}: '{old_name}' -> '{new_name}'")

        if confirm:
            if not typer.confirm("Apply this rename?"):
                print_info("Cancelled")
                raise typer.Exit(0)

        retry_execute(
            service.files().update(
                fileId=meta["id"],
                body={"name": new_name},
                supportsAllDrives=True,
                fields="id, name",
            ),
            operation="Rename file",
        )

        print_success(f"Renamed: '{old_name}' -> '{new_name}'")

    except typer.Exit:
        raise
    except Exception as e:
        print_error(f"Failed: {e}")
        raise typer.Exit(EXIT_ERROR)


@app.command()
def search(
    query: str = typer.Argument(..., help="Search text (matched against file name and content)"),
    type_filter: Optional[str] = typer.Option(None, "--type", "-t", help="Filter by type: sheets, docs, slides, forms, pdf, images, folders"),
    owner: Optional[str] = typer.Option(None, "--owner", help="Filter by owner email"),
    folder: Optional[str] = typer.Option(None, "--in", help="Search within folder (name, URL, or ID)"),
    trashed: bool = typer.Option(False, "--trashed", help="Include trashed files"),
    limit: int = typer.Option(50, "--limit", "-l", help="Maximum results"),
    output_format: str = typer.Option("markdown", "--format", "-f", help="Output format: json, markdown, csv"),
    interactive: bool = typer.Option(False, "--interactive", "-i", help="Launch interactive viewer"),
    output: Optional[Path] = typer.Option(None, "--output", "-o", help="Output file path"),
) -> None:
    """Search Google Drive with filters.

    Examples:
        gwark drive search "quarterly report"
        gwark drive search "budget" --type sheets --owner user@example.com
        gwark drive search "meeting notes" --in "Team Folder" --limit 20
        gwark drive search "invoice" --type pdf --format json
    """
    print_header("gwark drive search")

    if type_filter and type_filter not in TYPE_ALIASES:
        print_error(f"Unknown type: {type_filter}")
        print_info(f"Valid types: {', '.join(TYPE_ALIASES.keys())}")
        raise typer.Exit(EXIT_VALIDATION)

    config = load_config()

    try:
        from gmail_mcp.auth import get_drive_service

        service = get_drive_service()

        # Build query
        query_parts = [f"fullText contains '{_escape_query(query)}'"]

        if not trashed:
            query_parts.append("trashed = false")

        type_clause = _build_type_query(type_filter)
        if type_clause:
            query_parts.append(type_clause.lstrip(" and "))

        if owner:
            query_parts.append(f"'{_escape_query(owner)}' in owners")

        if folder:
            folder_meta = _resolve_target(service, folder, require_folder=True)
            query_parts.append(f"'{folder_meta['id']}' in parents")
            print_info(f"Searching in: {folder_meta.get('name', folder)}")

        q = " and ".join(query_parts)
        print_info(f"Searching: {query}")

        # Paginated fetch
        files: List[dict] = []
        page_token = None

        while len(files) < limit:
            page_size = min(100, limit - len(files))
            results = retry_execute(
                service.files().list(
                    q=q,
                    pageSize=page_size,
                    fields=_LS_FIELDS,
                    includeItemsFromAllDrives=True,
                    supportsAllDrives=True,
                    pageToken=page_token,
                ),
                operation="Search Drive",
            )

            for f in results.get("files", []):
                mime = f.get("mimeType", "")
                file_type = FILE_TYPE_MAP.get(mime, mime.split("/")[-1] if "/" in mime else "Unknown")
                owners = f.get("owners", [])
                owner_email = owners[0].get("emailAddress", "Unknown") if owners else "Unknown"

                files.append({
                    "id": f.get("id"),
                    "name": f.get("name", "Untitled"),
                    "type": file_type,
                    "mimeType": mime,
                    "size": _format_size(f.get("size")),
                    "modifiedTime": f.get("modifiedTime", ""),
                    "owner": owner_email,
                    "link": f.get("webViewLink", ""),
                })

            page_token = results.get("nextPageToken")
            if not page_token:
                break

        if not files:
            print_info("No files found")
            return

        print_success(f"Found {len(files)} results")

        # Format output
        formatter = OutputFormatter(output_dir=config.defaults.output_directory)

        if output_format == "json":
            content = formatter.to_json(files)
            ext = "json"
        elif output_format == "csv":
            content = formatter.to_csv(files)
            ext = "csv"
        else:
            content = _format_ls_markdown(files, f"Search: {query}")
            ext = "md"

        prefix = f"drive_search_{query.replace(' ', '_')[:20]}"
        output_path = formatter.save(content, prefix, ext, output)
        print_success(f"Saved to: {output_path}")

        if interactive and files:
            from gwark.ui.viewer import view_files
            view_files(files, title=f"Search: {query}")

    except typer.Exit:
        raise
    except Exception as e:
        print_error(f"Failed: {e}")
        raise typer.Exit(EXIT_ERROR)


# ---------------------------------------------------------------------------
# Phase 3: Destructive commands (move, copy, rm)
# ---------------------------------------------------------------------------


def _display_file_preview(files: List[dict], action: str, destination: Optional[str] = None) -> None:
    """Display a preview of files to be affected by a destructive operation."""
    console.print(f"\n[bold]{action}[/bold] — {len(files)} file(s):")
    if destination:
        console.print(f"  Destination: [cyan]{destination}[/cyan]")
    console.print()

    for f in files[:20]:
        file_type = f.get("type", FILE_TYPE_MAP.get(f.get("mimeType", ""), "File"))
        console.print(f"  • {f.get('name', 'Untitled')} ({file_type})")

    if len(files) > 20:
        console.print(f"  ... and {len(files) - 20} more")
    console.print()


@app.command()
def move(
    source: str = typer.Argument(..., help="File/folder to move (name, URL, or ID)"),
    destination: str = typer.Argument(..., help="Destination folder (name, URL, or ID)"),
    type_filter: Optional[str] = typer.Option(None, "--type", "-t", help="Bulk: move matching files from source folder"),
    dry_run: bool = typer.Option(False, "--dry-run", help="Preview without executing"),
    confirm: bool = typer.Option(False, "--confirm", "-c", help="Prompt before executing"),
) -> None:
    """Move files or folders to a new location.

    Supports moving between My Drive and shared drives.

    Examples:
        gwark drive move "Report.docx" "Archive"
        gwark drive move "Budget 2025" "Finance/Q1" --confirm
        gwark drive move "Source Folder" "Dest Folder" --type sheets --dry-run
    """
    print_header("gwark drive move")

    if type_filter and type_filter not in TYPE_ALIASES:
        print_error(f"Unknown type: {type_filter}")
        print_info(f"Valid types: {', '.join(TYPE_ALIASES.keys())}")
        raise typer.Exit(EXIT_VALIDATION)

    try:
        from gmail_mcp.auth import get_drive_service

        service = get_drive_service()

        # Resolve destination (must be folder)
        dest_meta = _resolve_target(service, destination, require_folder=True)
        dest_id = dest_meta["id"]
        dest_name = dest_meta.get("name", destination)

        # Resolve source — single file or folder for bulk
        if type_filter:
            # Bulk mode: source is a folder, move matching files
            source_meta = _resolve_target(service, source, require_folder=True)
            files_to_move = _list_folder_files(service, source_meta["id"], type_filter)
            if not files_to_move:
                print_info(f"No {type_filter} files found in '{source_meta.get('name', source)}'")
                return
        else:
            # Single file/folder
            source_meta = _resolve_target(service, source)
            files_to_move = [{
                "id": source_meta["id"],
                "name": source_meta.get("name", "Unknown"),
                "type": FILE_TYPE_MAP.get(source_meta.get("mimeType", ""), "File"),
                "mimeType": source_meta.get("mimeType", ""),
            }]

        # Preview
        _display_file_preview(files_to_move, "Move", dest_name)
        print_warning("This will remove file(s) from their current location.")

        if dry_run:
            print_info("[DRY RUN] No changes applied")
            return

        if confirm:
            if not typer.confirm("Apply these moves?"):
                print_info("Cancelled")
                raise typer.Exit(0)

        # Execute moves
        moved = 0
        for f in files_to_move:
            try:
                parents = _get_parents(service, f["id"])
                remove_parents = ",".join(parents) if parents else None

                update_kwargs: Dict[str, Any] = {
                    "fileId": f["id"],
                    "addParents": dest_id,
                    "supportsAllDrives": True,
                    "fields": "id, name, parents",
                }
                if remove_parents:
                    update_kwargs["removeParents"] = remove_parents

                retry_execute(
                    service.files().update(**update_kwargs),
                    operation=f"Move '{f['name']}'",
                )
                moved += 1
            except Exception as e:
                print_warning(f"Failed to move '{f['name']}': {e}")

        print_success(f"Moved {moved}/{len(files_to_move)} file(s) to '{dest_name}'")

    except typer.Exit:
        raise
    except Exception as e:
        print_error(f"Failed: {e}")
        raise typer.Exit(EXIT_ERROR)


@app.command()
def copy(
    source: str = typer.Argument(..., help="File or folder to copy (name, URL, or ID)"),
    destination: str = typer.Argument(..., help="Destination folder (name, URL, or ID)"),
    name: Optional[str] = typer.Option(None, "--name", "-n", help="Custom name for the copy"),
    recursive: bool = typer.Option(False, "--recursive", "-r", help="Copy folder contents recursively"),
    dry_run: bool = typer.Option(False, "--dry-run", help="Preview without executing"),
) -> None:
    """Copy files or folders to a new location.

    Examples:
        gwark drive copy "Template" "Projects" --name "Q1 Report"
        gwark drive copy "Shared Templates" "My Folder" --recursive --dry-run
    """
    print_header("gwark drive copy")

    try:
        from gmail_mcp.auth import get_drive_service

        service = get_drive_service()

        # Resolve destination
        dest_meta = _resolve_target(service, destination, require_folder=True)
        dest_id = dest_meta["id"]
        dest_name = dest_meta.get("name", destination)

        # Resolve source
        source_meta = _resolve_target(service, source)
        source_name = source_meta.get("name", "Unknown")
        is_folder = source_meta.get("mimeType") == FOLDER_MIME

        if is_folder and not recursive:
            print_error(f"'{source_name}' is a folder. Use --recursive to copy folder contents.")
            raise typer.Exit(EXIT_VALIDATION)

        if is_folder:
            # Recursive folder copy via BFS
            files = _list_folder_files(service, source_meta["id"], recursive=True)
            print_info(f"Copying folder '{source_name}' ({len(files)} files) to '{dest_name}'")
            print_warning("Recursive copy will duplicate all files and folder structure.")

            if dry_run:
                _display_file_preview(files, "Copy (recursive)", dest_name)
                print_info("[DRY RUN] No changes applied")
                return

            # Create root copy folder
            copy_folder_name = name or f"Copy of {source_name}"
            root_copy = retry_execute(
                service.files().create(
                    body={
                        "name": copy_folder_name,
                        "mimeType": FOLDER_MIME,
                        "parents": [dest_id],
                    },
                    supportsAllDrives=True,
                    fields="id, name",
                ),
                operation="Create copy root folder",
            )

            # BFS: create folder structure then copy files
            folder_map = {source_meta["id"]: root_copy["id"]}
            copied = 0
            bfs_queue: deque = deque()
            bfs_queue.append(source_meta["id"])

            while bfs_queue:
                current_id = bfs_queue.popleft()
                new_parent_id = folder_map[current_id]

                # List direct children
                page_token = None
                while True:
                    results = retry_execute(
                        service.files().list(
                            q=f"'{current_id}' in parents and trashed = false",
                            pageSize=100,
                            fields="nextPageToken, files(id, name, mimeType)",
                            includeItemsFromAllDrives=True,
                            supportsAllDrives=True,
                            pageToken=page_token,
                        ),
                        operation="List folder for copy",
                    )

                    for item in results.get("files", []):
                        if item.get("mimeType") == FOLDER_MIME:
                            new_folder = retry_execute(
                                service.files().create(
                                    body={
                                        "name": item["name"],
                                        "mimeType": FOLDER_MIME,
                                        "parents": [new_parent_id],
                                    },
                                    supportsAllDrives=True,
                                    fields="id, name",
                                ),
                                operation=f"Create subfolder '{item['name']}'",
                            )
                            folder_map[item["id"]] = new_folder["id"]
                            bfs_queue.append(item["id"])
                        else:
                            try:
                                retry_execute(
                                    service.files().copy(
                                        fileId=item["id"],
                                        body={
                                            "name": item["name"],
                                            "parents": [new_parent_id],
                                        },
                                        supportsAllDrives=True,
                                        fields="id",
                                    ),
                                    operation=f"Copy '{item['name']}'",
                                )
                                copied += 1
                            except Exception as e:
                                print_warning(f"Failed to copy '{item['name']}': {e}")

                    page_token = results.get("nextPageToken")
                    if not page_token:
                        break

            print_success(f"Copied {copied} file(s) to '{copy_folder_name}' in '{dest_name}'")

        else:
            # Single file copy
            copy_name = name or f"Copy of {source_name}"
            print_info(f"Copying '{source_name}' to '{dest_name}' as '{copy_name}'")

            if dry_run:
                _display_file_preview(
                    [{"name": source_name, "type": FILE_TYPE_MAP.get(source_meta.get("mimeType", ""), "File")}],
                    "Copy",
                    dest_name,
                )
                print_info("[DRY RUN] No changes applied")
                return

            result = retry_execute(
                service.files().copy(
                    fileId=source_meta["id"],
                    body={
                        "name": copy_name,
                        "parents": [dest_id],
                    },
                    supportsAllDrives=True,
                    fields="id, name, webViewLink",
                ),
                operation="Copy file",
            )

            print_success(f"Copied: '{source_name}' -> '{result['name']}'")
            link = result.get("webViewLink", "")
            if link:
                print_info(f"Link: {link}")

    except typer.Exit:
        raise
    except Exception as e:
        print_error(f"Failed: {e}")
        raise typer.Exit(EXIT_ERROR)


@app.command()
def rm(
    file: str = typer.Argument(..., help="File or folder to delete (name, URL, or ID)"),
    # permanent: bool = typer.Option(False, "--permanent", help="Permanently delete (irreversible)"),
    # NOTE: --permanent is disabled for safety. Uncomment above to enable hard deletes.
    confirm: bool = typer.Option(True, "--confirm/--no-confirm", help="Prompt before deleting"),
    type_filter: Optional[str] = typer.Option(None, "--type", "-t", help="Bulk: delete matching files in folder"),
    dry_run: bool = typer.Option(False, "--dry-run", help="Preview without executing"),
) -> None:
    """Move files to Google Drive trash (recoverable).

    Files can be restored from trash in Google Drive within 30 days.

    Examples:
        gwark drive rm "old-report.docx"
        gwark drive rm "Archive" --type pdf --dry-run
        gwark drive rm "temp-folder" --no-confirm
    """
    print_header("gwark drive rm")

    if type_filter and type_filter not in TYPE_ALIASES:
        print_error(f"Unknown type: {type_filter}")
        print_info(f"Valid types: {', '.join(TYPE_ALIASES.keys())}")
        raise typer.Exit(EXIT_VALIDATION)

    try:
        from gmail_mcp.auth import get_drive_service

        service = get_drive_service()

        # Resolve target(s)
        if type_filter:
            folder_meta = _resolve_target(service, file, require_folder=True)
            files_to_delete = _list_folder_files(service, folder_meta["id"], type_filter)
            if not files_to_delete:
                print_info(f"No {type_filter} files found in '{folder_meta.get('name', file)}'")
                return
        else:
            meta = _resolve_target(service, file)
            files_to_delete = [{
                "id": meta["id"],
                "name": meta.get("name", "Unknown"),
                "type": FILE_TYPE_MAP.get(meta.get("mimeType", ""), "File"),
                "mimeType": meta.get("mimeType", ""),
            }]

        _display_file_preview(files_to_delete, "Trash")
        print_warning("File(s) will be moved to trash. Recoverable for 30 days via Google Drive.")

        if dry_run:
            print_info("[DRY RUN] No changes applied")
            return

        if confirm:
            if not typer.confirm(f"Trash {len(files_to_delete)} file(s)?"):
                print_info("Cancelled")
                raise typer.Exit(0)

        # Execute
        deleted = 0
        for f in files_to_delete:
            try:
                retry_execute(
                    service.files().update(
                        fileId=f["id"],
                        body={"trashed": True},
                        supportsAllDrives=True,
                        fields="id",
                    ),
                    operation=f"Trash '{f['name']}'",
                )
                deleted += 1
            except Exception as e:
                print_warning(f"Failed to trash '{f['name']}': {e}")

        print_success(f"Trashed {deleted}/{len(files_to_delete)} file(s)")

    except typer.Exit:
        raise
    except Exception as e:
        print_error(f"Failed: {e}")
        raise typer.Exit(EXIT_ERROR)


# ---------------------------------------------------------------------------
# Phase 4: Permissions (share subcommands)
# ---------------------------------------------------------------------------


ROLE_CHOICES = ["reader", "writer", "commenter", "organizer"]


@share_app.command("list")
def share_list(
    file: str = typer.Argument(..., help="File or folder (name, URL, or ID)"),
    output_format: str = typer.Option("markdown", "--format", "-f", help="Output format: json, markdown"),
) -> None:
    """List sharing permissions for a file or folder.

    Examples:
        gwark drive share list "Report"
        gwark drive share list "https://drive.google.com/file/d/ID" --format json
    """
    print_header("gwark drive share list")

    try:
        from gmail_mcp.auth import get_drive_service

        service = get_drive_service()
        meta = _resolve_target(service, file)
        file_name = meta.get("name", "Unknown")

        print_info(f"Permissions for: {file_name}")

        result = retry_execute(
            service.permissions().list(
                fileId=meta["id"],
                supportsAllDrives=True,
                fields="permissions(id, type, role, emailAddress, displayName, domain)",
            ),
            operation="List permissions",
        )

        permissions = result.get("permissions", [])

        if not permissions:
            print_info("No permissions found")
            return

        if output_format == "json":
            console.print_json(data=permissions)
        else:
            from rich.table import Table

            table = Table(title=f"Permissions: {file_name}")
            table.add_column("Email / Domain", style="cyan")
            table.add_column("Name")
            table.add_column("Role", style="green")
            table.add_column("Type")

            for p in permissions:
                email = p.get("emailAddress", p.get("domain", "anyone"))
                display_name = p.get("displayName", "")
                role = p.get("role", "")
                ptype = p.get("type", "")
                table.add_row(email, display_name, role, ptype)

            console.print(table)

        print_success(f"{len(permissions)} permission(s)")

    except typer.Exit:
        raise
    except Exception as e:
        print_error(f"Failed: {e}")
        raise typer.Exit(EXIT_ERROR)


@share_app.command("add")
def share_add(
    file: str = typer.Argument(..., help="File or folder (name, URL, or ID)"),
    email: str = typer.Argument(..., help="Email address to share with"),
    role: str = typer.Option("reader", "--role", "-r", help="Permission role: reader, writer, commenter, organizer"),
    notify: bool = typer.Option(False, "--notify", help="Send notification email"),
) -> None:
    """Share a file or folder with a user.

    Examples:
        gwark drive share add "Report" user@example.com --role writer
        gwark drive share add "Team Folder" user@example.com --role organizer --notify
    """
    print_header("gwark drive share add")

    if role not in ROLE_CHOICES:
        print_error(f"Invalid role: {role}")
        print_info(f"Valid roles: {', '.join(ROLE_CHOICES)}")
        raise typer.Exit(EXIT_VALIDATION)

    try:
        from gmail_mcp.auth import get_drive_service

        service = get_drive_service()
        meta = _resolve_target(service, file)
        file_name = meta.get("name", "Unknown")

        print_info(f"Sharing '{file_name}' with {email} as {role}")

        result = retry_execute(
            service.permissions().create(
                fileId=meta["id"],
                body={
                    "type": "user",
                    "role": role,
                    "emailAddress": email,
                },
                supportsAllDrives=True,
                sendNotificationEmail=notify,
                fields="id, emailAddress, role",
            ),
            operation="Add permission",
        )

        print_success(f"Shared '{file_name}' with {result.get('emailAddress', email)} ({result.get('role', role)})")

    except typer.Exit:
        raise
    except Exception as e:
        print_error(f"Failed: {e}")
        raise typer.Exit(EXIT_ERROR)


@share_app.command("remove")
def share_remove(
    file: str = typer.Argument(..., help="File or folder (name, URL, or ID)"),
    email: str = typer.Argument(..., help="Email address to remove"),
    confirm: bool = typer.Option(True, "--confirm/--no-confirm", help="Prompt before removing"),
) -> None:
    """Remove sharing permission from a file or folder.

    Examples:
        gwark drive share remove "Report" user@example.com
        gwark drive share remove "Team Folder" user@example.com --no-confirm
    """
    print_header("gwark drive share remove")

    try:
        from gmail_mcp.auth import get_drive_service

        service = get_drive_service()
        meta = _resolve_target(service, file)
        file_name = meta.get("name", "Unknown")

        # Find permission by email
        result = retry_execute(
            service.permissions().list(
                fileId=meta["id"],
                supportsAllDrives=True,
                fields="permissions(id, emailAddress, role, type)",
            ),
            operation="List permissions",
        )

        target_perm = None
        for p in result.get("permissions", []):
            if p.get("emailAddress", "").lower() == email.lower():
                target_perm = p
                break

        if not target_perm:
            print_error(f"No permission found for {email} on '{file_name}'")
            raise typer.Exit(EXIT_NOT_FOUND)

        print_info(f"Removing {email} ({target_perm['role']}) from '{file_name}'")

        if confirm:
            if not typer.confirm("Remove this permission?"):
                print_info("Cancelled")
                raise typer.Exit(0)

        retry_execute(
            service.permissions().delete(
                fileId=meta["id"],
                permissionId=target_perm["id"],
                supportsAllDrives=True,
            ),
            operation="Remove permission",
        )

        print_success(f"Removed {email} from '{file_name}'")

    except typer.Exit:
        raise
    except Exception as e:
        print_error(f"Failed: {e}")
        raise typer.Exit(EXIT_ERROR)
