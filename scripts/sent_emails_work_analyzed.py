#!/usr/bin/env python
"""Filter and analyze work-related sent emails with AI time estimates."""

import os
import sys
import json
from datetime import datetime
from pathlib import Path
from typing import Optional, List, Dict, Any

# Shared OAuth authentication
from gmail_mcp.auth import get_gmail_service

# Shared utilities
from gmail_mcp.utils import extract_name

# Anthropic for AI
try:
    from anthropic import Anthropic
    ANTHROPIC_AVAILABLE = True
except ImportError:
    ANTHROPIC_AVAILABLE = False


def is_automated_email(to: str, subject: str) -> bool:
    """Check if email is automated/system generated.

    Args:
        to: Recipient email address
        subject: Email subject line

    Returns:
        True if email appears to be automated, False otherwise
    """
    to_lower = to.lower()
    subject_lower = subject.lower()

    # Automated recipient patterns
    automated_recipients = [
        'spam moderators',
        'hosting+',
        'hosting-',
        'unsubscribe',
        'opt-out',
        'noreply',
        'no-reply',
        '@aws.amazon.com',
        'evolution 7 admin',
    ]

    # Automated subject patterns
    automated_subjects = [
        'page speed weekly report',
        'moderator\'s spam report',
        'your receipt from',
        'invoice receipt',
        'payment for your',
        'you have a new invoice',
        'your payment to',
        '[action required]',
        '[action may be required]',
        'action required:',
        'perk alert',
        'welcome to mapbox',
        'mapbox onboarding',
        'activate your',
        'reserve your spot',
        'last chance to join',
        'opportunity to speak',
        'hey mack, opportunity',
        'seminario web',
        'webinar on',
        'join our webinar',
        '1 day left',
        'tomorrow:',
        'boo! it',
    ]

    # Check recipients
    for pattern in automated_recipients:
        if pattern in to_lower:
            return True

    # Check subjects
    for pattern in automated_subjects:
        if pattern in subject_lower:
            return True

    # Check if it's an unsubscribe (long hex string)
    if len(to) > 50 and any(c.isdigit() for c in to):
        return True

    return False


def is_personal_email(to: str, subject: str) -> bool:
    """Check if email is personal (not work).

    Args:
        to: Recipient email address
        subject: Email subject line

    Returns:
        True if email appears to be personal, False otherwise
    """
    to_lower = to.lower()
    subject_lower = subject.lower()

    personal_patterns = [
        'ruth palmer',
        'mia dimitrakopoulos',
        'jasper',
        'amelia',
        'boroondara',
        'bin resize',
        'replace damaged bin',
        'curated spaces',
        'scotch college',
        'stuart.powell@scotch',
        'krampusnacht',
        'barn doors',
        'proposed bar doors',
        '81 cubitt',  # Personal property, not E7 business
        'adam cater',  # Property manager for 81 Cubitt
        'spyros',  # Contractor for 81 Cubitt
        '100 dover',  # Personal property, not E7 business
        'trent stewart',  # Personal property management
        'mark wilson',  # Personal insurance
        'belinda nisbet',  # Personal insurance
        'marina stathakis',  # Personal insurance
        'treehab',  # Not work related
        'yolanda marasco',  # Personal insurance
        'eunice begley',  # Personal insurance
        'starworld cleaning',  # Personal property cleaning
        'jimmy house',  # Personal property maintenance
        'get it gone',  # Personal removalist
        'david palmer',  # Personal (brother)
        'robert a millar',  # Personal (Jasper's school)
        'tim martin',  # Personal (Jasper's school)
        'selling at abbeys',  # Personal (auction)
        'nick ash',  # Personal (finance)
        'greg preston',  # Personal (car)
        'brad martin',  # Personal
        'jane.chen@scotch',  # Personal (school)
    ]

    for pattern in personal_patterns:
        if pattern in to_lower or pattern in subject_lower:
            return True

    return False


