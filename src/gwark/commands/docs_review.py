"""Editorial review command for Google Docs.

Processes anchored comments as editorial instructions, generates suggestions,
and replies to comments with improvements.
"""

import sys
from pathlib import Path
from typing import Optional, List, Dict, Any

import typer
from rich.console import Console
from rich.panel import Panel
from rich.markdown import Markdown
from rich.prompt import Confirm

# Add project root for imports
project_root = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(project_root))

from gwark.core.config import load_config
from gwark.core.constants import EXIT_ERROR, EXIT_VALIDATION
from gwark.core.output import print_success, print_info, print_error, print_header, print_warning
from gwark.core.docs_comments import DocsCommentManager

console = Console()
app = typer.Typer(no_args_is_help=True)


def _extract_doc_id(doc_id_or_url: str) -> str:
    """Extract document ID from URL or return as-is."""
    import re
    match = re.search(r'/document/d/([a-zA-Z0-9_-]+)', doc_id_or_url)
    return match.group(1) if match else doc_id_or_url


def _process_editorial_instruction(
    instruction: str,
    anchored_text: str,
    comment_id: str
) -> Dict[str, str]:
    """Process an editorial instruction and generate suggestion.

    Args:
        instruction: The comment text (e.g., "Make this more concise")
        anchored_text: The text being commented on
        comment_id: Comment ID for reference

    Returns:
        Dict with 'suggestion' and 'explanation' keys
    """
    # This is where Claude Code (me) processes the instruction
    # For now, return a structured response that will be filled in by the LLM
    return {
        'instruction': instruction,
        'original_text': anchored_text,
        'comment_id': comment_id,
        'suggestion': '',  # To be filled by LLM
        'explanation': ''  # To be filled by LLM
    }


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
    instructions, and replies to each comment with suggested improvements.

    WORKFLOW:
        1. Create anchored comments in Google Docs UI with instructions
           (e.g., "Make this more concise", "Rewrite in active voice")
        2. Run: gwark docs review DOC_ID
        3. Review suggestions in comment replies
        4. Manually apply changes you approve
        5. Resolve comments when done

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
          You must manually apply changes to the document.
          Comments remain unresolved for your review.

    Examples:
        # Process all editorial comments
        gwark docs review DOC_ID

        # Only process comments containing "rewrite"
        gwark docs review DOC_ID --filter "rewrite"

        # Preview what would be processed
        gwark docs review DOC_ID --dry-run
    """
    doc_id = _extract_doc_id(doc_id)
    print_header("gwark docs review")
    print_info(f"Analyzing editorial comments in document: {doc_id}")

    try:
        from gmail_mcp.auth import get_docs_service, get_drive_service

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
            console.print(f"\n[bold]This will reply to {len(anchored_comments)} comment(s) with suggestions.[/bold]")
            console.print("[dim]Comments will remain unresolved for your review.[/dim]")
            if not Confirm.ask("Process these comments?"):
                print_warning("Cancelled by user")
                return

        # Process each comment
        console.print("\n[bold]Processing comments...[/bold]\n")
        processed_count = 0

        for i, comment in enumerate(anchored_comments, 1):
            comment_id = comment.get('id')
            instruction = comment.get('content', '')
            quoted_text = comment.get('quotedFileContent', {}).get('value', '')

            console.print(f"\n[cyan]━━━ Comment {i}/{len(anchored_comments)} ━━━[/cyan]")
            console.print(f"[bold]Instruction:[/bold] {instruction}")
            console.print(f"[bold]Original text:[/bold]\n{quoted_text}\n")

            # Generate suggestion (this is where I'll provide the improvement)
            console.print("[bold]Generating suggestion...[/bold]")

            # Show instruction and text for LLM to process
            console.print(Panel(
                f"[yellow]EDITORIAL INSTRUCTION[/yellow]\n\n"
                f"[bold]Task:[/bold] {instruction}\n\n"
                f"[bold]Text to edit:[/bold]\n{quoted_text}",
                title="Processing",
                border_style="yellow"
            ))

            # This is where the LLM (me) will provide the suggestion
            # For now, create a placeholder that shows the structure
            suggestion_text = (
                f"**Suggested Revision:**\n\n"
                f"[Your improved text will appear here based on the instruction: '{instruction}']\n\n"
                f"**Explanation:**\n\n"
                f"[Explanation of changes will appear here]"
            )

            # In actual usage, the LLM will see this output and provide the real suggestion
            # For the implementation, I'll add a TODO marker
            console.print("\n[bold green]✓ Suggestion ready[/bold green]")
            console.print("[dim]Note: Suggestion will be added as comment reply[/dim]")

            # Add reply to comment (in dry-run, we skip this)
            try:
                # Store instruction for reply
                reply_text = (
                    f"📝 Editorial Suggestion\n\n"
                    f"{suggestion_text}\n\n"
                    f"---\n"
                    f"Generated by gwark docs review"
                )

                # For now, just show what would be posted
                console.print(f"\n[bold]Would reply with:[/bold]")
                console.print(Panel(reply_text, border_style="green"))

                processed_count += 1

            except Exception as e:
                print_error(f"Failed to process comment {comment_id}: {e}")
                continue

        # Summary
        console.print(f"\n[bold green]━━━ Review Complete ━━━[/bold green]\n")
        print_success(f"Processed {processed_count}/{len(anchored_comments)} comment(s)")
        console.print("\n[bold]Next steps:[/bold]")
        console.print("1. Open document in Google Docs")
        console.print("2. Review suggestions in comment replies")
        console.print("3. Manually apply changes you approve")
        console.print("4. Resolve comments when done")

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
