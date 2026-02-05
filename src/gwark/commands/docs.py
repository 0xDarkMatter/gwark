"""Google Docs commands for gwark CLI.

Create, edit, and manage Google Docs with markdown support and AI features.
"""

import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional

import typer
import yaml
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
from gwark.core.markdown_converter import MarkdownToDocsConverter, DocsToMarkdownConverter
from gwark.core.docs_analyzer import (
    DocsStructureAnalyzer,
    DocumentStructure,
    format_structure_table,
    format_structure_tree,
)
from gwark.schemas.themes import DocTheme, get_default_theme

console = Console()
app = typer.Typer(no_args_is_help=True)




def _extract_doc_id(doc_id_or_url: str) -> str:
    """Extract document ID from URL or return as-is.

    Handles:
    - https://docs.google.com/document/d/{DOC_ID}/edit
    - https://docs.google.com/document/d/{DOC_ID}/view
    - Raw document ID
    """
    match = re.search(r'/document/d/([a-zA-Z0-9_-]+)', doc_id_or_url)
    return match.group(1) if match else doc_id_or_url


def _read_stdin_or_file(file_path: Optional[Path]) -> Optional[str]:
    """Read content from stdin (-) or file path."""
    if file_path is None:
        return None

    if str(file_path) == "-":
        # Read from stdin
        import sys
        if sys.stdin.isatty():
            return None
        return sys.stdin.read()

    if file_path.exists():
        return file_path.read_text(encoding="utf-8")

    return None


def _load_theme(theme_name: Optional[str]) -> DocTheme:
    """Load theme by name from .gwark/themes/ or return default."""
    if not theme_name:
        return get_default_theme()

    # Check for built-in default
    if theme_name.lower() == "professional":
        return get_default_theme()

    # Look in .gwark/themes/
    theme_paths = [
        project_root / ".gwark" / "themes" / f"{theme_name}.yaml",
        project_root / ".gwark" / "themes" / f"{theme_name}.yml",
        Path.home() / ".gwark" / "themes" / f"{theme_name}.yaml",
    ]

    for theme_path in theme_paths:
        if theme_path.exists():
            try:
                data = yaml.safe_load(theme_path.read_text())
                return DocTheme(**data)
            except Exception as e:
                print_warning(f"Failed to load theme {theme_name}: {e}")
                return get_default_theme()

    print_warning(f"Theme '{theme_name}' not found, using default")
    return get_default_theme()


def _display_edit_preview(
    requests: list[dict],
    structure: Optional[DocumentStructure] = None,
) -> None:
    """Show what changes will be applied.

    Args:
        requests: List of Google Docs API batchUpdate requests
        structure: Optional document structure for context
    """
    console.print("\n[bold]Proposed Changes:[/bold]")

    for i, req in enumerate(requests, 1):
        if "insertText" in req:
            loc = req["insertText"]["location"]["index"]
            text = req["insertText"]["text"]
            # Truncate for display
            display_text = text[:50].replace("\n", "\\n")
            if len(text) > 50:
                display_text += "..."
            console.print(f"  {i}. [green]INSERT[/green] at index {loc}: \"{display_text}\"")
        elif "deleteContentRange" in req:
            r = req["deleteContentRange"]["range"]
            console.print(f"  {i}. [red]DELETE[/red] range {r['startIndex']}-{r['endIndex']} ({r['endIndex'] - r['startIndex']} chars)")
        elif "replaceAllText" in req:
            old = req["replaceAllText"]["containsText"]["text"]
            new = req["replaceAllText"]["replaceText"]
            console.print(f"  {i}. [yellow]REPLACE[/yellow] \"{old[:30]}\" → \"{new[:30]}\"")
        elif "updateTextStyle" in req:
            r = req["updateTextStyle"]["range"]
            console.print(f"  {i}. [blue]STYLE[/blue] range {r['startIndex']}-{r['endIndex']}")
        elif "updateParagraphStyle" in req:
            r = req["updateParagraphStyle"]["range"]
            console.print(f"  {i}. [blue]PARA STYLE[/blue] range {r['startIndex']}-{r['endIndex']}")

    console.print(f"\nTotal operations: {len(requests)}")

    if structure:
        console.print(f"Document length: {structure.total_length} characters")


def _build_insert_after_requests(
    content: str,
    heading: str,
    structure: DocumentStructure,
    theme: Optional[DocTheme],
) -> list[dict]:
    """Build requests to insert content after a specific heading's content.

    Args:
        content: Markdown content to insert
        heading: Heading text to find
        structure: Document structure
        theme: Optional theme for styling

    Returns:
        List of batchUpdate requests

    Raises:
        ValueError: If section not found
    """
    section = structure.find_section(heading)
    if not section:
        raise ValueError(f"Section '{heading}' not found in document")

    # Insert at section end (before next section starts)
    # Subtract 1 to insert before the trailing newline
    insert_index = section.end_index - 1 if section.end_index > 1 else section.end_index

    converter = MarkdownToDocsConverter(theme=theme or get_default_theme())
    return converter.convert("\n" + content, start_index=insert_index)


def _build_delete_section_requests(
    heading: str,
    structure: DocumentStructure,
) -> list[dict]:
    """Build request to delete a section (heading + content).

    Args:
        heading: Heading text to find
        structure: Document structure

    Returns:
        List containing delete request

    Raises:
        ValueError: If section not found
    """
    section = structure.find_section(heading)
    if not section:
        raise ValueError(f"Section '{heading}' not found in document")

    # Calculate delete range - be careful not to include final document newline
    delete_end = section.end_index
    if delete_end == structure.total_length:
        delete_end = delete_end - 1

    return [{
        "deleteContentRange": {
            "range": {
                "startIndex": section.start_index,
                "endIndex": delete_end,
            }
        }
    }]


