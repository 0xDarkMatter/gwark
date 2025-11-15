#!/usr/bin/env python
"""Simple sent email extractor without AI analysis."""

import asyncio
import base64
import sys
from datetime import datetime
from pathlib import Path

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
from gmail_mcp.utils import extract_name


async def main():
    """Main function to extract sent emails."""
    print("=" * 80)
    print("  Sent Email Extractor (October 2025)")
    print("=" * 80)
    print()

    # October 2025
    start_date = datetime(2025, 10, 1)
    end_date = datetime(2025, 10, 31, 23, 59, 59)

    print(f"[INFO] Date range: {start_date.strftime('%Y-%m-%d')} to {end_date.strftime('%Y-%m-%d')}")
    print()

    # Initialize Gmail client
    client = GmailClient()
    ops = GmailOperations(client)

    # Search query
    query = f"in:sent after:{start_date.strftime('%Y/%m/%d')} before:{end_date.strftime('%Y/%m/%d')}"

    print(f"[INFO] Query: {query}")
    print("[INFO] Searching...")

    # Search (set high limit)
    result = await ops.search_emails(query=query, max_results=1000)

    messages = result.get("messages", [])
    print(f"[OK] Found {len(messages)} sent emails")

    if not messages:
        print("[INFO] No sent emails found")
        return 0

    # Fetch full details in batches of 50
    print(f"[INFO] Fetching email details...")
    batch_ops = BatchOperations(client, max_concurrent=2)  # Reduced concurrency to avoid SSL errors
    message_ids = [msg["id"] for msg in messages]

    all_emails = []
    batch_size = 50

    for i in range(0, len(message_ids), batch_size):
        batch_ids = message_ids[i:i + batch_size]
        batch_num = i//batch_size + 1
        total_batches = (len(message_ids) + batch_size - 1)//batch_size
        print(f"[INFO] Batch {batch_num}/{total_batches}")

        try:
            batch_result = await batch_ops.batch_read(batch_ids, format="full")
            emails_batch = list(batch_result.get("successful", {}).values())
            all_emails.extend(emails_batch)
            print(f"[OK] Batch {batch_num} complete - {len(emails_batch)} emails")
        except Exception as e:
            print(f"[ERROR] Batch {batch_num} failed: {e}")
            # Continue with next batch

        # Add small delay between batches
        await asyncio.sleep(1)

    print(f"[OK] Retrieved {len(all_emails)} emails total")
    print()

    # Extract and display
    print("=" * 80)
    print("  Results")
    print("=" * 80)
    print()

    for email in all_emails:
        headers = {h['name'].lower(): h['value'] for h in email.get('payload', {}).get('headers', [])}

        # Parse date
        try:
            from email.utils import parsedate_to_datetime
            parsed_date = parsedate_to_datetime(headers.get('date', ''))
            timestamp = parsed_date.strftime("%d/%m/%Y %H:%M")
        except:
            timestamp = headers.get('date', 'Unknown')

        receiver = extract_name(headers.get('to', ''))
        subject = headers.get('subject', 'No Subject')

        print(f"{timestamp} | {receiver} | {subject}")

    # Save to file in markdown format
    output_dir = project_root / 'reports'
    output_dir.mkdir(exist_ok=True)
    timestamp_str = datetime.now().strftime('%Y%m%d_%H%M%S')
    output_file = output_dir / f'sent_emails_{timestamp_str}.md'

    with open(output_file, 'w', encoding='utf-8') as f:
        f.write("# Sent Emails - October 2025\n\n")
        f.write(f"**Total:** {len(all_emails)} emails\n\n")
        f.write("---\n\n")

        for email in all_emails:
            headers = {h['name'].lower(): h['value'] for h in email.get('payload', {}).get('headers', [])}

            try:
                from email.utils import parsedate_to_datetime
                parsed_date = parsedate_to_datetime(headers.get('date', ''))
                timestamp = parsed_date.strftime("%d/%m/%Y %H:%M")
            except:
                timestamp = headers.get('date', 'Unknown')

            receiver = extract_name(headers.get('to', ''))
            subject = headers.get('subject', 'No Subject')

            f.write(f"{timestamp} | {receiver} | {subject}\n")

    print()
    print(f"[OK] Saved to: {output_file}")
    print(f"[INFO] Total sent emails: {len(all_emails)}")

    return 0


if __name__ == "__main__":
    try:
        exit_code = asyncio.run(main())
        sys.exit(exit_code)
    except KeyboardInterrupt:
        print("\n\nCancelled by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n✗ Error: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        sys.exit(1)
