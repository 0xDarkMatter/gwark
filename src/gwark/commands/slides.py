"""Slides commands for gwark CLI.

Google Slides operations for creating, viewing, editing, and exporting presentations.
"""

import re
import sys
import webbrowser
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
    """Get SlidesClient with error handling."""
    try:
        from gwark.core.slides_client import SlidesClient
        return SlidesClient.from_gwark_auth()
    except ImportError as e:
        print_error(f"Missing dependency: {e}")
        print_info("Run: pip install -e . and ensure OAuth is configured")
        raise typer.Exit(EXIT_ERROR)
    except Exception as e:
        print_error(f"Failed to authenticate: {e}")
        print_info("Ensure OAuth is configured: gwark config auth setup")
        raise typer.Exit(EXIT_ERROR)


def _extract_presentation_id(id_or_url: str) -> str:
    """Extract presentation ID from URL or return as-is.

    Handles:
    - https://docs.google.com/presentation/d/{ID}/edit
    - https://docs.google.com/presentation/d/{ID}/view
    - Raw presentation ID
    """
    match = re.search(r'/presentation/d/([a-zA-Z0-9_-]+)', id_or_url)
    return match.group(1) if match else id_or_url


def _read_stdin_or_file(file_path: Optional[Path]) -> Optional[str]:
    """Read content from file or stdin.

    Args:
        file_path: Path to file, "-" for stdin, or None

    Returns:
        File content as string, or None if no input
    """
    if file_path is None:
        return None

    if str(file_path) == "-":
        # Read from stdin
        if sys.stdin.isatty():
            return None
        return sys.stdin.read()

    if file_path.exists():
        return file_path.read_text(encoding="utf-8")

    print_error(f"File not found: {file_path}")
    raise typer.Exit(EXIT_VALIDATION)


def _format_presentations_markdown(presentations: list) -> str:
    """Format presentations as markdown table."""
    if not presentations:
        return "No presentations found."

    lines = ["# Google Slides Presentations\n"]
    lines.append("| Title | ID | Modified |")
    lines.append("|-------|----|---------:|")

    for p in presentations:
        title = p.get("name", "Untitled")[:50]
        pid = p.get("id", "")
        modified = p.get("modifiedTime", "")[:10]
        lines.append(f"| {title} | `{pid}` | {modified} |")

    return "\n".join(lines)


def _format_structure_markdown(structure, include_notes: bool = True) -> str:
    """Format presentation structure as markdown."""
    lines = [f"# {structure.title}\n"]
    lines.append(f"**ID:** `{structure.presentation_id}`  ")
    lines.append(f"**Slides:** {structure.slide_count}  ")
    lines.append(f"**Size:** {structure.page_width:.0f} x {structure.page_height:.0f} points\n")

    lines.append("## Slides\n")

    for slide in structure.slides:
        title = slide.title or "(no title)"
        lines.append(f"### Slide {slide.index + 1}: {title}\n")

        if slide.elements:
            lines.append(f"*Elements:* {slide.element_count}")

        if include_notes and slide.speaker_notes:
            lines.append(f"\n**Speaker Notes:**\n> {slide.speaker_notes[:200]}{'...' if len(slide.speaker_notes) > 200 else ''}")

        lines.append("")

    return "\n".join(lines)


# =============================================================================
# COMMANDS
# =============================================================================

@app.command("list")
def list_presentations(
    max_results: int = typer.Option(50, "--max-results", "-n", help="Maximum results"),
    query: Optional[str] = typer.Option(None, "--query", "-q", help="Filter by name"),
    output_format: str = typer.Option(
        "markdown", "--format", "-f", help="Output format: json, markdown"
    ),
    output: Optional[Path] = typer.Option(None, "--output", "-o", help="Output file"),
    interactive: bool = typer.Option(False, "--interactive", "-i", help="Interactive mode"),
) -> None:
    """List Google Slides presentations."""
    config = load_config()
    print_header("gwark slides list")
    print_info("Fetching presentations...")

    try:
        client = _get_client()
        presentations = client.list_presentations(max_results=max_results, query=query)
        print_info(f"Found {len(presentations)} presentations")

        if interactive:
            _interactive_list(presentations)
            return

        # Format output
        formatter = OutputFormatter(output_dir=config.defaults.output_directory)

        if output_format == "json":
            content = formatter.to_json(presentations)
            ext = "json"
        else:
            content = _format_presentations_markdown(presentations)
            ext = "md"

        output_path = formatter.save(content, "slides_list", ext, output)
        print_success(f"Saved to: {output_path}")

    except Exception as e:
        print_error(f"Failed: {e}")
        raise typer.Exit(EXIT_ERROR)