def is_work_email(to: str, subject: str) -> bool:
    """Check if email is work-related for Evolution 7.

    Args:
        to: Recipient email address
        subject: Email subject line

    Returns:
        True if email appears to be work-related, False otherwise
    """
    # If it's automated or personal, it's not work
    if is_automated_email(to, subject) or is_personal_email(to, subject):
        return False

    to_lower = to.lower()
    subject_lower = subject.lower()

    # Work indicators
    work_patterns = [
        # Clients
        'barry', 'nilsson', 'bnlaw',
        'tasman', 'brent chong',
        'agpc', 'joel mackenzie', 'australian grand prix',
        'ox2',
        'meet geelong',
        'foxtel',
        'decrolux',
        'tom crampton', 'trusted impact',
        'ruben schwagermann',
        'katie spiteri',
        'jacinda valeontis', 'uniting agewell',
        'kim lisk',
        'danielle zorzer',
        'richard ponsford', 'lws website',
        'jared grace',
        'jane king', 'list g barristers',
        'karan agarwal', 'cox & kings',
        'shivam thakur',
        'aurielle',
        'arijit banerjee',
        'julia langan',
        'scott stuebner',
        'james mcgill',
        'niko ramos',
        'mike nicholas',

        # Team
        'fiona doherty',
        'rom palmas',
        'james richardson',
        'illumin8', 'e7 accounts',
        'thibault',
        'nic garcia', 'nicogapier',
        'varsha',
        'kamila',
        'lachlan rayner',

        # Business operations
        'bill montgomery',
        'inspire9',  # E7 coworking space

        # Projects/enquiries
        'website dev', 'website access',
        'working with us',
        'paid ads services',
        'headless website',
        'evolution 7',
        'e7 &',
    ]

    for pattern in work_patterns:
        if pattern in to_lower or pattern in subject_lower:
            return True

    # Check Evolution 7 domains
    if '@evolution7.com.au' in to_lower and 'hosting' not in to_lower:
        return True

    return False


