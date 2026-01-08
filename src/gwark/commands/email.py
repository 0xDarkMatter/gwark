"""Email commands for gwark CLI."""

import asyncio
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

import typer
from rich.console import Console

# Add project root for imports
project_root = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(project_root))

from gwark.core.config import load_config, get_profile
from gwark.core.dates import date_to_gmail_query, format_short_date
from gwark.core.email_utils import extract_email_details, extract_name, build_gmail_query
from gwark.core.output import (
    OutputFormatter,
    print_success,
    print_info,
    print_error,
    print_header,
)
from gwark.ui.progress import FetchProgress
from gwark.ui.viewer import EmailViewer

console = Console()
app = typer.Typer(no_args_is_help=True)


@app.command()
def search(
    domain: Optional[str] = typer.Option(None, "--domain", "-d", help="Domain to search"),
    sender: Optional[str] = typer.Option(None, "--sender", "-s", help="Sender email address"),
    recipient: Optional[str] = typer.Option(None, "--recipient", "-r", help="Recipient email address"),
    subject: Optional[str] = typer.Option(None, "--subject", help="Subject search term"),
    query: Optional[str] = typer.Option(None, "--query", "-q", help="Raw Gmail query"),
    days: int = typer.Option(30, "--days", "-n", help="Days to look back"),
    max_results: int = typer.Option(500, "--max-results", "-m", help="Maximum results"),
    output_format: str = typer.Option("markdown", "--format", "-f", help="Output format: json, csv, markdown, text"),
    detail: str = typer.Option("summary", "--detail", help="Detail level: summary or full"),
    summarize: bool = typer.Option(False, "--summarize", help="Enable AI summarization"),
    interactive: bool = typer.Option(False, "--interactive", "-i", help="Launch interactive viewer"),
    profile: Optional[str] = typer.Option(None, "--profile", "-p", help="Use named profile"),
    output: Optional[Path] = typer.Option(None, "--output", "-o", help="Output file path"),
) -> None:
    """Search emails by domain, sender, subject, or custom query."""
    emails = asyncio.run(_search_async(
        domain=domain,
        sender=sender,
        recipient=recipient,
        subject=subject,
        query=query,
        days=days,
        max_results=max_results,
        output_format=output_format,
        detail=detail,
        summarize=summarize,
        profile=profile,
        output=output,
    ))

    # Launch interactive viewer after async completes (must be in sync context)
    if interactive and emails:
        from gwark.core.output import print_info
        print_info("Launching interactive viewer... (q to quit)")
        viewer = EmailViewer(emails, title=f"Email Search: {domain or query or 'all'}")
        viewer.run()


async def _search_async(
    domain: Optional[str],
    sender: Optional[str],
    recipient: Optional[str],
    subject: Optional[str],
    query: Optional[str],
    days: int,
    max_results: int,
    output_format: str,
    detail: str,
    summarize: bool,
    profile: Optional[str],
    output: Optional[Path],
) -> list | None:
    """Async implementation of email search."""
    # Load config
    config = load_config()
    if profile:
        prof = get_profile(profile)
        days = prof.settings.days_back or days
        max_results = prof.settings.max_results or max_results

    # Force full detail for summarization
    if summarize:
        detail = "full"

    print_header("gwark email search")
    print_info(f"Days back: {days}, Max results: {max_results}, Detail: {detail}")

    try:
        # Import Gmail client
        from gmail_mcp.gmail import GmailClient, GmailOperations

        # Build query
        after_date = date_to_gmail_query(datetime.now() - timedelta(days=days))
        gmail_query = build_gmail_query(
            domain=domain,
            sender=sender,
            recipient=recipient,
            subject=subject,
            after_date=after_date,
            custom_query=query,
        )

        if not gmail_query:
            print_error("No search criteria provided. Use --domain, --sender, --query, etc.")
            raise typer.Exit(1)

        print_info(f"Query: {gmail_query}")

        # Initialize client
        print_info("Connecting to Gmail API...")
        client = GmailClient()
        operations = GmailOperations(client)

        # Search for messages
        print_info("Searching emails...")
        search_results = await operations.search_emails(
            query=gmail_query,
            max_results=max_results,
        )
        messages = search_results.get("messages", [])

        if not messages:
            print_info("No emails found matching criteria.")
            return

        # Limit to max_results
        if len(messages) > max_results:
            messages = messages[:max_results]

        print_success(f"Found {len(messages)} emails")

        # Fetch email details using simple sync API (more reliable than batch)
        from gmail_mcp.auth import get_gmail_service
        service = get_gmail_service()

        message_ids = [m["id"] for m in messages]
        api_format = "full" if detail == "full" else "metadata"

        # Use animated progress bar for fetching
        emails = []
        with FetchProgress(len(message_ids), "Fetching emails") as progress:
            for msg_id in message_ids:
                try:
                    email_data = service.users().messages().get(
                        userId="me",
                        id=msg_id,
                        format=api_format,
                    ).execute()
                    details = extract_email_details(email_data, detail_level=detail)
                    emails.append(details)
                except Exception as e:
                    pass  # Skip failed fetches silently during progress
                progress.advance()

        if not emails:
            print_error("Failed to fetch any email details")
            raise typer.Exit(1)

        # Sort by date (newest first)
        emails.sort(key=lambda x: x.get("date_timestamp", 0), reverse=True)

        print_success(f"Processed {len(emails)} emails")

        # AI Summarization
        if summarize:
            try:
                from gmail_mcp.ai import batch_summarize_emails
                print_info("Generating AI summaries...")
                emails = batch_summarize_emails(emails)
                print_success("AI summaries generated")
            except ImportError:
                print_error("AI summarizer not available. Install anthropic package.")
            except Exception as e:
                print_error(f"AI summarization failed: {e}")

        # Format output
        formatter = OutputFormatter(output_dir=config.defaults.output_directory)

        if output_format == "json":
            content = formatter.to_json(emails)
            ext = "json"
        elif output_format == "csv":
            content = formatter.to_csv(emails)
            ext = "csv"
        elif output_format == "markdown":
            content = _format_email_markdown(emails, summarize=summarize)
            ext = "md"
        else:
            content = _format_email_text(emails)
            ext = "txt"

        # Save output
        prefix = f"email_search_{domain or 'all'}"
        output_path = formatter.save(content, prefix, ext, output)
        print_success(f"Saved to: {output_path}")

        return emails

    except ImportError as e:
        print_error(f"Missing dependency: {e}")
        print_info("Run: pip install -e .")
        raise typer.Exit(1)
    except Exception as e:
        print_error(f"Search failed: {e}")
        raise typer.Exit(1)