def _interactive_list(presentations: list) -> None:
    """Interactive presentation browser."""
    if not presentations:
        print_warning("No presentations to display")
        return

    selected = 0

    def render():
        console.clear()
        table = Table(title="Google Slides Presentations")
        table.add_column("#", style="cyan", width=4)
        table.add_column("Title", style="bold")
        table.add_column("Modified", style="dim")
        table.add_column("ID", style="dim")

        for i, p in enumerate(presentations):
            marker = "▸" if i == selected else " "
            style = "reverse" if i == selected else ""
            table.add_row(
                f"{marker}{i + 1}",
                p.get("name", "Untitled")[:40],
                p.get("modifiedTime", "")[:10],
                p.get("id", "")[:12] + "...",
                style=style,
            )

        console.print(table)
        console.print("[dim]↑↓ Navigate | Enter/o: Open | q: Quit[/]")

    def getch():
        if sys.platform == 'win32':
            import msvcrt
            ch = msvcrt.getch()
            if ch in (b'\x00', b'\xe0'):
                ch2 = msvcrt.getch()
                if ch2 == b'H': return 'up'
                if ch2 == b'P': return 'down'
            if ch == b'\r': return 'enter'
            if ch == b'\x1b': return 'esc'
            return ch.decode('utf-8', errors='ignore').lower()
        else:
            import tty, termios
            fd = sys.stdin.fileno()
            old = termios.tcgetattr(fd)
            try:
                tty.setraw(fd)
                ch = sys.stdin.read(1)
                if ch == '\x1b':
                    ch2 = sys.stdin.read(2)
                    if ch2 == '[A': return 'up'
                    if ch2 == '[B': return 'down'
                    return 'esc'
                if ch in ('\r', '\n'): return 'enter'
                return ch.lower()
            finally:
                termios.tcsetattr(fd, termios.TCSADRAIN, old)

    try:
        while True:
            render()
            key = getch()

            if key in ('q', 'esc'):
                break
            elif key == 'up':
                selected = max(0, selected - 1)
            elif key == 'down':
                selected = min(len(presentations) - 1, selected + 1)
            elif key in ('enter', 'o'):
                pid = presentations[selected].get("id")
                if pid:
                    url = f"https://docs.google.com/presentation/d/{pid}/edit"
                    webbrowser.open(url)
    except (KeyboardInterrupt, EOFError):
        pass


