#!/usr/bin/env python
"""Extract sent emails using Gmail API directly (like calendar script)."""

import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional

# Shared OAuth authentication
from gmail_mcp.auth import get_gmail_service

# Shared utilities
from gmail_mcp.utils import extract_name


def main(year: int = 2025, month: int = 10) -> int:
    """Main function."""
    import calendar

    # Get the last day of the month
    last_day = calendar.monthrange(year, month)[1]
    month_name = calendar.month_name[month]

    print("=" * 80)
    print(f"  Sent Emails Extractor ({month_name} {year})")
    print("=" * 80)
    print()

    # Get Gmail service
    print("[INFO] Connecting to Gmail API...")
    service = get_gmail_service()
    print("[OK] Connected")

    # Search for sent emails
    query = f"in:sent after:{year}/{month:02d}/01 before:{year}/{month:02d}/{last_day}"

    print(f"[INFO] Query: {query}")
    print("[INFO] Searching emails...")

    # Get all sent email IDs
    all_messages = []
    page_token = None

    while True:
        results = service.users().messages().list(
            userId='me',
            q=query,
            maxResults=500,
            pageToken=page_token
        ).execute()

        messages = results.get('messages', [])
        all_messages.extend(messages)

        page_token = results.get('nextPageToken')
        if not page_token:
            break

        print(f"[INFO] Found {len(all_messages)} emails so far...")

    print(f"[OK] Found {len(all_messages)} total sent emails")

    if not all_messages:
        print("[INFO] No sent emails found")
        return 0

    # Fetch email details (one at a time to avoid SSL errors)
    print("[INFO] Fetching email details...")
    emails = []

    for i, msg in enumerate(all_messages, 1):
        if i % 10 == 0:
            print(f"[INFO] Progress: {i}/{len(all_messages)}")

        try:
            email = service.users().messages().get(
                userId='me',
                id=msg['id'],
                format='metadata',
                metadataHeaders=['From', 'To', 'Subject', 'Date']
            ).execute()
            emails.append(email)
        except Exception as e:
            print(f"[ERROR] Failed to fetch email {i}: {e}")
            continue

    print(f"[OK] Retrieved {len(emails)} email details")
    print()

    # Output results
    print("=" * 80)
    print("  Results")
    print("=" * 80)
    print()

    for email in emails:
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

        # Handle Unicode for Windows console
        try:
            print(f"{timestamp} | {receiver} | {subject}")
        except UnicodeEncodeError:
            # Replace problematic characters for console output
            safe_subject = subject.encode('ascii', errors='replace').decode('ascii')
            print(f"{timestamp} | {receiver} | {safe_subject}")

    # Save to markdown file
    project_root = Path(__file__).parent.parent
    output_dir = project_root / 'reports'
    output_dir.mkdir(exist_ok=True)
    timestamp_str = datetime.now().strftime('%Y%m%d_%H%M%S')
    output_file = output_dir / f'sent_emails_{year}{month:02d}_{timestamp_str}.md'

    with open(output_file, 'w', encoding='utf-8') as f:
        f.write(f"# Sent Emails - {month_name} {year}\n\n")
        f.write(f"**Total:** {len(emails)} emails\n\n")
        f.write("---\n\n")

        for email in emails:
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
    print(f"[INFO] Total sent emails: {len(emails)}")

    return 0


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Extract sent emails from Gmail")
    parser.add_argument('--year', type=int, default=2025, help='Year (default: 2025)')
    parser.add_argument('--month', type=int, default=10, help='Month (default: 10)')
    args = parser.parse_args()

    try:
        sys.exit(main(year=args.year, month=args.month))
    except KeyboardInterrupt:
        print("\n\nCancelled by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n✗ Error: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        sys.exit(1)
