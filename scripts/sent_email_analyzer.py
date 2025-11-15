#!/usr/bin/env python
"""Analyze sent emails with AI-powered time estimation.

Extracts sent emails and estimates preparation time for each one.
"""

import asyncio
import argparse
import base64
import json
import os
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Dict, Optional

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

# Anthropic for AI analysis
try:
    from anthropic import Anthropic
    ANTHROPIC_AVAILABLE = True
except ImportError:
    ANTHROPIC_AVAILABLE = False


def extract_email_body(email_data: dict) -> str:
    """Extract email body from email data."""
    payload = email_data.get("payload", {})

    def get_body_from_part(part):
        """Recursively extract body from email parts."""
        if "parts" in part:
            # Multipart email
            for subpart in part["parts"]:
                body = get_body_from_part(subpart)
                if body:
                    return body
        else:
            # Single part
            mime_type = part.get("mimeType", "")
            if mime_type == "text/plain" or mime_type == "text/html":
                body_data = part.get("body", {}).get("data", "")
                if body_data:
                    decoded = base64.urlsafe_b64decode(body_data).decode("utf-8", errors="ignore")
                    return decoded
        return ""

    body = get_body_from_part(payload)

    # Limit body length for AI processing
    if len(body) > 3000:
        body = body[:3000]

    return body


async def analyze_sent_emails_with_ai(emails: List[dict]) -> List[dict]:
    """Use AI to summarize emails and estimate preparation time.

    Args:
        emails: List of email data dictionaries

    Returns:
        List of emails with added 'summary' and 'estimated_time' fields
    """
    if not ANTHROPIC_AVAILABLE:
        print("[ERROR] Anthropic library not available. Install with: pip install anthropic")
        return emails

    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        print("[ERROR] ANTHROPIC_API_KEY not found in .env file")
        return emails

    client = Anthropic(api_key=api_key)

    print(f"[INFO] Analyzing {len(emails)} emails with AI...")

    # Process in batches of 5 for efficiency
    batch_size = 5
    results = []

    for i in range(0, len(emails), batch_size):
        batch = emails[i:i + batch_size]

        # Prepare batch prompt
        emails_text = ""
        for idx, email in enumerate(batch, 1):
            subject = email.get('subject', 'No Subject')
            body = email.get('body', '')[:2000]  # Limit body
            to = email.get('to', 'Unknown')

            emails_text += f"\n--- Email {idx} ---\n"
            emails_text += f"To: {to}\n"
            emails_text += f"Subject: {subject}\n"
            emails_text += f"Body: {body}\n"

        # AI prompt
        prompt = f"""Analyze these {len(batch)} sent emails and for each one provide:
1. A brief 1-sentence summary of what the email is about
2. An estimate of how long it would have taken to prepare and send this email (in minutes)

Consider factors like:
- Email complexity and length
- Whether it required research or thought
- Number of recipients
- Formality and care needed
- Whether it's a quick reply or original composition

Format your response EXACTLY as follows for each email:

Email 1:
Summary: [one sentence summary]
Time: [number in minutes, must be a multiple of 15: 15, 30, 45, 60, 75, 90, etc.]

Email 2:
Summary: [one sentence summary]
Time: [number in minutes, multiple of 15]

Here are the emails:
{emails_text}"""

        try:
            response = client.messages.create(
                model="claude-3-haiku-20240307",
                max_tokens=2000,
                messages=[{
                    "role": "user",
                    "content": prompt
                }]
            )

            # Parse response
            response_text = response.content[0].text

            # Extract summaries and times
            current_email_idx = 0
            lines = response_text.split('\n')

            for line in lines:
                line = line.strip()
                if line.startswith('Summary:'):
                    summary = line.replace('Summary:', '').strip()
                    if current_email_idx < len(batch):
                        batch[current_email_idx]['summary'] = summary
                elif line.startswith('Time:'):
                    time_str = line.replace('Time:', '').strip()
                    # Extract number from string
                    time_mins = int(''.join(filter(str.isdigit, time_str)))
                    if current_email_idx < len(batch):
                        batch[current_email_idx]['estimated_minutes'] = time_mins
                        current_email_idx += 1

            results.extend(batch)
            print(f"[OK] Processed batch {i//batch_size + 1}/{(len(emails) + batch_size - 1)//batch_size}")

        except Exception as e:
            print(f"[ERROR] Failed to analyze batch: {e}")
            # Add defaults for failed emails
            for email in batch:
                email['summary'] = "Unable to analyze"
                email['estimated_minutes'] = 15
            results.extend(batch)

    return results