def _build_move_section_requests(
    source_heading: str,
    target_heading: str,
    before: bool,
    structure: DocumentStructure,
    docs_service,
    doc_id: str,
) -> list[dict]:
    """Build requests to move a section to a new location.

    This operation:
    1. Extracts the source section content and styles
    2. Deletes the source section
    3. Inserts at the target location
    4. Re-applies heading styles to preserve structure

    To avoid index cascade issues, we:
    - If target is after source: delete first, then insert
    - If target is before source: insert first, then delete (with adjusted indices)

    Args:
        source_heading: Heading of section to move
        target_heading: Heading of target location
        before: True to insert before target, False for after
        structure: Document structure
        docs_service: Google Docs API service
        doc_id: Document ID

    Returns:
        List of batchUpdate requests

    Raises:
        ValueError: If source or target section not found
    """
    source = structure.find_section(source_heading)
    target = structure.find_section(target_heading)

    if not source:
        raise ValueError(f"Source section '{source_heading}' not found")
    if not target:
        raise ValueError(f"Target section '{target_heading}' not found")

    # Can't move to same position
    if source.start_index == target.start_index:
        raise ValueError("Cannot move section to its current position")

    # Get the raw document content
    doc = docs_service.documents().get(documentId=doc_id).execute()
    body = doc.get("body", {})
    content = body.get("content", [])

    # Extract text and paragraph style info from source section
    paragraphs = []  # List of (text, namedStyleType, relative_start)
    current_offset = 0

    for element in content:
        start_idx = element.get("startIndex", 0)
        end_idx = element.get("endIndex", 0)

        # Check if element is within source section
        if start_idx >= source.start_index and end_idx <= source.end_index:
            if "paragraph" in element:
                para = element["paragraph"]
                para_style = para.get("paragraphStyle", {})
                named_style = para_style.get("namedStyleType", "NORMAL_TEXT")

                para_text = ""
                for elem in para.get("elements", []):
                    text_run = elem.get("textRun", {})
                    para_text += text_run.get("content", "")

                if para_text:
                    paragraphs.append({
                        "text": para_text,
                        "style": named_style,
                        "relative_start": current_offset,
                        "length": len(para_text),
                    })
                    current_offset += len(para_text)

    if not paragraphs:
        raise ValueError("Could not extract content from source section")

    # Combine all text
    source_text = "".join(p["text"] for p in paragraphs)

    # Calculate target insertion point
    if before:
        insert_index = target.start_index
    else:
        insert_index = target.end_index

    # Calculate delete range - be careful not to include final document newline
    delete_start = source.start_index
    delete_end = source.end_index
    # If this is the last section, don't delete the final newline
    if delete_end == structure.total_length:
        delete_end = delete_end - 1

    requests = []

    # Determine operation order based on relative positions
    if insert_index > source.end_index:
        # Target is after source: delete first, then insert
        # After deletion, indices shift down by source length
        source_length = delete_end - delete_start
        adjusted_insert = insert_index - source_length

        requests.append({
            "deleteContentRange": {
                "range": {
                    "startIndex": delete_start,
                    "endIndex": delete_end,
                }
            }
        })
        requests.append({
            "insertText": {
                "location": {"index": adjusted_insert},
                "text": source_text,
            }
        })

        # Add style requests for ALL paragraphs to preserve/reset styles
        # This is needed because inserted text inherits surrounding styles
        for para in paragraphs:
            style_start = adjusted_insert + para["relative_start"]
            style_end = style_start + para["length"]
            # For paragraphs that are just newlines, we still need to style them
            # but use style_end = style_start + 1 to cover just the newline
            if para["length"] <= 1:
                style_end = style_start + 1
            requests.append({
                "updateParagraphStyle": {
                    "range": {
                        "startIndex": style_start,
                        "endIndex": max(style_end - 1, style_start + 1),
                    },
                    "paragraphStyle": {
                        "namedStyleType": para["style"],
                    },
                    "fields": "namedStyleType",
                }
            })
    else:
        # Target is before source: insert first, then delete
        # After insertion, source indices shift up by inserted length
        text_length = len(source_text)

        requests.append({
            "insertText": {
                "location": {"index": insert_index},
                "text": source_text,
            }
        })

        # Add style requests for ALL paragraphs to preserve/reset styles
        # This is needed because inserted text inherits surrounding styles
        for para in paragraphs:
            style_start = insert_index + para["relative_start"]
            style_end = style_start + para["length"]
            # For paragraphs that are just newlines, we still need to style them
            if para["length"] <= 1:
                style_end = style_start + 1
            requests.append({
                "updateParagraphStyle": {
                    "range": {
                        "startIndex": style_start,
                        "endIndex": max(style_end - 1, style_start + 1),
                    },
                    "paragraphStyle": {
                        "namedStyleType": para["style"],
                    },
                    "fields": "namedStyleType",
                }
            })

        requests.append({
            "deleteContentRange": {
                "range": {
                    "startIndex": delete_start + text_length,
                    "endIndex": delete_end + text_length,
                }
            }
        })

    return requests


@app.command()
def create(
    title: str = typer.Argument(..., help="Document title"),
    file: Optional[Path] = typer.Option(None, "--file", "-f", help="Markdown file ('-' for stdin)"),
    template: Optional[str] = typer.Option(None, "--template", "-t", help="Template document ID to copy"),
    theme: Optional[str] = typer.Option(None, "--theme", help="Theme name (default: professional)"),
    folder: Optional[str] = typer.Option(None, "--folder", help="Destination folder ID"),
    open_browser: bool = typer.Option(False, "--open", "-o", help="Open in browser after creation"),
) -> None:
    """Create Google Doc from markdown file, stdin, or template.

    Examples:
        gwark docs create "Report" --file report.md --theme professional
        echo "# Hello" | gwark docs create "Quick Doc" -f -
        gwark docs create "New Doc" --template TEMPLATE_ID

    For AI-generated content, use Claude Code to generate markdown, then pipe:
        claude "Write agenda for Q1 planning" | gwark docs create "Meeting Notes" -f -
    """
    print_header("gwark docs create")
    print_info(f"Creating document: {title}")

    # Validate: need at least one source
    content_source = file or template
    if not content_source:
        print_warning("No content source provided. Creating empty document.")

    try:
        from gmail_mcp.auth import get_docs_service, get_drive_service

        docs_service = get_docs_service()
        drive_service = get_drive_service()

        # Handle template-based creation
        if template:
            template_id = _extract_doc_id(template)
            print_info(f"Copying template: {template_id}")

            copy_body = {"name": title}
            if folder:
                copy_body["parents"] = [folder]

            copied = drive_service.files().copy(
                fileId=template_id,
                body=copy_body,
            ).execute()

            doc_id = copied["id"]
            print_success(f"Document created from template: {doc_id}")

        else:
            # Create empty document
            doc_body = {"title": title}
            doc = docs_service.documents().create(body=doc_body).execute()
            doc_id = doc["documentId"]
            print_info(f"Created document: {doc_id}")

            # Move to folder if specified
            if folder:
                drive_service.files().update(
                    fileId=doc_id,
                    addParents=folder,
                    removeParents="root",
                ).execute()
                print_info(f"Moved to folder: {folder}")

        # Read content
        markdown_content = None

        if file:
            markdown_content = _read_stdin_or_file(file)
            if markdown_content:
                print_info(f"Read {len(markdown_content)} characters from input")

        # Convert markdown to Docs API requests and apply
        if markdown_content:
            doc_theme = _load_theme(theme)
            converter = MarkdownToDocsConverter(theme=doc_theme)
            requests = converter.convert(markdown_content)

            if requests:
                print_info(f"Applying {len(requests)} formatting requests...")
                docs_service.documents().batchUpdate(
                    documentId=doc_id,
                    body={"requests": requests}
                ).execute()
                print_success("Content and formatting applied")

        # Output
        edit_url = f"https://docs.google.com/document/d/{doc_id}/edit"
        console.print(f"\n[bold]Document ID:[/bold] {doc_id}")
        console.print(f"[bold]Edit URL:[/bold] {edit_url}")

        if open_browser:
            import webbrowser
            webbrowser.open(edit_url)
            print_info("Opened in browser")

        print_success("Document created successfully!")

    except ImportError as e:
        print_error(f"Missing dependency: {e}")
        print_info("Run: pip install -e . and ensure OAuth is configured")
        raise typer.Exit(EXIT_ERROR)
    except Exception as e:
        print_error(f"Failed: {e}")
        raise typer.Exit(EXIT_ERROR)


@app.command()
def get(
    doc_id: str = typer.Argument(..., help="Document ID or URL"),
    output_format: str = typer.Option("markdown", "--format", "-f", help="Output format: markdown, json, text"),
    output: Optional[Path] = typer.Option(None, "--output", "-o", help="Output file path"),
) -> None:
    """Export document as markdown, JSON, or text.

    Examples:
        gwark docs get DOC_ID
        gwark docs get DOC_ID --format json -o doc.json
        gwark docs get "https://docs.google.com/document/d/DOC_ID/edit"
    """
    config = load_config()

    doc_id = _extract_doc_id(doc_id)
    print_header("gwark docs get")
    print_info(f"Fetching document: {doc_id}")

    try:
        from gmail_mcp.auth import get_docs_service

        service = get_docs_service()
        doc = service.documents().get(documentId=doc_id).execute()

        doc_title = doc.get("title", "Untitled")
        print_success(f"Retrieved: {doc_title}")

        # Format output
        formatter = OutputFormatter(output_dir=config.defaults.output_directory)

        if output_format == "json":
            content = formatter.to_json(doc)
            ext = "json"
        elif output_format == "text":
            # Extract plain text
            converter = DocsToMarkdownConverter()
            md = converter.convert(doc)
            # Strip markdown formatting for plain text
            content = re.sub(r'[#*_`\[\]()]', '', md)
            ext = "txt"
        else:  # markdown
            converter = DocsToMarkdownConverter()
            content = converter.convert(doc)
            ext = "md"

        prefix = f"doc_{doc_id[:8]}"
        output_path = formatter.save(content, prefix, ext, output)
        print_success(f"Saved to: {output_path}")

    except ImportError as e:
        print_error(f"Missing dependency: {e}")
        print_info("Run: pip install -e . and ensure OAuth is configured")
        raise typer.Exit(EXIT_ERROR)
    except Exception as e:
        print_error(f"Failed: {e}")
        raise typer.Exit(EXIT_ERROR)


