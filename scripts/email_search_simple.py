#!/usr/bin/env python
"""Simple sequential email search (no batch operations)."""

import asyncio
import json
import sys
from datetime import datetime, timedelta
from pathlib import Path

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root / "src"))

from gmail_mcp.gmail import GmailClient, GmailOperations
from scripts.email_search import extract_email_details


async def search_simple(domain: str, days_back: int = 180):
    """Search emails sequentially (slower but more reliable)."""

    print("\n" + "=" * 80)
    print("  Gmail Email Search (Simple Mode)")
    print("=" * 80 + "\n")

    # Build query
    date_cutoff = datetime.now() - timedelta(days=days_back)
    date_str = date_cutoff.strftime("%Y/%m/%d")
    query = f"after:{date_str} (to:*@{domain} OR from:*@{domain})"

    print(f"[INFO] Query: {query}")
    print(f"[INFO] Connecting to Gmail API...\n")

    client = GmailClient(account_id="primary")
    ops = GmailOperations(client=client)

    try:
        # Search
        results = await ops.search_emails(query=query, page_size=100)
        messages = results.get("messages", [])
        total = len(messages)

        print(f"[OK] Found {total} emails\n")
        print("[INFO] Fetching email details (one at a time)...")
        print("[INFO] This may take a few minutes...\n")

        emails = []
        for idx, msg in enumerate(messages, 1):
            try:
                print(f"  [{idx}/{total}] Fetching {msg['id']}...", end="", flush=True)

                # Fetch one at a time
                email_data = await ops.read_email(msg["id"], format="full")
                details = extract_email_details(email_data)
                emails.append(details)

                print(" OK")

                # Small delay to avoid rate limiting
                await asyncio.sleep(0.2)

            except Exception as e:
                print(f" FAILED: {e}")
                continue

        print(f"\n[OK] Successfully retrieved {len(emails)}/{total} emails\n")

        # Save to JSON
        output_file = f"grandprix_emails_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(output_file, "w", encoding="utf-8") as f:
            json.dump({
                "query": query,
                "date": datetime.now().isoformat(),
                "total": len(emails),
                "emails": emails
            }, f, indent=2, ensure_ascii=False)

        print(f"[OK] Results saved to: {output_file}")

        # Print summary
        print("\n" + "=" * 80)
        print(f"SUMMARY ({len(emails)} emails)")
        print("=" * 80 + "\n")

        for idx, email in enumerate(emails[:10], 1):
            print(f"[{idx}] {email['subject']}")
            print(f"    Date: {email['date']}")
            print(f"    From: {email['from']}")
            print(f"    To: {email['to']}")
            if email['attachments']:
                att_count = len(email['attachments'])
                print(f"    Attachments: {att_count}")
            print()

        if len(emails) > 10:
            print(f"... and {len(emails) - 10} more\n")

        print(f"Full details in: {output_file}\n")

    finally:
        await ops.close()


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--domain", required=True)
    parser.add_argument("--days-back", type=int, default=180)
    args = parser.parse_args()

    asyncio.run(search_simple(args.domain, args.days_back))