async def main(
    days_back: int = 30,
    max_results: int = 100,
    output_file: Optional[str] = None
) -> int:
    """Main function to analyze sent emails.

    Args:
        days_back: Number of days to look back
        max_results: Maximum number of emails to retrieve
        output_file: Optional output file path
    """
    print("=" * 80)
    print("  Sent Email Analyzer with AI Time Estimation")
    print("=" * 80)
    print()

    # Calculate date range for October 2025
    # Hardcode October 2025 for now
    start_date = datetime(2025, 10, 1)
    end_date = datetime(2025, 10, 31, 23, 59, 59)

    print(f"[INFO] Searching sent emails from {start_date.strftime('%Y-%m-%d')} to {end_date.strftime('%Y-%m-%d')}")
    print(f"[INFO] Max results: {max_results}")
    print()

    # Initialize Gmail client
    client = GmailClient()
    ops = GmailOperations(client)

    # Build search query for sent emails in October
    query = f"in:sent after:{start_date.strftime('%Y/%m/%d')} before:{end_date.strftime('%Y/%m/%d')}"

    print(f"[INFO] Search query: {query}")
    print("[INFO] Searching emails...")

    # Search for emails (gets message IDs only)
    result = await ops.search_emails(
        query=query,
        max_results=max_results
    )

    messages = result.get("messages", [])
    print(f"[OK] Found {len(messages)} sent emails")

    if not messages:
        print("[INFO] No sent emails found in the specified period")
        return 0

    # Get full email details using batch operations
    # Split into batches of 50 (max batch size)
    print(f"[INFO] Fetching full email details...")
    batch_ops = BatchOperations(client)
    message_ids = [msg["id"] for msg in messages]

    all_emails = []
    all_failed = {}
    batch_size = 50

    for i in range(0, len(message_ids), batch_size):
        batch_ids = message_ids[i:i + batch_size]
        print(f"[INFO] Processing batch {i//batch_size + 1}/{(len(message_ids) + batch_size - 1)//batch_size}")

        batch_result = await batch_ops.batch_read(batch_ids, format="full")
        emails_batch = list(batch_result.get("successful", {}).values())
        failed_batch = batch_result.get("failed", {})

        all_emails.extend(emails_batch)
        all_failed.update(failed_batch)

    emails = all_emails

    if all_failed:
        print(f"[WARNING] Failed to fetch {len(all_failed)} emails")

    print(f"[OK] Retrieved {len(emails)} full email details")

    if not emails:
        print("[INFO] No sent emails found in the specified period")
        return 0

    # Extract relevant data
    extracted_emails = []
    for email in emails:
        headers = {h['name'].lower(): h['value'] for h in email.get('payload', {}).get('headers', [])}

        email_data = {
            'date': headers.get('date', ''),
            'to': extract_name(headers.get('to', '')),
            'to_email': headers.get('to', ''),
            'subject': headers.get('subject', 'No Subject'),
            'body': extract_email_body(email)
        }
        extracted_emails.append(email_data)

    # Analyze with AI
    analyzed_emails = await analyze_sent_emails_with_ai(extracted_emails)

    # Sort by date
    analyzed_emails.sort(key=lambda x: x.get('date', ''))

    # Output results
    print()
    print("=" * 80)
    print("  Results")
    print("=" * 80)
    print()

    for email in analyzed_emails:
        # Parse date
        try:
            from email.utils import parsedate_to_datetime
            parsed_date = parsedate_to_datetime(email.get('date', ''))
            timestamp = parsed_date.strftime("%d/%m/%Y %H:%M")
        except:
            timestamp = email.get('date', 'Unknown')

        receiver = email.get('to', 'Unknown')
        subject = email.get('subject', 'No Subject')
        summary = email.get('summary', 'No summary')
        minutes = email.get('estimated_minutes', 15)

        # Convert minutes to hh:mm format
        hours = minutes // 60
        mins = minutes % 60
        time_str = f"{hours:02d}:{mins:02d}"

        print(f"{timestamp} | {receiver} | {subject} | {summary} | {time_str}")

    # Save to file if requested
    if output_file:
        output_path = Path(output_file)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        with open(output_path, 'w', encoding='utf-8') as f:
            f.write("# Sent Email Analysis Report\n\n")
            f.write(f"**Date Range:** {start_date.strftime('%Y-%m-%d')} to {end_date.strftime('%Y-%m-%d')}  \n")
            f.write(f"**Total Emails:** {len(analyzed_emails)}  \n\n")
            f.write("---\n\n")

            total_minutes = sum(e.get('estimated_minutes', 0) for e in analyzed_emails)
            total_hours = total_minutes // 60
            total_mins = total_minutes % 60
            f.write(f"**Total Time Spent:** {total_hours:02d}:{total_mins:02d}\n\n")
            f.write("---\n\n")

            for email in analyzed_emails:
                try:
                    from email.utils import parsedate_to_datetime
                    parsed_date = parsedate_to_datetime(email.get('date', ''))
                    timestamp = parsed_date.strftime("%d/%m/%Y %H:%M")
                except:
                    timestamp = email.get('date', 'Unknown')

                receiver = email.get('to', 'Unknown')
                subject = email.get('subject', 'No Subject')
                summary = email.get('summary', 'No summary')
                minutes = email.get('estimated_minutes', 15)

                hours = minutes // 60
                mins = minutes % 60
                time_str = f"{hours:02d}:{mins:02d}"

                f.write(f"{timestamp} | {receiver} | {subject} | {summary} | {time_str}\n")

        print()
        print(f"[OK] Results saved to: {output_path}")

    return 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Analyze sent emails with AI time estimation"
    )

    parser.add_argument(
        '--days-back',
        type=int,
        default=30,
        help='Number of days to look back (default: 30)'
    )

    parser.add_argument(
        '--max-results',
        type=int,
        default=100,
        help='Maximum number of emails to retrieve (default: 100)'
    )

    parser.add_argument(
        '--output',
        type=str,
        help='Output file path (default: reports/sent_emails_TIMESTAMP.md)'
    )

    args = parser.parse_args()

    # Generate output file if not specified
    output_file = args.output
    if not output_file:
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        output_file = f"reports/sent_emails_{timestamp}.md"

    try:
        exit_code = asyncio.run(main(
            days_back=args.days_back,
            max_results=args.max_results,
            output_file=output_file
        ))
        sys.exit(exit_code)
    except KeyboardInterrupt:
        print("\n\nAnalysis cancelled by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n✗ Error: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        sys.exit(1)