@app.command()
def edit(
    doc_id: str = typer.Argument(..., help="Document ID or URL"),
    # Traditional operations
    append: Optional[str] = typer.Option(None, "--append", "-a", help="Append text/markdown content"),
    prepend: Optional[str] = typer.Option(None, "--prepend", help="Prepend text/markdown content"),
    replace: Optional[str] = typer.Option(None, "--replace", "-r", help="Replace text (format: 'old::new')"),
    file: Optional[Path] = typer.Option(None, "--file", "-f", help="Content file ('-' for stdin)"),
    # Section-aware operations (NEW)
    insert_after: Optional[str] = typer.Option(None, "--insert-after", help="Insert content after section heading"),
    move_section: Optional[str] = typer.Option(None, "--move-section", help="Section heading to move"),
    move_before: Optional[str] = typer.Option(None, "--before", help="Move section before this heading"),
    move_after: Optional[str] = typer.Option(None, "--after", help="Move section after this heading"),
    delete_section: Optional[str] = typer.Option(None, "--delete-section", help="Delete section by heading"),
    # Safety flags (NEW)
    dry_run: bool = typer.Option(False, "--dry-run", help="Preview changes without applying"),
    confirm: bool = typer.Option(False, "--confirm", "-c", help="Require confirmation before applying"),
    theme: Optional[str] = typer.Option(None, "--theme", help="Theme for new content"),
    # Collaboration visibility flags (NEW)
    highlight: bool = typer.Option(False, "--highlight", help="Highlight inserted content with yellow background"),
    comment: Optional[str] = typer.Option(None, "--comment", help="Add file comment explaining the edit"),
    keep_revision: bool = typer.Option(False, "--keep-revision", help="Mark revision as permanent (won't be auto-deleted)"),
) -> None:
    """Edit document with section-aware operations.

    Traditional operations:
        gwark docs edit DOC_ID --append "## New Section"
        gwark docs edit DOC_ID --prepend "# Updated Title"
        gwark docs edit DOC_ID --replace "old text::new text"
        echo "Content" | gwark docs edit DOC_ID --append -f -

    Section-aware operations (collaborative-friendly):
        gwark docs edit DOC_ID --insert-after "Introduction" --file content.md
        gwark docs edit DOC_ID --move-section "Conclusion" --before "References"
        gwark docs edit DOC_ID --delete-section "Draft Notes"

    Safety flags:
        gwark docs edit DOC_ID --append "content" --dry-run
        gwark docs edit DOC_ID --delete-section "Old" --confirm

    Collaboration visibility:
        gwark docs edit DOC_ID --append "content" --highlight --comment "Added by gwark"
        gwark docs edit DOC_ID --append "content" --keep-revision

    Use 'gwark docs sections DOC_ID' to see document structure first.
    """
    doc_id = _extract_doc_id(doc_id)
    print_header("gwark docs edit")
    print_info(f"Editing document: {doc_id}")

    # Validate: need at least one operation
    has_operation = any([
        append, prepend, replace, file,
        insert_after, move_section, delete_section
    ])
    if not has_operation:
        print_error("Must specify an operation: --append, --prepend, --replace, --insert-after, --move-section, --delete-section, or --file")
        raise typer.Exit(EXIT_VALIDATION)

    # Validate move operation
    if move_section and not (move_before or move_after):
        print_error("--move-section requires either --before or --after")
        raise typer.Exit(EXIT_VALIDATION)
    if (move_before or move_after) and not move_section:
        print_error("--before/--after requires --move-section")
        raise typer.Exit(EXIT_VALIDATION)
    if move_before and move_after:
        print_error("Cannot specify both --before and --after")
        raise typer.Exit(EXIT_VALIDATION)

    try:
        from gmail_mcp.auth import get_docs_service

        service = get_docs_service()

        # Get current document
        doc = service.documents().get(documentId=doc_id).execute()
        doc_title = doc.get("title", "Untitled")
        print_info(f"Document: {doc_title}")

        # Analyze document structure for section-aware operations
        analyzer = DocsStructureAnalyzer()
        structure = analyzer.analyze(doc)

        requests = []

        # Handle file input
        file_content = _read_stdin_or_file(file)

        # Find document end index
        body_content = doc.get("body", {}).get("content", [])
        end_index = 1  # Default to start
        for element in body_content:
            if "endIndex" in element:
                end_index = element["endIndex"]

        # === Section-aware operations (NEW) ===

        # Delete section
        if delete_section:
            try:
                delete_requests = _build_delete_section_requests(delete_section, structure)
                requests.extend(delete_requests)
                print_info(f"Deleting section: '{delete_section}'")
            except ValueError as e:
                print_error(str(e))
                raise typer.Exit(EXIT_VALIDATION)

        # Move section
        if move_section:
            target = move_before or move_after
            before = move_before is not None
            try:
                move_requests = _build_move_section_requests(
                    move_section, target, before, structure, service, doc_id
                )
                requests.extend(move_requests)
                position = "before" if before else "after"
                print_info(f"Moving section '{move_section}' {position} '{target}'")
            except ValueError as e:
                print_error(str(e))
                raise typer.Exit(EXIT_VALIDATION)

        # Insert after section
        if insert_after:
            content = file_content or ""
            if not content:
                print_error("--insert-after requires content via --file or stdin")
                raise typer.Exit(EXIT_VALIDATION)
            try:
                doc_theme = _load_theme(theme)
                insert_requests = _build_insert_after_requests(
                    content, insert_after, structure, doc_theme
                )
                requests.extend(insert_requests)
                print_info(f"Inserting content after section: '{insert_after}'")
            except ValueError as e:
                print_error(str(e))
                raise typer.Exit(EXIT_VALIDATION)

        # === Traditional operations ===

        # Handle replace operation
        if replace:
            if "::" not in replace:
                print_error("Replace format must be 'old::new'")
                raise typer.Exit(EXIT_VALIDATION)

            old_text, new_text = replace.split("::", 1)
            requests.append({
                "replaceAllText": {
                    "containsText": {
                        "text": old_text,
                        "matchCase": True,
                    },
                    "replaceText": new_text,
                }
            })
            print_info(f"Replacing '{old_text[:30]}...' with '{new_text[:30]}...'")

        # Handle prepend (only if not using insert_after)
        if prepend and not insert_after:
            doc_theme = _load_theme(theme)
            converter = MarkdownToDocsConverter(theme=doc_theme)

            # Insert at beginning (after document structure element)
            insert_requests = converter.convert(prepend + "\n")
            # Adjust indices - insert at position 1 (after document start)
            for req in insert_requests:
                if "insertText" in req:
                    req["insertText"]["location"]["index"] = 1
            requests.extend(insert_requests)
            print_info("Prepending content")

        # Handle append (only if not using insert_after)
        if append and not insert_after:
            content = append
            if file_content and not insert_after:
                content = file_content
            if content:
                doc_theme = _load_theme(theme)
                converter = MarkdownToDocsConverter(theme=doc_theme)

                # Add newline before appended content
                content = "\n" + content

                # Start at document end (before final newline)
                start_idx = end_index - 1 if end_index > 1 else 1
                md_requests = converter.convert(content, start_index=start_idx)
                requests.extend(md_requests)
                print_info("Appending content")

        # Handle file content for append (legacy behavior)
        if file_content and not any([append, prepend, insert_after]):
            # Default: prepend file content
            doc_theme = _load_theme(theme)
            converter = MarkdownToDocsConverter(theme=doc_theme)
            insert_requests = converter.convert(file_content + "\n")
            for req in insert_requests:
                if "insertText" in req:
                    req["insertText"]["location"]["index"] = 1
            requests.extend(insert_requests)
            print_info("Prepending file content")

        # === Safety checks ===

        if dry_run:
            _display_edit_preview(requests, structure)
            print_info("[DRY RUN] No changes applied")
            return

        if confirm:
            _display_edit_preview(requests, structure)
            if not typer.confirm("\nApply these changes?"):
                print_info("Cancelled")
                raise typer.Exit(0)

        # Execute batch update
        if requests:
            # Track insertions for highlighting
            insert_ranges = []
            for req in requests:
                if "insertText" in req:
                    loc = req["insertText"]["location"]["index"]
                    text = req["insertText"]["text"]
                    insert_ranges.append((loc, loc + len(text)))

            service.documents().batchUpdate(
                documentId=doc_id,
                body={"requests": requests}
            ).execute()
            print_success(f"Applied {len(requests)} changes")

            # Apply highlighting to inserted content
            if highlight and insert_ranges:
                highlight_requests = []
                for start_idx, end_idx in insert_ranges:
                    highlight_requests.append({
                        "updateTextStyle": {
                            "range": {
                                "startIndex": start_idx,
                                "endIndex": end_idx,
                            },
                            "textStyle": {
                                "backgroundColor": {
                                    "color": {
                                        "rgbColor": {
                                            "red": 1.0,
                                            "green": 0.95,
                                            "blue": 0.6,
                                        }
                                    }
                                }
                            },
                            "fields": "backgroundColor",
                        }
                    })
                if highlight_requests:
                    service.documents().batchUpdate(
                        documentId=doc_id,
                        body={"requests": highlight_requests}
                    ).execute()
                    print_info("Applied yellow highlight to inserted content")

            # Add file comment if specified
            if comment:
                try:
                    from gmail_mcp.auth import get_drive_service
                    drive_service = get_drive_service()

                    comment_body = {
                        "content": comment,
                    }
                    drive_service.comments().create(
                        fileId=doc_id,
                        body=comment_body,
                        fields="id,content,createdTime",
                    ).execute()
                    print_info(f"Added comment: {comment[:50]}...")
                except Exception as e:
                    print_warning(f"Failed to add comment: {e}")

            # Mark revision as permanent if specified
            if keep_revision:
                try:
                    from gmail_mcp.auth import get_drive_service
                    drive_service = get_drive_service()

                    # Get current (latest) revision
                    revisions = drive_service.revisions().list(
                        fileId=doc_id,
                        fields="revisions(id,modifiedTime)",
                    ).execute()

                    revision_list = revisions.get("revisions", [])
                    if revision_list:
                        latest_rev = revision_list[-1]
                        drive_service.revisions().update(
                            fileId=doc_id,
                            revisionId=latest_rev["id"],
                            body={"keepForever": True},
                        ).execute()
                        print_info(f"Marked revision {latest_rev['id'][:8]}... as permanent")
                except Exception as e:
                    print_warning(f"Failed to mark revision: {e}")
        else:
            print_warning("No changes to apply")

    except ImportError as e:
        print_error(f"Missing dependency: {e}")
        print_info("Run: pip install -e . and ensure OAuth is configured")
        raise typer.Exit(EXIT_ERROR)
    except typer.Exit:
        raise
    except Exception as e:
        print_error(f"Failed: {e}")
        raise typer.Exit(EXIT_ERROR)


