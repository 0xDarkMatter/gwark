#!/usr/bin/env python
"""Generic email search and analysis tool for Gmail MCP Server.

Search emails by domain, sender, date range, and export detailed results.
"""

import asyncio
import argparse
import base64
import json
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root / "src"))

# Load environment variables
try:
    from dotenv import load_dotenv
    env_path = project_root / ".env"
    load_dotenv(dotenv_path=env_path)
except ImportError:
    pass

from gmail_mcp.gmail import GmailClient, GmailOperations
from gmail_mcp.gmail.batch import BatchOperations

# Import summarizer
try:
    from email_summarizer import batch_summarize_emails
    SUMMARIZER_AVAILABLE = True
except ImportError:
    SUMMARIZER_AVAILABLE = False


def print_header(text: str) -> None:
    """Print formatted header."""
    print("\n" + "=" * 80)
    print(f"  {text}")
    print("=" * 80 + "\n")


def print_success(text: str) -> None:
    """Print success message."""
    print(f"[OK] {text}")


def print_info(text: str) -> None:
    """Print info message."""
    print(f"[INFO] {text}")


def extract_name(email_address: str) -> str:
    """Extract name from email address.

    Examples:
        "John Doe <john@example.com>" -> "John Doe"
        "john@example.com" -> "john"
        "John.Doe@example.com" -> "John Doe"
    """
    if not email_address:
        return "Unknown"

    # Check if name is in angle brackets format
    if "<" in email_address:
        name_part = email_address.split("<")[0].strip()
        if name_part:
            return name_part

    # Extract from email address
    email_part = email_address.split("<")[-1].replace(">", "").strip()
    local_part = email_part.split("@")[0]

    # Replace dots and underscores with spaces, capitalize
    name = local_part.replace(".", " ").replace("_", " ").title()
    return name


def format_short_date(date_str: str) -> str:
    """Format date string to DD/MM/YYYY.

    Args:
        date_str: Email date string

    Returns:
        Formatted date string or original if parsing fails
    """
    try:
        from email.utils import parsedate_to_datetime
        parsed = parsedate_to_datetime(date_str)
        return parsed.strftime("%d/%m/%Y")
    except Exception:
        return date_str


def extract_email_details(email_data: dict, detail_level: str = "full") -> dict:
    """Extract relevant details from email message.

    Args:
        email_data: Raw Gmail API message data
        detail_level: Level of detail - "summary", "metadata", or "full"

    Returns:
        Structured email details dictionary
    """
    payload = email_data.get("payload", {})
    headers = payload.get("headers", [])

    # Build header lookup
    header_map = {h["name"]: h["value"] for h in headers}

    # Parse date
    date_str = header_map.get("Date", "")
    try:
        # Try to parse date for sorting
        from email.utils import parsedate_to_datetime

        parsed_date = parsedate_to_datetime(date_str)
        date_timestamp = parsed_date.timestamp()
    except Exception:
        date_timestamp = 0

    # Basic metadata available in all modes
    result = {
        "id": email_data["id"],
        "threadId": email_data.get("threadId"),
        "subject": header_map.get("Subject", "No Subject"),
        "from": header_map.get("From", "Unknown"),
        "to": header_map.get("To", "Unknown"),
        "date": date_str,
        "date_timestamp": date_timestamp,
        "snippet": email_data.get("snippet", ""),
        "labels": email_data.get("labelIds", []),
        "size_estimate": email_data.get("sizeEstimate", 0),
    }

    # Only extract body and attachments in full mode
    if detail_level == "full":
        # Extract email body
        def get_body(payload):
            """Recursively extract email body text."""
            if "body" in payload and payload["body"].get("data"):
                try:
                    return base64.urlsafe_b64decode(payload["body"]["data"]).decode(
                        "utf-8", errors="ignore"
                    )
                except Exception:
                    return ""

            if "parts" in payload:
                for part in payload["parts"]:
                    # Prefer text/plain, fallback to text/html
                    if part.get("mimeType") in ["text/plain", "text/html"]:
                        if part.get("body", {}).get("data"):
                            try:
                                return base64.urlsafe_b64decode(part["body"]["data"]).decode(
                                    "utf-8", errors="ignore"
                                )
                            except Exception:
                                continue
                    # Recursive for nested parts
                    if "parts" in part:
                        body = get_body(part)
                        if body:
                            return body
            return ""

        body_text = get_body(payload)

        # Extract attachments
        attachments = []

        def extract_attachments(parts):
            """Recursively extract attachment info."""
            for part in parts:
                filename = part.get("filename")
                if filename:
                    attachments.append(
                        {
                            "filename": filename,
                            "mimeType": part.get("mimeType", "unknown"),
                            "size": part.get("body", {}).get("size", 0),
                        }
                    )
                # Recurse into nested parts
                if "parts" in part:
                    extract_attachments(part["parts"])

        if "parts" in payload:
            extract_attachments(payload["parts"])

        result["cc"] = header_map.get("Cc")
        result["bcc"] = header_map.get("Bcc")
        result["body_preview"] = body_text[:500] if body_text else email_data.get("snippet", "")
        result["body_full"] = body_text if len(body_text) < 10000 else body_text[:10000] + "..."
        result["attachments"] = attachments
    else:
        # Summary/metadata mode - minimal data
        result["attachments"] = []

    return result