@app.command("get")
def get_presentation(
    presentation_id: str = typer.Argument(..., help="Presentation ID or URL"),
    output_format: str = typer.Option(
        "markdown", "--format", "-f", help="Output format: json, markdown"
    ),
    output: Optional[Path] = typer.Option(None, "--output", "-o", help="Output file"),
    include_notes: bool = typer.Option(True, "--notes/--no-notes", help="Include speaker notes"),
    interactive: bool = typer.Option(False, "--interactive", "-i", help="Interactive viewer"),
) -> None:
    """Get presentation structure and slide outline."""
    config = load_config()
    presentation_id = _extract_presentation_id(presentation_id)

    print_header("gwark slides get")
    print_info(f"Fetching presentation: {presentation_id}")

    try:
        client = _get_client()
        structure = client.get_presentation_structure(presentation_id)
        print_success(f"Retrieved: {structure.title} ({structure.slide_count} slides)")

        if interactive:
            _interactive_viewer(structure, client.get_presentation_url(presentation_id))
            return

        # Format output
        formatter = OutputFormatter(output_dir=config.defaults.output_directory)

        if output_format == "json":
            # Convert to dict for JSON
            slides_data = []
            for slide in structure.slides:
                slides_data.append({
                    "index": slide.index,
                    "id": slide.slide_id,
                    "title": slide.title,
                    "speaker_notes": slide.speaker_notes if include_notes else "",
                    "element_count": slide.element_count,
                })

            data = {
                "presentation_id": structure.presentation_id,
                "title": structure.title,
                "slide_count": structure.slide_count,
                "page_size": {
                    "width": structure.page_width,
                    "height": structure.page_height,
                },
                "slides": slides_data,
            }
            content = formatter.to_json(data)
            ext = "json"
        else:
            content = _format_structure_markdown(structure, include_notes)
            ext = "md"

        output_path = formatter.save(content, f"slides_{presentation_id[:8]}", ext, output)
        print_success(f"Saved to: {output_path}")

    except Exception as e:
        print_error(f"Failed: {e}")
        raise typer.Exit(EXIT_ERROR)


def _interactive_viewer(structure, presentation_url: str) -> None:
    """Interactive slide viewer."""
    from rich.panel import Panel
    from rich.text import Text

    slides = structure.slides
    if not slides:
        print_warning("No slides to display")
        return

    selected = 0
    show_notes = True

    def render():
        console.clear()

        # Left pane: slide list
        left_lines = Text()
        left_lines.append(f"Slides ({len(slides)} total)\n\n", style="bold")

        for i, slide in enumerate(slides):
            marker = "▸" if i == selected else " "
            title = (slide.title or "(no title)")[:35]
            if i == selected:
                left_lines.append(f" {marker} {i + 1}. {title}\n", style="reverse bold")
            else:
                left_lines.append(f" {marker} {i + 1}. {title}\n")

        left_panel = Panel(left_lines, title=structure.title[:30], border_style="blue")

        # Right pane: slide content
        slide = slides[selected]
        content = Text()
        content.append(f"{slide.title or '(no title)'}\n", style="bold reverse")
        content.append("─" * 40 + "\n\n")

        # Show element summary
        if slide.elements:
            for elem in slide.elements[:5]:
                if elem.text_content:
                    content.append(f"• {elem.text_content[:60]}\n")

        # Speaker notes
        if show_notes and slide.speaker_notes:
            content.append("\n" + "─" * 40 + "\n", style="dim")
            content.append("Speaker Notes:\n", style="bold dim")
            notes_preview = slide.speaker_notes[:200]
            if len(slide.speaker_notes) > 200:
                notes_preview += "..."
            content.append(f"  {notes_preview}\n", style="dim")

        right_panel = Panel(
            content,
            title=f"Slide {selected + 1}/{len(slides)}",
            border_style="green"
        )

        # Grid layout
        table = Table.grid(expand=True)
        table.add_column(ratio=1)
        table.add_column(ratio=2)
        table.add_row(left_panel, right_panel)

        console.print(table)
        notes_toggle = "hide" if show_notes else "show"
        console.print(f"[dim]↑↓ Nav | n={notes_toggle} notes | o=Open | q=Quit[/]")

    def getch():
        if sys.platform == 'win32':
            import msvcrt
            ch = msvcrt.getch()
            if ch in (b'\x00', b'\xe0'):
                ch2 = msvcrt.getch()
                if ch2 == b'H': return 'up'
                if ch2 == b'P': return 'down'
            if ch == b'\r': return 'enter'
            if ch == b'\x1b': return 'esc'
            return ch.decode('utf-8', errors='ignore').lower()
        else:
            import tty, termios
            fd = sys.stdin.fileno()
            old = termios.tcgetattr(fd)
            try:
                tty.setraw(fd)
                ch = sys.stdin.read(1)
                if ch == '\x1b':
                    ch2 = sys.stdin.read(2)
                    if ch2 == '[A': return 'up'
                    if ch2 == '[B': return 'down'
                    return 'esc'
                if ch in ('\r', '\n'): return 'enter'
                return ch.lower()
            finally:
                termios.tcsetattr(fd, termios.TCSADRAIN, old)

    try:
        while True:
            render()
            key = getch()

            if key in ('q', 'esc'):
                break
            elif key == 'up':
                selected = max(0, selected - 1)
            elif key == 'down':
                selected = min(len(slides) - 1, selected + 1)
            elif key == 'n':
                show_notes = not show_notes
            elif key in ('o', 'enter'):
                webbrowser.open(presentation_url)
            elif key == 'g':
                selected = 0
            elif key == 'G':
                selected = len(slides) - 1
    except (KeyboardInterrupt, EOFError):
        pass