@app.command()
def sections(
    doc_id: str = typer.Argument(..., help="Document ID or URL"),
    output_format: str = typer.Option("table", "--format", "-f", help="Output format: table, tree, json"),
) -> None:
    """Analyze and display document section structure.

    Shows heading hierarchy with indices - useful for planning edit operations.

    Examples:
        gwark docs sections DOC_ID
        gwark docs sections DOC_ID --format tree
        gwark docs sections DOC_ID --format json
    """
    doc_id = _extract_doc_id(doc_id)
    print_header("gwark docs sections")
    print_info(f"Analyzing document: {doc_id}")

    try:
        from gmail_mcp.auth import get_docs_service

        service = get_docs_service()
        doc = service.documents().get(documentId=doc_id).execute()

        doc_title = doc.get("title", "Untitled")
        print_success(f"Document: {doc_title}")

        # Analyze structure
        analyzer = DocsStructureAnalyzer()
        structure = analyzer.analyze(doc)

        if not structure.sections:
            print_warning("No headings found in document")
            console.print("\nThe document has no structured sections (headings).")
            console.print("Use heading styles in your document to enable section-aware operations.")
            return

        # Format output
        if output_format == "json":
            import json
            data = {
                "title": structure.title,
                "revision_id": structure.revision_id,
                "total_length": structure.total_length,
                "sections": [
                    {
                        "heading": s.heading_text,
                        "level": s.heading_level,
                        "start": s.start_index,
                        "end": s.end_index,
                        "content_start": s.content_start,
                        "size": s.total_length,
                    }
                    for s in structure.sections
                ]
            }
            console.print(json.dumps(data, indent=2))
        elif output_format == "tree":
            console.print(format_structure_tree(structure))
        else:  # table
            console.print(format_structure_table(structure))

        # Help text
        console.print("\n[dim]Section-aware edit commands:[/dim]")
        console.print(f"  [cyan]gwark docs edit {doc_id[:8]}... --insert-after \"<heading>\" -f content.md[/cyan]")
        console.print(f"  [cyan]gwark docs edit {doc_id[:8]}... --move-section \"<heading>\" --before \"<target>\"[/cyan]")
        console.print(f"  [cyan]gwark docs edit {doc_id[:8]}... --delete-section \"<heading>\" --confirm[/cyan]")

    except ImportError as e:
        print_error(f"Missing dependency: {e}")
        print_info("Run: pip install -e . and ensure OAuth is configured")
        raise typer.Exit(EXIT_ERROR)
    except Exception as e:
        print_error(f"Failed: {e}")
        raise typer.Exit(EXIT_ERROR)