def analyze_emails_with_ai(emails: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Use AI to summarize and estimate time for emails.

    Args:
        emails: List of email dictionaries with 'to' and 'subject' fields

    Returns:
        Updated list of emails with added 'summary' and 'estimated_minutes' fields
    """
    if not ANTHROPIC_AVAILABLE:
        print("[ERROR] Anthropic library not available")
        for email in emails:
            email['summary'] = "AI analysis not available"
            email['estimated_minutes'] = 15
        return emails

    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        # Try to load from .env
        env_path = Path(__file__).parent.parent / ".env"
        if env_path.exists():
            with open(env_path) as f:
                for line in f:
                    if line.startswith('ANTHROPIC_API_KEY'):
                        api_key = line.split('=')[1].strip().strip('"').strip("'")
                        break

    if not api_key:
        print("[ERROR] ANTHROPIC_API_KEY not found")
        for email in emails:
            email['summary'] = "AI analysis not available"
            email['estimated_minutes'] = 15
        return emails

    client = Anthropic(api_key=api_key)

    print(f"[INFO] Analyzing {len(emails)} emails with AI...")

    # Process in batches of 10
    batch_size = 10
    results = []

    for i in range(0, len(emails), batch_size):
        batch = emails[i:i + batch_size]

        # Build prompt
        emails_text = ""
        for idx, email in enumerate(batch, 1):
            emails_text += f"\n--- Email {idx} ---\n"
            emails_text += f"To: {email['to']}\n"
            emails_text += f"Subject: {email['subject']}\n\n"

        prompt = f"""Analyze these {len(batch)} work emails I sent and for each provide:

1. A brief 1-sentence summary of what the email was about
2. Estimated time to prepare and send (in minutes, rounded to nearest 15 min increment)

Consider:
- Quick replies/forwards: 15 minutes
- Standard business emails: 15-30 minutes
- Complex emails with thought/research: 30-60 minutes
- Detailed proposals/documentation: 60+ minutes

Format EXACTLY as:

Email 1:
Summary: [one sentence]
Time: [number in minutes, must be 15, 30, 45, 60, 75, 90, 105, or 120]

{emails_text}"""

        try:
            response = client.messages.create(
                model="claude-3-haiku-20240307",
                max_tokens=2000,
                messages=[{"role": "user", "content": prompt}]
            )

            response_text = response.content[0].text

            # Parse response
            current_idx = 0
            lines = response_text.split('\n')

            for line in lines:
                line = line.strip()
                if line.startswith('Summary:'):
                    summary = line.replace('Summary:', '').strip()
                    if current_idx < len(batch):
                        batch[current_idx]['summary'] = summary
                elif line.startswith('Time:'):
                    time_str = line.replace('Time:', '').strip()
                    try:
                        time_mins = int(''.join(filter(str.isdigit, time_str)))
                        # Round to nearest 15
                        time_mins = round(time_mins / 15) * 15
                        if time_mins == 0:
                            time_mins = 15
                    except:
                        time_mins = 15

                    if current_idx < len(batch):
                        batch[current_idx]['estimated_minutes'] = time_mins
                        current_idx += 1

            results.extend(batch)
            print(f"[OK] Analyzed batch {i//batch_size + 1}/{(len(emails) + batch_size - 1)//batch_size}")

        except Exception as e:
            print(f"[ERROR] Failed to analyze batch: {e}")
            for email in batch:
                if 'summary' not in email:
                    email['summary'] = "Analysis failed"
                if 'estimated_minutes' not in email:
                    email['estimated_minutes'] = 15
            results.extend(batch)

    return results


def main() -> int:
    """Main function.

    Returns:
        Exit code (0 for success, 1 for error)
    """
    print("=" * 80)
    print("  Work Email Analyzer (October 2025)")
    print("=" * 80)
    print()

    # Get Gmail service
    print("[INFO] Connecting to Gmail API...")
    service = get_gmail_service()
    print("[OK] Connected")

    # Load the existing sent emails export
    project_root = Path(__file__).parent.parent
    reports_dir = project_root / 'reports'

    # Find most recent sent_emails file (exclude temp files and work_emails files)
    sent_files = [f for f in reports_dir.glob('sent_emails_*.md')
                  if '_temp' not in f.name and 'work_emails' not in f.name]
    if not sent_files:
        print("[ERROR] No sent emails report found. Run sent_emails_direct.py first.")
        return 1

    latest_file = max(sent_files, key=lambda p: p.stat().st_mtime)
    print(f"[INFO] Loading emails from: {latest_file.name}")

    # Parse the markdown file to get email list
    emails = []
    with open(latest_file, 'r', encoding='utf-8') as f:
        for line in f:
            if '|' in line and not line.startswith('#') and not line.startswith('**') and not line.startswith('---'):
                parts = line.strip().split('|')
                if len(parts) >= 3:
                    timestamp = parts[0].strip()
                    to = parts[1].strip()
                    subject = parts[2].strip()

                    # Skip empty lines
                    if timestamp and to and subject:
                        emails.append({
                            'timestamp': timestamp,
                            'to': to,
                            'subject': subject
                        })

    print(f"[OK] Loaded {len(emails)} emails")

    # Filter for work emails
    print("[INFO] Filtering for work-related emails...")
    work_emails = []
    for email in emails:
        if is_work_email(email['to'], email['subject']):
            work_emails.append(email)

    print(f"[OK] Found {len(work_emails)} work-related emails")
    print(f"[INFO] Excluded {len(emails) - len(work_emails)} automated/personal emails")

    if not work_emails:
        print("[INFO] No work emails to analyze")
        return 0

    # Analyze with AI
    analyzed_emails = analyze_emails_with_ai(work_emails)

    # Output results
    print()
    print("=" * 80)
    print("  Results")
    print("=" * 80)
    print()

    for email in analyzed_emails:
        timestamp = email['timestamp']
        receiver = email['to']
        subject = email['subject']
        summary = email.get('summary', 'No summary')
        minutes = email.get('estimated_minutes', 15)

        hours = minutes // 60
        mins = minutes % 60
        time_str = f"{hours:02d}:{mins:02d}"

        try:
            print(f"{timestamp} | {receiver} | {subject} | {summary} | {time_str}")
        except UnicodeEncodeError:
            safe_subject = subject.encode('ascii', errors='replace').decode('ascii')
            safe_summary = summary.encode('ascii', errors='replace').decode('ascii')
            print(f"{timestamp} | {receiver} | {safe_subject} | {safe_summary} | {time_str}")

    # Save to file
    timestamp_str = datetime.now().strftime('%Y%m%d_%H%M%S')
    output_file = reports_dir / f'work_emails_analyzed_{timestamp_str}.md'

    with open(output_file, 'w', encoding='utf-8') as f:
        f.write("# Work Emails Analysis - October 2025\n\n")
        f.write(f"**Total Work Emails:** {len(analyzed_emails)}\n")

        total_minutes = sum(e.get('estimated_minutes', 0) for e in analyzed_emails)
        total_hours = total_minutes // 60
        total_mins = total_minutes % 60
        f.write(f"**Estimated Total Time:** {total_hours:02d}:{total_mins:02d}\n\n")
        f.write("---\n\n")

        for email in analyzed_emails:
            timestamp = email['timestamp']
            receiver = email['to']
            subject = email['subject']
            summary = email.get('summary', 'No summary')
            minutes = email.get('estimated_minutes', 15)

            hours = minutes // 60
            mins = minutes % 60
            time_str = f"{hours:02d}:{mins:02d}"

            f.write(f"{timestamp} | {receiver} | {subject} | {summary} | {time_str}\n")

    print()
    print(f"[OK] Saved to: {output_file}")
    print(f"[INFO] Total work emails: {len(analyzed_emails)}")
    print(f"[INFO] Estimated total time: {total_hours:02d}:{total_mins:02d}")

    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print("\n\nCancelled by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n✗ Error: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        sys.exit(1)