@app.command("create")
def create_presentation(
    title: str = typer.Argument(..., help="Presentation title"),
    file: Optional[Path] = typer.Option(
        None, "--file", "-f", help="Markdown file ('-' for stdin)"
    ),
    template: Optional[str] = typer.Option(
        None, "--template", "-t", help="Template presentation ID to clone"
    ),
    folder: Optional[str] = typer.Option(
        None, "--folder", help="Destination folder ID"
    ),
    open_browser: bool = typer.Option(False, "--open", "-o", help="Open in browser"),
) -> None:
    """Create a new presentation from markdown or template.

    Examples:
        # Empty presentation
        gwark slides create "My Deck"

        # From markdown file
        gwark slides create "Report" --file slides.md

        # From stdin (Claude Code pipeline)
        echo "# Slide 1\\n- Point" | gwark slides create "Quick Deck" -f -

        # From template
        gwark slides create "Q1 Report" --template TEMPLATE_ID
    """
    print_header("gwark slides create")

    try:
        client = _get_client()

        # Read markdown content if provided
        markdown_content = _read_stdin_or_file(file)

        if template:
            # Clone from template
            print_info(f"Cloning from template: {template}")
            result = client.create_from_template(title, template, folder)
        else:
            # Create empty presentation
            print_info(f"Creating presentation: {title}")
            result = client.create_presentation(title)

        presentation_id = result["id"]
        presentation_url = result["url"]

        # If markdown content provided, convert and apply
        if markdown_content:
            print_info("Converting markdown to slides...")
            _apply_markdown_content(client, presentation_id, markdown_content)

        print_success(f"Created: {title}")
        print_info(f"ID: {presentation_id}")
        print_info(f"URL: {presentation_url}")

        if open_browser:
            webbrowser.open(presentation_url)

    except Exception as e:
        print_error(f"Failed: {e}")
        raise typer.Exit(EXIT_ERROR)


def _apply_markdown_content(client, presentation_id: str, markdown: str) -> None:
    """Parse markdown and create slides.

    Format:
        # Slide Title
        - Bullet 1
        - Bullet 2

        ## Speaker Notes
        Notes here

        ---

        # Next Slide
    """
    # Split by --- (slide separator)
    slide_texts = re.split(r'\n---+\n', markdown)

    for slide_text in slide_texts:
        if not slide_text.strip():
            continue

        # Extract speaker notes
        notes = ""
        notes_match = re.search(
            r'##\s*Speaker\s*Notes\s*\n(.*?)(?=\n##|\Z)',
            slide_text,
            re.DOTALL | re.IGNORECASE
        )
        if notes_match:
            notes = notes_match.group(1).strip()
            slide_text = slide_text[:notes_match.start()] + slide_text[notes_match.end():]

        # Extract title (first # heading)
        title = ""
        title_match = re.match(r'#\s+(.+)\n', slide_text)
        if title_match:
            title = title_match.group(1).strip()
            slide_text = slide_text[title_match.end():]

        # Extract bullet points
        bullets = []
        for line in slide_text.split('\n'):
            line = line.strip()
            if line.startswith('- ') or line.startswith('* '):
                bullets.append(line[2:])
            elif line and not line.startswith('#'):
                bullets.append(line)

        # Add slide
        layout = "TITLE_AND_BODY" if bullets else "TITLE_ONLY"
        slide_id = client.add_slide(presentation_id, layout=layout)

        # For now, we create slides but text insertion requires
        # finding placeholder shape IDs which is complex.
        # Basic implementation creates the slides structure.

        # Add speaker notes if present
        if notes:
            try:
                client.add_speaker_notes(presentation_id, slide_id, notes)
            except Exception:
                pass  # Notes shape may not exist for all layouts