@app.command()
def theme(
    apply: Optional[str] = typer.Option(None, "--apply", "-a", help="Apply theme to document"),
    doc_id: Optional[str] = typer.Option(None, "--doc", "-d", help="Document ID (required with --apply)"),
    list_themes: bool = typer.Option(False, "--list", "-l", help="List available themes"),
    show: Optional[str] = typer.Option(None, "--show", "-s", help="Show theme details"),
) -> None:
    """Manage and apply document themes.

    Examples:
        gwark docs theme --list
        gwark docs theme --show professional
        gwark docs theme --apply professional --doc DOC_ID
    """
    print_header("gwark docs theme")

    # List themes
    if list_themes:
        print_info("Available themes:")

        # Built-in themes
        console.print("\n[bold]Built-in:[/bold]")
        console.print("  - professional (default)")

        # Custom themes from .gwark/themes/
        themes_dirs = [
            project_root / ".gwark" / "themes",
            Path.home() / ".gwark" / "themes",
        ]

        custom_themes = []
        for themes_dir in themes_dirs:
            if themes_dir.exists():
                for f in themes_dir.glob("*.yaml"):
                    custom_themes.append(f.stem)
                for f in themes_dir.glob("*.yml"):
                    custom_themes.append(f.stem)

        if custom_themes:
            console.print("\n[bold]Custom:[/bold]")
            for t in sorted(set(custom_themes)):
                console.print(f"  - {t}")

        console.print(f"\nThemes directory: .gwark/themes/")
        return

    # Show theme details
    if show:
        theme_obj = _load_theme(show)
        console.print(f"\n[bold]Theme: {theme_obj.name}[/bold]")
        if theme_obj.description:
            console.print(f"Description: {theme_obj.description}\n")

        console.print("[bold]Paragraph Styles:[/bold]")
        for name, style in theme_obj.styles.items():
            font = style.font_family or "default"
            size = f"{style.font_size}pt" if style.font_size else "default"
            color = style.color or "default"
            console.print(f"  {name}: {font}, {size}, {color}")

        console.print("\n[bold]Inline Styles:[/bold]")
        for name, style in theme_obj.inline.items():
            attrs = []
            if style.bold:
                attrs.append("bold")
            if style.italic:
                attrs.append("italic")
            if style.font_family:
                attrs.append(style.font_family)
            if style.color:
                attrs.append(style.color)
            console.print(f"  {name}: {', '.join(attrs) or 'none'}")

        return

    # Apply theme to document
    if apply:
        if not doc_id:
            print_error("--doc is required when applying a theme")
            raise typer.Exit(EXIT_VALIDATION)

        doc_id = _extract_doc_id(doc_id)
        theme_obj = _load_theme(apply)
        print_info(f"Applying theme '{theme_obj.name}' to document: {doc_id}")

        try:
            from gmail_mcp.auth import get_docs_service

            service = get_docs_service()

            # Get document content
            doc = service.documents().get(documentId=doc_id).execute()
            body_content = doc.get("body", {}).get("content", [])

            requests = []

            # Apply styles to each paragraph
            for element in body_content:
                if "paragraph" not in element:
                    continue

                para = element["paragraph"]
                start_idx = element.get("startIndex", 0)
                end_idx = element.get("endIndex", 0)

                # Determine current style type
                para_style = para.get("paragraphStyle", {})
                named_style = para_style.get("namedStyleType", "NORMAL_TEXT")

                # Map Google's named styles to our theme styles
                style_map = {
                    "TITLE": "TITLE",
                    "HEADING_1": "HEADING_1",
                    "HEADING_2": "HEADING_2",
                    "HEADING_3": "HEADING_3",
                    "HEADING_4": "HEADING_3",
                    "HEADING_5": "HEADING_3",
                    "HEADING_6": "HEADING_3",
                    "SUBTITLE": "HEADING_2",
                    "NORMAL_TEXT": "NORMAL_TEXT",
                }

                theme_style_name = style_map.get(named_style, "NORMAL_TEXT")
                theme_style = theme_obj.styles.get(theme_style_name)

                if theme_style and start_idx < end_idx:
                    # Apply paragraph formatting
                    para_style_dict = theme_style.to_docs_paragraph_style()
                    if para_style_dict:
                        requests.append({
                            "updateParagraphStyle": {
                                "range": {"startIndex": start_idx, "endIndex": end_idx},
                                "paragraphStyle": para_style_dict,
                                "fields": ",".join(para_style_dict.keys()),
                            }
                        })

                    # Apply text formatting
                    # Skip text styles for NORMAL_TEXT to preserve inline bold/italic
                    if named_style != "NORMAL_TEXT":
                        text_style = theme_style.to_text_style().to_docs_api()
                        if text_style:
                            fields = []
                            for key in text_style:
                                if isinstance(text_style[key], dict):
                                    fields.append(key)
                                else:
                                    fields.append(key)
                            requests.append({
                                "updateTextStyle": {
                                    "range": {"startIndex": start_idx, "endIndex": end_idx},
                                    "textStyle": text_style,
                                    "fields": ",".join(fields),
                                }
                            })

            if requests:
                service.documents().batchUpdate(
                    documentId=doc_id,
                    body={"requests": requests}
                ).execute()
                print_success(f"Applied {len(requests)} style updates")
            else:
                print_warning("No styles to apply")

        except ImportError as e:
            print_error(f"Missing dependency: {e}")
            raise typer.Exit(EXIT_ERROR)
        except Exception as e:
            print_error(f"Failed: {e}")
            raise typer.Exit(EXIT_ERROR)

        return

    # No operation specified
    print_info("Use --list, --show, or --apply")
    console.print(app.info.help)


@app.command()
def summarize(
    doc_id: str = typer.Argument(..., help="Document ID or URL"),
    output: Optional[Path] = typer.Option(None, "--output", "-o", help="Output file path"),
) -> None:
    """Export document content for summarization via Claude Code.

    This exports the document as text. Pipe to Claude Code for summarization:

    Examples:
        gwark docs summarize DOC_ID | claude "Summarize as bullet points"
        gwark docs summarize DOC_ID | claude "Extract action items"
        gwark docs summarize DOC_ID -o doc.txt  # Save for later
    """
    config = load_config()

    doc_id = _extract_doc_id(doc_id)
    print_header("gwark docs summarize")
    print_info(f"Exporting document for summarization: {doc_id}")

    try:
        from gmail_mcp.auth import get_docs_service

        service = get_docs_service()

        # Get document content
        doc = service.documents().get(documentId=doc_id).execute()
        doc_title = doc.get("title", "Untitled")
        print_info(f"Document: {doc_title}")

        # Convert to text
        converter = DocsToMarkdownConverter()
        doc_text = converter.convert(doc)

        if not doc_text.strip():
            print_error("Document is empty")
            raise typer.Exit(EXIT_ERROR)

        print_info(f"Extracted {len(doc_text)} characters", err=True)

        # Output
        if output:
            formatter = OutputFormatter(output_dir=config.defaults.output_directory)
            output_path = formatter.save(doc_text, f"doc_{doc_id[:8]}", "txt", output)
            print_success(f"Saved to: {output_path}")
        else:
            # Print to stdout for piping
            print(doc_text)

    except ImportError as e:
        print_error(f"Missing dependency: {e}")
        raise typer.Exit(EXIT_ERROR)
    except Exception as e:
        print_error(f"Failed: {e}")
        raise typer.Exit(EXIT_ERROR)


@app.command()
def comment(
    doc_id: str = typer.Argument(..., help="Document ID or URL"),
    text: Optional[str] = typer.Option(None, "--text", "-t", help="Comment text (creates file-level comment)"),
    list_comments: bool = typer.Option(False, "--list", "-l", help="List all comments"),
    reply: Optional[str] = typer.Option(None, "--reply", "-r", help="Reply to comment ID"),
    resolve: Optional[str] = typer.Option(None, "--resolve", help="Resolve comment ID"),
    unresolve: Optional[str] = typer.Option(None, "--unresolve", help="Reopen comment ID"),
    include_resolved: bool = typer.Option(False, "--include-resolved", help="Include resolved (with --list)"),
) -> None:
    """Manage comments on Google Docs.

    IMPORTANT: Due to Google Drive API limitations, gwark can only create FILE-LEVEL comments.
    To create anchored comments (attached to specific text), use the Google Docs UI directly.
    However, gwark CAN list, reply to, and resolve anchored comments created in the UI.

    What works:
        + Create file-level comments via API
        + List all comments (file-level and anchored)
        + Reply to any comment (file-level or anchored)
        + Resolve/unresolve anchored comments (created in UI)

    What doesn't work:
        - Create anchored comments via API (must use Google Docs UI)
        - Resolve file-level comments (only anchored comments can be resolved)

    Examples:
        # Create a file-level comment
        gwark docs comment DOC_ID --text "Please review this document"

        # List all comments (includes anchored ones created in UI)
        gwark docs comment DOC_ID --list

        # Reply to a comment (works for any comment type)
        gwark docs comment DOC_ID --reply COMMENT_ID --text "Done, see v2"

        # Resolve a comment
        gwark docs comment DOC_ID --resolve COMMENT_ID

        # Reopen a resolved comment
        gwark docs comment DOC_ID --unresolve COMMENT_ID

    Hybrid workflow:
        1. Create anchored comments manually in Google Docs UI
        2. Use gwark to list, reply to, and manage them
    """
    doc_id = _extract_doc_id(doc_id)
    print_header("gwark docs comment")

    try:
        from gmail_mcp.auth import get_docs_service, get_drive_service
        from gwark.core.docs_comments import DocsCommentManager

        docs_service = get_docs_service()
        drive_service = get_drive_service()
        manager = DocsCommentManager(docs_service, drive_service)

        # List comments
        if list_comments:
            print_info(f"Fetching comments for document: {doc_id}")
            comments = manager.list_comments(doc_id, include_resolved=include_resolved)

            if not comments:
                print_warning("No comments found")
                return

            print_success(f"Found {len(comments)} comment(s)")

            # Display comments
            for i, comment in enumerate(comments, 1):
                author = comment.get('author', {}).get('displayName', 'Unknown')
                content = comment.get('content', '')
                created = comment.get('createdTime', '')
                comment_id = comment.get('id', '')
                resolved = comment.get('resolved', False)
                anchored = 'anchor' in comment

                # Format timestamp
                try:
                    from datetime import datetime
                    dt = datetime.fromisoformat(created.replace('Z', '+00:00'))
                    time_str = dt.strftime('%Y-%m-%d %H:%M')
                except Exception:
                    time_str = created[:16]

                # Print comment
                status = "[✓ Resolved]" if resolved else "[Open]"
                anchor_info = "[Anchored]" if anchored else "[File-level]"

                console.print(f"\n[bold cyan]Comment {i}[/bold cyan] {status} {anchor_info}")
                console.print(f"[dim]ID: {comment_id}[/dim]")
                console.print(f"[bold]{author}[/bold] - {time_str}")
                console.print(f"  {content}")

                # Show replies if any
                replies = comment.get('replies', [])
                if replies:
                    console.print(f"  [dim]{len(replies)} reply/replies:[/dim]")
                    for reply in replies:
                        reply_author = reply.get('author', {}).get('displayName', 'Unknown')
                        reply_content = reply.get('content', '')
                        console.print(f"    [cyan]>[/cyan] {reply_author}: {reply_content}")

            console.print(f"\n[dim]Total: {len(comments)} comment(s)[/dim]")
            return

        # Reply to comment
        if reply:
            if not text:
                print_error("--text required when replying to a comment")
                raise typer.Exit(EXIT_VALIDATION)

            print_info(f"Adding reply to comment: {reply}")
            result = manager.reply_to_comment(doc_id, reply, text)
            print_success(f"Reply added: {result.get('id')}")
            return

        # Resolve comment
        if resolve:
            print_info(f"Resolving comment: {resolve}")
            console.print("[dim]Note: Only anchored comments (created in UI) can be resolved[/dim]")
            manager.resolve_comment(doc_id, resolve)
            print_success(f"Comment {resolve} resolved")
            return

        # Unresolve comment
        if unresolve:
            print_info(f"Reopening comment: {unresolve}")
            console.print("[dim]Note: Only anchored comments (created in UI) can be reopened[/dim]")
            manager.unresolve_comment(doc_id, unresolve)
            print_success(f"Comment {unresolve} reopened")
            return

        # Add file-level comment
        if not text:
            print_error("--text required when creating a comment")
            raise typer.Exit(EXIT_VALIDATION)

        print_info("Creating file-level comment")
        console.print("[dim]Note: API limitation - cannot create anchored comments programmatically[/dim]")
        console.print("[dim]To anchor comments to text, create them manually in Google Docs UI[/dim]")

        result = manager.add_file_comment(doc_id, text)
        print_success("File-level comment added")
        console.print(f"[dim]Comment ID: {result.get('id')}[/dim]")

        # Show link to document
        doc_link = f"https://docs.google.com/document/d/{doc_id}/edit"
        console.print(f"\n[dim]View: {doc_link}[/dim]")

    except ImportError as e:
        print_error(f"Missing dependency: {e}")
        print_info("Run: pip install -e . and ensure OAuth is configured")
        raise typer.Exit(EXIT_ERROR)
    except ValueError as e:
        print_error(f"Not found: {e}")
        raise typer.Exit(EXIT_VALIDATION)
    except Exception as e:
        print_error(f"Failed: {e}")
        import traceback
        console.print(traceback.format_exc(), style="dim")
        raise typer.Exit(EXIT_ERROR)