def _format_email_markdown(emails: list, summarize: bool = False) -> str:
    """Format emails as markdown table."""
    lines = []
    lines.append("# Email Search Results\n")
    lines.append(f"*Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}*\n")
    lines.append(f"*Total: {len(emails)} emails*\n")

    # Table header
    lines.append("| Date | From → To | Subject | Link |")
    lines.append("|------|-----------|---------|------|")

    for email in emails:
        date = format_short_date(email.get("date", ""))
        from_name = extract_name(email.get("from", ""))
        to_name = extract_name(email.get("to", ""))
        subject = email.get("subject", "No Subject").replace("|", "\\|")[:60]
        email_id = email.get("id", "")
        link = f"[View](https://mail.google.com/mail/u/0/#all/{email_id})"

        lines.append(f"| {date} | {from_name} → {to_name} | {subject} | {link} |")

        # Add AI summary if available
        if summarize and email.get("ai_summary"):
            summary = email["ai_summary"].replace("|", "\\|")
            for line in summary.split("\n"):
                if line.strip():
                    lines.append(f"|  |  | *{line.strip()}* |  |")

    return "\n".join(lines)


def _format_email_text(emails: list) -> str:
    """Format emails as plain text."""
    lines = []
    for email in emails:
        lines.append(f"Subject: {email.get('subject', 'No Subject')}")
        lines.append(f"From: {email.get('from', 'Unknown')}")
        lines.append(f"To: {email.get('to', 'Unknown')}")
        lines.append(f"Date: {email.get('date', '')}")
        lines.append(f"Snippet: {email.get('snippet', '')}")
        lines.append("-" * 80)
    return "\n".join(lines)


@app.command()
def sent(
    year: int = typer.Option(datetime.now().year, "--year", "-y", help="Year to search"),
    month: int = typer.Option(datetime.now().month, "--month", "-m", help="Month to search"),
    estimate_time: bool = typer.Option(False, "--estimate-time", "-t", help="Estimate time spent"),
    max_results: int = typer.Option(500, "--max-results", help="Maximum results"),
    output_format: str = typer.Option("markdown", "--format", "-f", help="Output format"),
    profile: Optional[str] = typer.Option(None, "--profile", "-p", help="Use named profile"),
    output: Optional[Path] = typer.Option(None, "--output", "-o", help="Output file path"),
) -> None:
    """Extract and analyze sent emails for a specific month."""
    asyncio.run(_sent_async(
        year=year,
        month=month,
        estimate_time=estimate_time,
        max_results=max_results,
        output_format=output_format,
        profile=profile,
        output=output,
    ))