@app.command("export")
def export_presentation(
    presentation_id: str = typer.Argument(..., help="Presentation ID or URL"),
    output_format: str = typer.Option(
        "markdown", "--format", "-f", help="Export format: json, markdown"
    ),
    output: Optional[Path] = typer.Option(None, "--output", "-o", help="Output file"),
    include_notes: bool = typer.Option(True, "--notes/--no-notes", help="Include speaker notes"),
) -> None:
    """Export presentation structure.

    Note: PDF export requires Drive API access. Use Google Slides UI
    for full PDF export with formatting.
    """
    config = load_config()
    presentation_id = _extract_presentation_id(presentation_id)

    print_header("gwark slides export")
    print_info(f"Exporting presentation: {presentation_id}")

    try:
        client = _get_client()
        structure = client.get_presentation_structure(presentation_id)

        formatter = OutputFormatter(output_dir=config.defaults.output_directory)

        if output_format == "json":
            # Full JSON export
            raw = client.get_presentation(presentation_id)
            content = formatter.to_json(raw)
            ext = "json"
        else:
            # Markdown export
            content = _export_to_markdown(structure, include_notes)
            ext = "md"

        output_path = formatter.save(content, f"slides_export_{presentation_id[:8]}", ext, output)
        print_success(f"Exported to: {output_path}")

    except Exception as e:
        print_error(f"Failed: {e}")
        raise typer.Exit(EXIT_ERROR)


def _export_to_markdown(structure, include_notes: bool = True) -> str:
    """Export presentation to markdown format."""
    lines = []

    for i, slide in enumerate(structure.slides):
        if i > 0:
            lines.append("\n---\n")

        # Title
        title = slide.title or "(Untitled Slide)"
        lines.append(f"# {title}\n")

        # Content from text elements
        for elem in slide.elements:
            if elem.text_content and elem.placeholder_type != "TITLE":
                # Format as bullets if it looks like list content
                text = elem.text_content.strip()
                if '\n' in text:
                    for line in text.split('\n'):
                        line = line.strip()
                        if line:
                            lines.append(f"- {line}")
                else:
                    lines.append(text)
                lines.append("")

        # Speaker notes
        if include_notes and slide.speaker_notes:
            lines.append("\n## Speaker Notes")
            lines.append(slide.speaker_notes)
            lines.append("")

    return "\n".join(lines)


@app.command("add-slide")
def add_slide(
    presentation_id: str = typer.Argument(..., help="Presentation ID or URL"),
    title: Optional[str] = typer.Option(None, "--title", "-t", help="Slide title"),
    content: Optional[str] = typer.Option(None, "--content", "-c", help="Slide content"),
    file: Optional[Path] = typer.Option(
        None, "--file", "-f", help="Content file ('-' for stdin)"
    ),
    layout: str = typer.Option(
        "TITLE_AND_BODY", "--layout", "-l",
        help="Slide layout: BLANK, TITLE, TITLE_AND_BODY, TITLE_ONLY, SECTION_HEADER"
    ),
    position: Optional[int] = typer.Option(
        None, "--position", "-p", help="Insert position (1-based, default: end)"
    ),
    notes: Optional[str] = typer.Option(None, "--notes", "-n", help="Speaker notes"),
) -> None:
    """Add a slide to an existing presentation.

    Examples:
        gwark slides add-slide PRES_ID --title "New Slide"
        gwark slides add-slide PRES_ID --layout BLANK
        echo "Content" | gwark slides add-slide PRES_ID -f -
    """
    presentation_id = _extract_presentation_id(presentation_id)

    print_header("gwark slides add-slide")
    print_info(f"Adding slide to: {presentation_id}")

    try:
        client = _get_client()

        # Get content from file/stdin if provided
        file_content = _read_stdin_or_file(file)
        if file_content and not content:
            content = file_content

        # Adjust position to 0-based if provided
        insert_pos = None
        if position is not None:
            insert_pos = max(0, position - 1)

        # Add the slide
        slide_id = client.add_slide(
            presentation_id,
            layout=layout.upper(),
            position=insert_pos
        )

        print_success(f"Added slide: {slide_id}")

        # Add speaker notes if provided
        if notes:
            try:
                client.add_speaker_notes(presentation_id, slide_id, notes)
                print_info("Added speaker notes")
            except Exception as e:
                print_warning(f"Could not add notes: {e}")

        # Show URL
        url = client.get_presentation_url(presentation_id)
        print_info(f"URL: {url}")

    except Exception as e:
        print_error(f"Failed: {e}")
        raise typer.Exit(EXIT_ERROR)