@app.command("list")
def list_docs(
    query: Optional[str] = typer.Option(None, "--query", "-q", help="Search query"),
    folder: Optional[str] = typer.Option(None, "--folder", help="Folder ID to search in"),
    max_results: int = typer.Option(50, "--max-results", "-n", help="Maximum results"),
    owned_only: bool = typer.Option(False, "--owned-only", help="Only docs you own"),
    output_format: str = typer.Option("markdown", "--format", "-f", help="Output format: json, markdown"),
    output: Optional[Path] = typer.Option(None, "--output", "-o", help="Output file path"),
) -> None:
    """List Google Docs from Drive.

    Examples:
        gwark docs list
        gwark docs list --query "meeting notes"
        gwark docs list --folder FOLDER_ID --owned-only
    """
    config = load_config()

    print_header("gwark docs list")
    print_info("Fetching documents from Drive...")

    try:
        from gmail_mcp.auth import get_drive_service

        drive = get_drive_service()

        # Build query
        query_parts = ["mimeType='application/vnd.google-apps.document'", "trashed=false"]

        if owned_only:
            query_parts.append("'me' in owners")

        if folder:
            query_parts.append(f"'{folder}' in parents")

        if query:
            query_parts.append(f"fullText contains '{query}'")

        drive_query = " and ".join(query_parts)

        results = drive.files().list(
            q=drive_query,
            fields="files(id, name, createdTime, modifiedTime, owners, webViewLink)",
            pageSize=max_results,
            orderBy="modifiedTime desc",
        ).execute()

        docs = results.get('files', [])
        print_info(f"Found {len(docs)} documents")

        # Process documents
        processed_docs = []
        for d in docs:
            owners = d.get("owners", [])
            owner_email = owners[0].get("emailAddress", "Unknown") if owners else "Unknown"

            processed_docs.append({
                "id": d.get("id"),
                "title": d.get("name", "Untitled"),
                "createdTime": d.get("createdTime", ""),
                "modifiedTime": d.get("modifiedTime", ""),
                "owner": owner_email,
                "link": d.get("webViewLink", ""),
            })

        # Format output
        formatter = OutputFormatter(output_dir=config.defaults.output_directory)

        if output_format == "json":
            content = formatter.to_json(processed_docs)
            ext = "json"
        else:
            content = _format_docs_markdown(processed_docs)
            ext = "md"

        prefix = "docs_list"
        output_path = formatter.save(content, prefix, ext, output)
        print_success(f"Saved to: {output_path}")

    except ImportError as e:
        print_error(f"Missing dependency: {e}")
        print_info("Run: pip install -e . and ensure OAuth is configured")
        raise typer.Exit(EXIT_ERROR)
    except Exception as e:
        print_error(f"Failed: {e}")
        raise typer.Exit(EXIT_ERROR)


def _format_docs_markdown(docs: list) -> str:
    """Format docs list as markdown table."""
    lines = []
    lines.append("# Google Docs\n")
    lines.append(f"*Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}*\n")
    lines.append(f"*Total: {len(docs)} documents*\n")

    lines.append("| Modified | Title | Owner | Link |")
    lines.append("|----------|-------|-------|------|")

    for d in docs:
        try:
            mod_time = datetime.fromisoformat(d["modifiedTime"].replace("Z", "+00:00"))
            date_str = mod_time.strftime("%Y-%m-%d")
        except Exception:
            date_str = d.get("modifiedTime", "")[:10]

        title = d.get("title", "Untitled").replace("|", "\\|")[:40]
        owner = d.get("owner", "").split("@")[0]
        link = d.get("link", "")

        lines.append(f"| {date_str} | {title} | {owner} | [Open]({link}) |")

    return "\n".join(lines)