async def search_emails(
    domain: Optional[str] = None,
    sender: Optional[str] = None,
    recipient: Optional[str] = None,
    subject: Optional[str] = None,
    query: Optional[str] = None,
    days_back: int = 180,
    max_results: int = 500,
    account_id: str = "primary",
    output_format: str = "json",
    detail_level: str = "summary",
    show_preview: bool = False,
    summarize: bool = False,
) -> None:
    """Search and export Gmail emails based on criteria.

    Args:
        domain: Domain to search (e.g., 'grandprix.com.au')
        sender: Sender email address
        recipient: Recipient email address
        subject: Subject line search term
        query: Raw Gmail query (overrides other filters)
        days_back: Number of days to look back
        max_results: Maximum results to return
        account_id: Gmail account ID
        output_format: Output format (json, csv, text, markdown)
        detail_level: Detail level - "summary" (fast, metadata only), "full" (slow, includes body/attachments)
        show_preview: Show email snippet/preview in summary mode (markdown only)
        summarize: Generate AI summaries using Claude (requires full detail level)
    """
    print_header("Gmail Email Search")

    # Handle summarization requirements
    if summarize:
        if not SUMMARIZER_AVAILABLE:
            print("[ERROR] Summarization requires 'anthropic' package")
            print("[INFO] Install with: pip install anthropic")
            return
        # Summarization requires full email bodies
        if detail_level != "full":
            print_info("Summarization enabled - switching to 'full' detail level")
            detail_level = "full"

    # Build search query
    if query:
        search_query = query
        print_info(f"Using custom query: {query}")
    else:
        query_parts = []

        # Calculate date cutoff
        date_cutoff = datetime.now() - timedelta(days=days_back)
        date_str = date_cutoff.strftime("%Y/%m/%d")
        query_parts.append(f"after:{date_str}")

        # Add filters
        if domain:
            query_parts.append(f"(to:*@{domain} OR from:*@{domain})")
        if sender:
            query_parts.append(f"from:{sender}")
        if recipient:
            query_parts.append(f"to:{recipient}")
        if subject:
            query_parts.append(f'subject:"{subject}"')

        search_query = " ".join(query_parts)

    print_info(f"Query: {search_query}")
    print_info(f"Date Range: Last {days_back} days")
    print_info(f"Max Results: {max_results}")
    print_info(f"Detail Level: {detail_level}")
    print()

    # Create client and operations
    print_info("Connecting to Gmail API...")
    client = GmailClient(account_id=account_id)
    ops = GmailOperations(client=client)

    try:
        # Search emails
        print_info("Searching emails...")
        search_results = await ops.search_emails(
            query=search_query, page_size=100, max_results=max_results
        )

        messages = search_results.get("messages", [])
        total_estimate = search_results.get("resultSizeEstimate", 0)

        print_success(f"Found {total_estimate} matching emails")
        print_info(f"Fetching details for {len(messages)} emails...")
        print()

        if not messages:
            print("No emails found matching criteria.")
            return

        # Batch read email details (chunk into groups of 50)
        # Reduce concurrency to avoid SSL errors
        batch_ops = BatchOperations(client=client, max_concurrent=1)

        message_ids = [m["id"] for m in messages]
        all_successful = {}
        all_failed = {}

        # Choose API format based on detail level
        api_format = "full" if detail_level == "full" else "metadata"

        print_info(f"Fetching emails with format: {api_format}")

        # Process in chunks of 50
        for i in range(0, len(message_ids), 50):
            chunk = message_ids[i:i+50]
            batch_results = await batch_ops.batch_read(message_ids=chunk, format=api_format)
            all_successful.update(batch_results["successful"])
            all_failed.update(batch_results["failed"])

        # Combine results
        batch_results = {
            "successful": all_successful,
            "failed": all_failed,
            "total": len(message_ids),
            "success_count": len(all_successful),
            "failure_count": len(all_failed),
        }

        # Process results
        print_info("Processing email details...")
        emails = []

        for msg_id, email_data in batch_results["successful"].items():
            details = extract_email_details(email_data, detail_level=detail_level)
            emails.append(details)

        # Sort by date (most recent first)
        emails.sort(key=lambda x: x.get("date_timestamp", 0), reverse=True)

        print_success(f"Processed {len(emails)} emails successfully")

        if batch_results["failed"]:
            print_info(f"Failed to fetch {len(batch_results['failed'])} emails")

        # Generate AI summaries if requested
        if summarize and emails:
            print_info("Generating AI summaries...")
            try:
                emails = batch_summarize_emails(emails, batch_size=10)
                print_success("AI summaries generated")
            except Exception as e:
                print(f"[ERROR] Failed to generate summaries: {e}")

        # Display summary
        print_header(f"EMAIL INDEX ({len(emails)} emails)")

        for idx, email in enumerate(emails[:10], 1):  # Show first 10
            print(f"[{idx}] {email['subject']}")
            print(f"    ID: {email['id']}")
            print(f"    Date: {email['date']}")
            print(f"    From: {email['from']}")
            print(f"    To: {email['to']}")

            if email.get("cc"):
                print(f"    CC: {email['cc']}")

            if detail_level == "full" and email["attachments"]:
                print(f"    Attachments ({len(email['attachments'])}):")
                for att in email["attachments"][:3]:  # Show first 3
                    size_kb = att["size"] / 1024
                    print(f"      - {att['filename']} ({size_kb:.1f} KB)")

            print(f"    Preview: {email['snippet'][:100]}...")
            print()

        if len(emails) > 10:
            print(f"... and {len(emails) - 10} more emails\n")

        # Export results
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

        # Create reports directory if it doesn't exist
        reports_dir = Path("reports")
        reports_dir.mkdir(exist_ok=True)

        if output_format == "json":
            output_file = reports_dir / f"email_search_{timestamp}.json"
            with open(output_file, "w", encoding="utf-8") as f:
                json.dump(
                    {
                        "search_query": search_query,
                        "search_date": datetime.now().isoformat(),
                        "total_results": len(emails),
                        "emails": emails,
                    },
                    f,
                    indent=2,
                    ensure_ascii=False,
                )

        elif output_format == "csv":
            import csv

            output_file = reports_dir / f"email_search_{timestamp}.csv"
            with open(output_file, "w", encoding="utf-8", newline="") as f:
                writer = csv.DictWriter(
                    f,
                    fieldnames=[
                        "id",
                        "date",
                        "from",
                        "to",
                        "cc",
                        "subject",
                        "snippet",
                        "attachment_count",
                        "attachment_names",
                    ],
                )
                writer.writeheader()

                for email in emails:
                    att_names = ", ".join([a["filename"] for a in email["attachments"]])
                    writer.writerow(
                        {
                            "id": email["id"],
                            "date": email["date"],
                            "from": email["from"],
                            "to": email["to"],
                            "cc": email.get("cc", ""),
                            "subject": email["subject"],
                            "snippet": email["snippet"],
                            "attachment_count": len(email["attachments"]),
                            "attachment_names": att_names,
                        }
                    )

        elif output_format == "text":
            output_file = reports_dir / f"email_search_{timestamp}.txt"
            with open(output_file, "w", encoding="utf-8") as f:
                f.write(f"Email Search Results\n")
                f.write(f"Query: {search_query}\n")
                f.write(f"Date: {datetime.now().isoformat()}\n")
                f.write(f"Total Results: {len(emails)}\n")
                f.write("=" * 80 + "\n\n")

                for idx, email in enumerate(emails, 1):
                    f.write(f"[{idx}] {email['subject']}\n")
                    f.write(f"Date: {email['date']}\n")
                    f.write(f"From: {email['from']}\n")
                    f.write(f"To: {email['to']}\n")
                    if email.get("cc"):
                        f.write(f"CC: {email['cc']}\n")
                    if email["attachments"]:
                        f.write(f"Attachments: {', '.join([a['filename'] for a in email['attachments']])}\n")
                    f.write(f"\n{email['snippet']}\n")
                    f.write("-" * 80 + "\n\n")

        elif output_format == "markdown":
            output_file = reports_dir / f"email_search_{timestamp}.md"
            with open(output_file, "w", encoding="utf-8") as f:
                f.write(f"# Email Search Results\n\n")
                f.write(f"**Query:** `{search_query}`  \n")
                f.write(f"**Date:** {datetime.now().isoformat()}  \n")
                f.write(f"**Total Results:** {len(emails)}  \n")
                if summarize:
                    f.write(f"**AI Summaries:** Enabled (Claude Haiku)  \n")
                f.write("\n---\n\n")

                # Always use compact table format
                if show_preview and not summarize:
                    f.write("| Date | From → To | Subject | Preview | Link |\n")
                    f.write("|------|-----------|---------|---------|------|\n")
                else:
                    f.write("| Date | From → To | Subject | Link |\n")
                    f.write("|------|-----------|---------|------|\n")

                for email in emails:
                    # Format date
                    short_date = format_short_date(email['date'])

                    # Extract names
                    from_name = extract_name(email['from'])

                    # Handle multiple recipients
                    to_addresses = email['to'].split(',')
                    to_names = [extract_name(addr.strip()) for addr in to_addresses[:3]]  # Max 3
                    to_text = ", ".join(to_names)
                    if len(to_addresses) > 3:
                        to_text += f" +{len(to_addresses) - 3}"

                    # Build from/to column
                    direction = f"{from_name} → {to_text}"

                    # Gmail web URL
                    gmail_url = f"https://mail.google.com/mail/u/0/#all/{email['id']}"

                    # Write table row
                    # Escape pipe characters in subject and snippet
                    safe_subject = email['subject'].replace('|', '\\|')

                    if show_preview and not summarize:
                        # Truncate snippet to ~100 chars for preview column
                        snippet = email['snippet'][:100] + "..." if len(email['snippet']) > 100 else email['snippet']
                        safe_snippet = snippet.replace('|', '\\|').replace('\n', ' ')
                        f.write(f"| {short_date} | {direction} | {safe_subject} | {safe_snippet} | [View]({gmail_url}) |\n")
                    else:
                        f.write(f"| {short_date} | {direction} | {safe_subject} | [View]({gmail_url}) |\n")

                    # Add AI summary as table rows if available
                    if email.get("ai_summary"):
                        # Each bullet becomes a full-width table row
                        summary_lines = email['ai_summary'].split('\n')
                        for line in summary_lines:
                            if line.strip():
                                stripped = line.strip()
                                # Format overview line with italics
                                if stripped.startswith('- Overview:'):
                                    text = stripped.replace('- Overview:', '- *Overview*:', 1)
                                    # Pad to fill the row width (roughly 140 chars)
                                    f.write(f"|               {text:<125}|\n")
                                else:
                                    # Regular bullet points
                                    f.write(f"|               {stripped:<125}|\n")
                        # Add empty row for spacing
                        f.write(f"|               {'':125}|\n")

        print_header("Export Complete")
        print_success(f"Results saved to: {output_file}")
        print_info(f"Total emails exported: {len(emails)}")
        print_info(f"Format: {output_format.upper()}")

    finally:
        await ops.close()