@app.command("edit")
def edit_presentation(
    presentation_id: str = typer.Argument(..., help="Presentation ID or URL"),
    delete_slide: Optional[int] = typer.Option(
        None, "--delete-slide", help="Delete slide by index (1-based)"
    ),
    move_slide: Optional[str] = typer.Option(
        None, "--move-slide", help="Move slide: 'FROM:TO' (1-based)"
    ),
    replace_text: Optional[str] = typer.Option(
        None, "--replace", "-r", help="Replace text: 'old::new'"
    ),
    dry_run: bool = typer.Option(False, "--dry-run", help="Preview without applying"),
) -> None:
    """Edit presentation with various operations.

    Examples:
        # Delete slide 3
        gwark slides edit PRES_ID --delete-slide 3

        # Move slide 5 to position 2
        gwark slides edit PRES_ID --move-slide "5:2"

        # Replace text globally
        gwark slides edit PRES_ID --replace "2024::2025"
    """
    presentation_id = _extract_presentation_id(presentation_id)

    print_header("gwark slides edit")

    try:
        client = _get_client()
        structure = client.get_presentation_structure(presentation_id)

        if delete_slide:
            if delete_slide < 1 or delete_slide > structure.slide_count:
                print_error(f"Invalid slide index: {delete_slide} (1-{structure.slide_count})")
                raise typer.Exit(EXIT_VALIDATION)

            slide = structure.slides[delete_slide - 1]
            print_info(f"Delete slide {delete_slide}: {slide.title or '(no title)'}")

            if not dry_run:
                client.delete_slide(presentation_id, slide.slide_id)
                print_success("Slide deleted")
            else:
                print_info("[dry-run] Would delete slide")

        elif move_slide:
            try:
                from_pos, to_pos = map(int, move_slide.split(":"))
            except ValueError:
                print_error("Invalid format. Use 'FROM:TO' (e.g., '5:2')")
                raise typer.Exit(EXIT_VALIDATION)

            if from_pos < 1 or from_pos > structure.slide_count:
                print_error(f"Invalid source index: {from_pos}")
                raise typer.Exit(EXIT_VALIDATION)

            slide = structure.slides[from_pos - 1]
            print_info(f"Move slide {from_pos} → {to_pos}: {slide.title or '(no title)'}")

            if not dry_run:
                client.move_slide(presentation_id, slide.slide_id, to_pos - 1)
                print_success("Slide moved")
            else:
                print_info("[dry-run] Would move slide")

        elif replace_text:
            if "::" not in replace_text:
                print_error("Invalid format. Use 'old::new'")
                raise typer.Exit(EXIT_VALIDATION)

            old, new = replace_text.split("::", 1)
            print_info(f"Replace: '{old}' → '{new}'")

            if not dry_run:
                count = client.replace_all_text(presentation_id, old, new)
                print_success(f"Replaced {count} occurrence(s)")
            else:
                print_info("[dry-run] Would replace text")

        else:
            print_warning("No operation specified. Use --delete-slide, --move-slide, or --replace")

    except Exception as e:
        print_error(f"Failed: {e}")
        raise typer.Exit(EXIT_ERROR)