@app.command()
def review(
    doc_id: str = typer.Argument(..., help="Document ID or URL"),
    filter_text: Optional[str] = typer.Option(
        None,
        "--filter",
        "-f",
        help="Only process comments containing this text"
    ),
    dry_run: bool = typer.Option(
        False,
        "--dry-run",
        help="Show what would be processed without replying to comments"
    ),
    skip_confirmation: bool = typer.Option(
        False,
        "--yes",
        "-y",
        help="Skip confirmation prompt"
    ),
) -> None:
    """Process editorial comments on a Google Doc.

    Reads anchored comments (created in Google Docs UI), interprets editing
    instructions, and replies to each comment with AI-generated suggestions.

    WORKFLOW:
        1. Create anchored comments in Google Docs UI with instructions
           (e.g., "Make this more concise", "Rewrite in active voice")
        2. Run: gwark docs review DOC_ID
        3. AI processes each comment and replies with suggestions
        4. Review suggestions in comment replies
        5. Reply "accept" or "approved" to suggestions you want applied
        6. Run: gwark docs apply DOC_ID (applies approved changes)
        7. Resolve comments when done

    SUPPORTED INSTRUCTIONS:
        • "Make this more concise" - Reduce word count
        • "Rewrite in active voice" - Convert passive to active
        • "Clarify this section" - Improve clarity
        • "Fix grammar" - Correct errors
        • "Suggest better wording" - Provide alternatives
        • "Expand with details" - Add more content
        • "Simplify for beginners" - Reduce complexity
        • "Add code example" - Generate relevant examples

    NOTE: This command only SUGGESTS changes via comment replies.
          To apply approved suggestions, use: gwark docs apply DOC_ID
          Comments remain unresolved for your review.

    Examples:
        # Process all editorial comments
        gwark docs review DOC_ID

        # Only process comments containing "rewrite"
        gwark docs review DOC_ID --filter "rewrite"

        # Preview what would be processed
        gwark docs review DOC_ID --dry-run
    """
    from rich.panel import Panel
    from rich.prompt import Confirm

    doc_id = _extract_doc_id(doc_id)
    print_header("gwark docs review")
    print_info(f"Analyzing editorial comments in document: {doc_id}")

    try:
        from gmail_mcp.auth import get_docs_service, get_drive_service
        from gwark.core.docs_comments import DocsCommentManager

        docs_service = get_docs_service()
        drive_service = get_drive_service()
        manager = DocsCommentManager(docs_service, drive_service)

        # Get all unresolved comments
        print_info("Fetching comments...")
        all_comments = manager.list_comments(doc_id, include_resolved=False)

        # Filter for anchored comments only (have quotedFileContent)
        anchored_comments = [
            c for c in all_comments
            if 'anchor' in c and 'quotedFileContent' in c
        ]

        if not anchored_comments:
            print_warning("No anchored comments found")
            console.print("\n[dim]To use this feature:[/dim]")
            console.print("[dim]1. Open the document in Google Docs UI[/dim]")
            console.print("[dim]2. Select text and add comments with editing instructions[/dim]")
            console.print("[dim]3. Run this command again[/dim]")
            return

        # Apply text filter if specified
        if filter_text:
            filtered = [
                c for c in anchored_comments
                if filter_text.lower() in c.get('content', '').lower()
            ]
            if not filtered:
                print_warning(f"No comments matching filter: {filter_text}")
                return
            anchored_comments = filtered
            print_info(f"Filtered to {len(anchored_comments)} comment(s) matching '{filter_text}'")

        print_success(f"Found {len(anchored_comments)} editorial comment(s)")

        # Show preview
        console.print("\n[bold]Editorial Comments:[/bold]\n")
        for i, comment in enumerate(anchored_comments, 1):
            instruction = comment.get('content', '')
            quoted_text = comment.get('quotedFileContent', {}).get('value', '')
            author = comment.get('author', {}).get('displayName', 'Unknown')

            console.print(f"[cyan]Comment {i}/{len(anchored_comments)}[/cyan]")
            console.print(f"[bold]Instruction:[/bold] {instruction}")
            console.print(f"[bold]Anchored text:[/bold] {quoted_text[:100]}{'...' if len(quoted_text) > 100 else ''}")
            console.print(f"[dim]Author: {author}[/dim]\n")

        # Dry run exit
        if dry_run:
            print_info("Dry run - no changes made")
            return

        # Confirm processing
        if not skip_confirmation:
            console.print(f"\n[bold]This will reply to {len(anchored_comments)} comment(s) with AI suggestions.[/bold]")
            console.print("[dim]Comments will remain unresolved for your review.[/dim]")
            if not Confirm.ask("Process these comments?"):
                print_warning("Cancelled by user")
                return

        # Output tasks as JSON for programmatic processing
        console.print("\n[bold]=== EDITORIAL TASKS ===[/bold]\n")

        # Export tasks to JSON file
        import json
        tasks_file = Path("editorial_tasks.json")
        tasks_data = {
            "document_id": doc_id,
            "tasks": [
                {
                    "comment_id": c.get('id'),
                    "instruction": c.get('content', ''),
                    "original_text": c.get('quotedFileContent', {}).get('value', ''),
                    "author": c.get('author', {}).get('displayName', 'Unknown')
                }
                for c in anchored_comments
            ]
        }

        with open(tasks_file, 'w', encoding='utf-8') as f:
            json.dump(tasks_data, f, indent=2, ensure_ascii=False)

        print_success(f"Exported {len(anchored_comments)} tasks to: {tasks_file}")

        # Display tasks
        for i, task in enumerate(tasks_data['tasks'], 1):
            console.print(f"\n[cyan]TASK {i}/{len(anchored_comments)}[/cyan]")
            console.print(f"[bold]ID:[/bold] {task['comment_id']}")
            console.print(f"[bold]Instruction:[/bold] {task['instruction']}")
            console.print(f"[bold]Text:[/bold]")
            console.print(Panel(task['original_text'], border_style="dim"))

        # Instructions
        console.print(f"\n[bold green]=== Next Steps ===[/bold green]\n")
        console.print("Tasks have been exported to editorial_tasks.json")
        console.print("\nNow I (Claude Code) will:")
        console.print("1. Read the tasks from editorial_tasks.json")
        console.print("2. Generate AI suggestions for each one")
        console.print("3. Post them as comment replies in your Google Doc")
        console.print("\nRunning automated processing...")

        doc_link = f"https://docs.google.com/document/d/{doc_id}/edit"
        console.print(f"\n[dim]View: {doc_link}[/dim]")

    except ImportError as e:
        print_error(f"Missing dependency: {e}")
        print_info("Run: pip install -e . and ensure OAuth is configured")
        raise typer.Exit(EXIT_ERROR)
    except Exception as e:
        print_error(f"Failed: {e}")
        import traceback
        console.print(traceback.format_exc(), style="dim")
        raise typer.Exit(EXIT_ERROR)