async def _sent_async(
    year: int,
    month: int,
    estimate_time: bool,
    max_results: int,
    output_format: str,
    profile: Optional[str],
    output: Optional[Path],
) -> None:
    """Async implementation of sent email extraction."""
    print_header("gwark email sent")
    print_info(f"Extracting sent emails for {year}-{month:02d}")

    try:
        from gmail_mcp.gmail import GmailClient, GmailOperations
        from gmail_mcp.gmail.batch import BatchOperations

        # Calculate date range
        start_date = datetime(year, month, 1)
        if month == 12:
            end_date = datetime(year + 1, 1, 1)
        else:
            end_date = datetime(year, month + 1, 1)

        query = f"in:sent after:{date_to_gmail_query(start_date)} before:{date_to_gmail_query(end_date)}"
        print_info(f"Query: {query}")

        # Initialize client
        client = GmailClient()
        await client.connect()
        operations = GmailOperations(client)

        # Search for messages
        messages = await operations.search_messages(query=query, max_results=max_results)

        if not messages:
            print_info("No sent emails found.")
            return

        print_success(f"Found {len(messages)} sent emails")

        # Batch read
        batch_ops = BatchOperations(client=client, max_concurrent=50)
        message_ids = [m["id"] for m in messages]

        all_successful = {}
        for i in range(0, len(message_ids), 50):
            chunk = message_ids[i:i+50]
            batch_results = await batch_ops.batch_read(
                message_ids=chunk,
                format="full" if estimate_time else "metadata",
            )
            all_successful.update(batch_results["successful"])

        # Process results
        emails = []
        for msg_id, email_data in all_successful.items():
            details = extract_email_details(email_data, detail_level="full" if estimate_time else "summary")
            emails.append(details)

        emails.sort(key=lambda x: x.get("date_timestamp", 0), reverse=True)

        # Time estimation with AI
        if estimate_time:
            try:
                from gmail_mcp.ai import batch_summarize_emails
                print_info("Estimating time spent...")
                emails = batch_summarize_emails(emails)
            except Exception as e:
                print_error(f"Time estimation failed: {e}")

        # Format and save
        config = load_config()
        formatter = OutputFormatter(output_dir=config.defaults.output_directory)

        if output_format == "markdown":
            content = _format_sent_markdown(emails, year, month, estimate_time)
            ext = "md"
        else:
            content = formatter.to_json(emails)
            ext = "json"

        prefix = f"sent_emails_{year}{month:02d}"
        output_path = formatter.save(content, prefix, ext, output)
        print_success(f"Saved to: {output_path}")

    except Exception as e:
        print_error(f"Failed: {e}")
        raise typer.Exit(1)


def _format_sent_markdown(emails: list, year: int, month: int, estimate_time: bool) -> str:
    """Format sent emails as markdown."""
    lines = []
    lines.append(f"# Sent Emails - {year}-{month:02d}\n")
    lines.append(f"*Total: {len(emails)} emails*\n")

    if estimate_time:
        lines.append("| Date | To | Subject | Summary | Time |")
        lines.append("|------|----|---------| --------|------|")
    else:
        lines.append("| Date | To | Subject |")
        lines.append("|------|----|---------|")

    for email in emails:
        date = format_short_date(email.get("date", ""))
        to_name = extract_name(email.get("to", ""))
        subject = email.get("subject", "No Subject").replace("|", "\\|")[:50]

        if estimate_time:
            summary = email.get("ai_summary", "")[:100].replace("|", "\\|")
            lines.append(f"| {date} | {to_name} | {subject} | {summary} | -- |")
        else:
            lines.append(f"| {date} | {to_name} | {subject} |")

    return "\n".join(lines)


@app.command()
def summarize(
    input_file: Path = typer.Argument(..., help="Input JSON file with emails"),
    batch_size: int = typer.Option(10, "--batch-size", "-b", help="Emails per API call"),
    output: Optional[Path] = typer.Option(None, "--output", "-o", help="Output file path"),
) -> None:
    """Summarize emails from a JSON file using AI."""
    import json

    print_header("gwark email summarize")

    if not input_file.exists():
        print_error(f"Input file not found: {input_file}")
        raise typer.Exit(1)

    try:
        with open(input_file, "r", encoding="utf-8") as f:
            emails = json.load(f)

        print_info(f"Loaded {len(emails)} emails from {input_file}")

        from gmail_mcp.ai import batch_summarize_emails

        summarized = batch_summarize_emails(emails, batch_size=batch_size)

        # Save output
        output_path = output or input_file.with_suffix(".summarized.json")
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(summarized, f, indent=2)

        print_success(f"Saved to: {output_path}")

    except Exception as e:
        print_error(f"Summarization failed: {e}")
        raise typer.Exit(1)