def main() -> int:
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Search and export Gmail emails",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Quick summary search (fast, metadata only)
  python scripts/email_search.py --domain grandprix.com.au --days-back 180

  # Summary with preview snippets
  python scripts/email_search.py --domain grandprix.com.au --format markdown --show-preview

  # Full detail search (slow, includes body and attachments)
  python scripts/email_search.py --domain grandprix.com.au --detail-level full

  # Search by sender
  python scripts/email_search.py --sender john@example.com --days-back 30

  # Search by subject
  python scripts/email_search.py --subject "Invoice" --days-back 90

  # Custom Gmail query
  python scripts/email_search.py --query "has:attachment larger:5M" --days-back 60

  # Export to different formats
  python scripts/email_search.py --domain example.com --format markdown
  python scripts/email_search.py --domain example.com --format csv
  python scripts/email_search.py --domain example.com --format text
        """,
    )

    # Search filters
    parser.add_argument("--domain", help="Domain to search (e.g., 'example.com')")
    parser.add_argument("--sender", help="Sender email address")
    parser.add_argument("--recipient", help="Recipient email address")
    parser.add_argument("--subject", help="Subject line search term")
    parser.add_argument("--query", help="Raw Gmail query (overrides other filters)")

    # Date range
    parser.add_argument(
        "--days-back", type=int, default=180, help="Days to look back (default: 180)"
    )

    # Output options
    parser.add_argument(
        "--max-results", type=int, default=500, help="Maximum results (default: 500)"
    )
    parser.add_argument(
        "--format",
        choices=["json", "csv", "text", "markdown"],
        default="json",
        help="Output format (default: json)",
    )
    parser.add_argument(
        "--detail-level",
        choices=["summary", "full"],
        default="summary",
        help="Detail level: 'summary' (fast, metadata only) or 'full' (slow, includes body/attachments) (default: summary)",
    )
    parser.add_argument(
        "--show-preview",
        action="store_true",
        help="Show email snippet/preview in summary mode (markdown format only)",
    )
    parser.add_argument(
        "--summarize",
        action="store_true",
        help="Generate AI summaries using Claude API (requires ANTHROPIC_API_KEY in .env, forces full detail level)",
    )

    # Account
    parser.add_argument(
        "--account-id", default="primary", help="Gmail account ID (default: primary)"
    )

    args = parser.parse_args()

    # Validate: must have at least one search criterion
    if not any([args.domain, args.sender, args.recipient, args.subject, args.query]):
        parser.error(
            "Must specify at least one search criterion: --domain, --sender, --recipient, --subject, or --query"
        )

    try:
        asyncio.run(
            search_emails(
                domain=args.domain,
                sender=args.sender,
                recipient=args.recipient,
                subject=args.subject,
                query=args.query,
                days_back=args.days_back,
                max_results=args.max_results,
                account_id=args.account_id,
                output_format=args.format,
                detail_level=args.detail_level,
                show_preview=args.show_preview,
                summarize=args.summarize,
            )
        )
        return 0

    except KeyboardInterrupt:
        print("\n\nSearch cancelled by user")
        return 1
    except Exception as e:
        print(f"\n✗ Error: {e}", file=sys.stderr)
        print("\nMake sure you've completed OAuth2 setup:")
        print("  python scripts/setup_oauth.py")
        return 1


if __name__ == "__main__":
    sys.exit(main())