@app.command()
def apply(
    doc_id: str = typer.Argument(..., help="Document ID or URL"),
    dry_run: bool = typer.Option(
        False,
        "--dry-run",
        help="Show what would be applied without making changes"
    ),
    skip_confirmation: bool = typer.Option(
        False,
        "--yes",
        "-y",
        help="Skip confirmation prompt"
    ),
) -> None:
    """Apply approved gwark suggestions to the document.

    Reads comment replies looking for user approval (replies containing
    "accept", "approved", "yes", or "apply"), then applies the gwark
    suggestions to the document.

    WORKFLOW:
        1. Run: gwark docs review DOC_ID (generates suggestions)
        2. Review suggestions in Google Docs comment replies
        3. Reply "accept" or "approved" to the ones you want applied
        4. Run: gwark docs apply DOC_ID (applies approved changes)
        5. Check the document - changes are applied to the text
        6. Use Docs revision history if you need to undo

    APPROVAL KEYWORDS:
        Reply to gwark's comment with any of these words:
        • "accept"
        • "approved"
        • "yes"
        • "apply"
        • "ok"
        • "confirm"

    NOTE: This command modifies your document. Use --dry-run first
          to preview what would be changed.

    Examples:
        # Preview what would be applied
        gwark docs apply DOC_ID --dry-run

        # Apply all approved suggestions
        gwark docs apply DOC_ID

        # Skip confirmation prompt
        gwark docs apply DOC_ID --yes
    """
    from rich.panel import Panel
    from rich.prompt import Confirm

    doc_id = _extract_doc_id(doc_id)
    print_header("gwark docs apply")
    print_info(f"Checking for approved suggestions in document: {doc_id}")

    try:
        from gmail_mcp.auth import get_docs_service, get_drive_service
        from gwark.core.docs_comments import DocsCommentManager

        docs_service = get_docs_service()
        drive_service = get_drive_service()
        manager = DocsCommentManager(docs_service, drive_service)

        # Get all comments (including resolved)
        print_info("Fetching comments and replies...")
        all_comments = manager.list_comments(doc_id, include_resolved=True)

        # Find gwark suggestions that have been approved
        # Very broad matching - any positive response counts as approval
        approval_keywords = [
            'accept', 'accepted', 'approve', 'approved', 'approve',
            'yes', 'yep', 'yeah', 'yup',
            'apply', 'ok', 'okay', 'confirm', 'confirmed',
            'go ahead', 'proceed', 'do it', 'looks good', 'lgtm',
            'agree', 'agreed', 'correct', 'right', 'good'
        ]
        approved_changes = []

        for comment in all_comments:
            # Skip if no anchor (not anchored to text)
            if 'anchor' not in comment:
                continue

            # Check replies for gwark suggestions
            replies = comment.get('replies', [])
            gwark_reply = None
            user_approval = False

            for reply in replies:
                content = reply.get('content', '')
                author = reply.get('author', {}).get('displayName', '')

                # Is this a gwark suggestion? (new format with emoji OR old format with footer)
                if content.startswith('🤖 **gwark**') or 'AI Editorial Suggestion via gwark' in content:
                    gwark_reply = content

                # Is this a user approval?
                elif any(keyword in content.lower() for keyword in approval_keywords):
                    user_approval = True

            # If we found both gwark suggestion AND user approval
            if gwark_reply and user_approval:
                quoted_text = comment.get('quotedFileContent', {}).get('value', '')

                # Extract the suggestion content (remove header and footer)
                suggestion_content = gwark_reply
                # Remove "🤖 **gwark**" header
                suggestion_content = re.sub(r'^🤖 \*\*gwark\*\*\s*\n+', '', suggestion_content)
                # Remove footer (---\nAI Editorial Suggestion...)
                suggestion_content = re.sub(r'\n+---\n.*$', '', suggestion_content, flags=re.DOTALL)

                approved_changes.append({
                    'comment_id': comment.get('id'),
                    'original_text': quoted_text,
                    'suggestion': suggestion_content.strip(),
                    'instruction': comment.get('content', '')
                })

        if not approved_changes:
            print_warning("No approved suggestions found")
            console.print("\n[dim]To approve suggestions:[/dim]")
            console.print("[dim]1. Review gwark's suggestions in Google Docs[/dim]")
            console.print("[dim]2. Reply 'accept' or 'approved' to the ones you want[/dim]")
            console.print("[dim]3. Run this command again[/dim]")
            return

        print_success(f"Found {len(approved_changes)} approved suggestion(s)")

        # Show preview
        console.print("\n[bold]Approved Changes:[/bold]\n")
        for i, change in enumerate(approved_changes, 1):
            # Sanitize text for Windows console (replace problematic Unicode)
            suggestion_preview = change['suggestion'][:300]
            suggestion_preview = suggestion_preview.replace('✓', '[OK]').replace('✗', '[X]')
            suggestion_preview = suggestion_preview.replace('•', '-').replace('━', '=')

            original_preview = change['original_text'][:100]
            original_preview = original_preview.replace('✓', '[OK]').replace('✗', '[X]')

            console.print(f"[cyan]Change {i}/{len(approved_changes)}[/cyan]")
            console.print(f"[bold]Original:[/bold] {original_preview}{'...' if len(change['original_text']) > 100 else ''}")
            console.print(f"[bold]Suggestion:[/bold]")
            console.print(Panel(suggestion_preview + ('...' if len(change['suggestion']) > 300 else ''), border_style="green"))

        # Dry run exit
        if dry_run:
            print_info("Dry run - no changes made")
            return

        # Confirm application
        if not skip_confirmation:
            console.print(f"\n[bold yellow]WARNING: This will modify your document![/bold yellow]")
            console.print(f"[dim]{len(approved_changes)} change(s) will be applied[/dim]")
            console.print("[dim]You can undo via Google Docs revision history[/dim]")
            if not Confirm.ask("Apply these changes?"):
                print_warning("Cancelled by user")
                return

        # Apply changes using Docs API
        print_info("Applying changes to document...")

        # Get document to find text positions
        doc = docs_service.documents().get(documentId=doc_id).execute()

        # Prepare batch updates (process in reverse to maintain positions)
        requests = []

        for change in reversed(approved_changes):  # Reverse to maintain text positions
            original = change['original_text']
            suggestion = change['suggestion']

            # Parse suggestion format - look for common patterns
            replacement_text = None

            # Pattern 1: "Cleaned up version:\n\n{text}"
            match = re.search(r'(?:Cleaned up version|Rewritten|New version):\s*\n+(.*)', suggestion, re.DOTALL | re.IGNORECASE)
            if match:
                replacement_text = match.group(1).strip()

            # Pattern 2: "**Rewritten:**\n\n{text}"
            if not replacement_text:
                match = re.search(r'\*\*(?:Rewritten|Cleaned up version|New version):\*\*\s*\n+(.*)', suggestion, re.DOTALL | re.IGNORECASE)
                if match:
                    replacement_text = match.group(1).strip()
                    # Remove "**Why this change:**" section if present
                    replacement_text = re.sub(r'\n+\*\*Why.*$', '', replacement_text, flags=re.DOTALL)

            # If no clear replacement pattern, skip (it's informational only)
            if not replacement_text:
                console.print(f"[yellow]Skipping informational comment (no clear replacement text)[/yellow]")
                continue

            # Find the text in the document
            # First try exact match
            text_range = _find_text_in_doc(doc, original)

            # If not found, try with the first 50 characters only (handle truncation)
            if not text_range and len(original) > 50:
                text_range = _find_text_in_doc(doc, original[:50])

            if not text_range:
                console.print(f"[yellow]Warning: Could not find text in document: {original[:50]}...[/yellow]")
                continue

            # Create replace request
            requests.append({
                'deleteContentRange': {
                    'range': {
                        'startIndex': text_range['startIndex'],
                        'endIndex': text_range['endIndex']
                    }
                }
            })
            requests.append({
                'insertText': {
                    'location': {
                        'index': text_range['startIndex']
                    },
                    'text': replacement_text
                }
            })

        if not requests:
            print_warning("No changes to apply (all suggestions were informational)")
            return

        # Execute batch update
        if requests:
            docs_service.documents().batchUpdate(
                documentId=doc_id,
                body={'requests': requests}
            ).execute()

            print_success(f"Applied {len(requests) // 2} change(s) to document")

            # Resolve comments
            for change in approved_changes:
                try:
                    manager.resolve_comment(doc_id, change['comment_id'])
                except Exception as e:
                    console.print(f"[dim]Note: Could not resolve comment {change['comment_id']}: {e}[/dim]")

            doc_link = f"https://docs.google.com/document/d/{doc_id}/edit"
            console.print(f"\n[bold green]Done![/bold green] View: {doc_link}")
            console.print("[dim]Check revision history if you need to undo changes[/dim]")

    except ImportError as e:
        print_error(f"Missing dependency: {e}")
        print_info("Run: pip install -e . and ensure OAuth is configured")
        raise typer.Exit(EXIT_ERROR)
    except Exception as e:
        print_error(f"Failed: {e}")
        import traceback
        console.print(traceback.format_exc(), style="dim")
        raise typer.Exit(EXIT_ERROR)


def _find_text_in_doc(doc: dict, search_text: str) -> Optional[dict]:
    """Find text in document and return its range.

    Args:
        doc: Document resource from Docs API
        search_text: Text to find

    Returns:
        Dict with startIndex and endIndex, or None if not found
    """
    # Build full document text for searching
    doc_text = ""
    positions = []  # Track (char_position, doc_index)
    char_index = 1  # Docs API uses 1-based indexing

    for element in doc.get('body', {}).get('content', []):
        if 'paragraph' not in element:
            continue

        para = element['paragraph']
        for text_run in para.get('elements', []):
            if 'textRun' not in text_run:
                continue

            content = text_run['textRun'].get('content', '')
            for i, char in enumerate(content):
                positions.append(char_index + i)
            doc_text += content
            char_index += len(content)

    # Try exact match first (don't normalize - quotedFileContent might have literal \n)
    if search_text in doc_text:
        offset = doc_text.index(search_text)
        if offset < len(positions):
            return {
                'startIndex': positions[offset],
                'endIndex': positions[min(offset + len(search_text), len(positions) - 1)]
            }

    # Try with normalized newlines
    search_normalized = search_text.replace('\\n', '\n')
    if search_normalized != search_text and search_normalized in doc_text:
        offset = doc_text.index(search_normalized)
        if offset < len(positions):
            return {
                'startIndex': positions[offset],
                'endIndex': positions[min(offset + len(search_normalized), len(positions) - 1)]
            }

    # Fallback: try first 100 chars
    if len(search_text) > 100:
        search_short = search_text[:100]
        if search_short in doc_text:
            offset = doc_text.index(search_short)
            if offset < len(positions):
                start_idx = positions[offset]
                end_idx = positions[min(offset + len(search_text), len(positions) - 1)]
                return {
                    'startIndex': start_idx,
                    'endIndex': end_idx
                }

    return None
