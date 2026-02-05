"""Batch email summarization for interactive mode.

This module provides batch email summarization without requiring API keys,
by formatting emails for Claude Code to process interactively.
"""

import json
from pathlib import Path
from typing import List, Dict, Any


def prepare_batch_for_summary(emails: List[Dict[str, Any]], batch_size: int = 10) -> List[List[Dict[str, Any]]]:
    """Split emails into batches for summarization.

    Args:
        emails: List of email dictionaries
        batch_size: Number of emails per batch (default: 10)

    Returns:
        List of email batches
    """
    batches = []
    for i in range(0, len(emails), batch_size):
        batches.append(emails[i:i + batch_size])
    return batches


def format_batch_for_claude(batch: List[Dict[str, Any]], batch_num: int, total_batches: int) -> str:
    """Format a batch of emails for Claude to summarize.

    Args:
        batch: List of email dictionaries
        batch_num: Current batch number (1-indexed)
        total_batches: Total number of batches

    Returns:
        Formatted prompt string
    """
    lines = [
        f"# Email Batch {batch_num}/{total_batches}",
        "",
        "Please provide a 4-5 line summary for each email below, focusing on:",
        "- Key action items or decisions",
        "- Important information or requests",
        "- Relevant context or deadlines",
        "",
        "Respond with a JSON array of summaries in this exact format:",
        '[',
        '  {"id": "email_id_here", "summary": "4-5 line summary here"},',
        '  ...',
        ']',
        "",
        "---",
        ""
    ]

    for idx, email in enumerate(batch, 1):
        # Get body text
        body = email.get('body_full') or email.get('body_preview') or email.get('snippet', '')
        body = body[:1500] if len(body) > 1500 else body

        # Get attachments (filter out signature images)
        attachments = email.get('attachments', [])
        real_attachments = [
            att for att in attachments
            if att.get('size', 0) > 100000  # >100KB, likely not signature
            or att.get('mimeType', '').startswith('application/')  # Documents
            or att.get('filename', '').endswith(('.pdf', '.doc', '.docx', '.xls', '.xlsx', '.zip'))
        ]

        lines.append(f"## Email {idx}")
        lines.append(f"**ID:** `{email.get('id', '')}`")
        lines.append(f"**From:** {email.get('from', 'Unknown')}")
        lines.append(f"**To:** {email.get('to', 'Unknown')}")
        lines.append(f"**Date:** {email.get('date', '')}")
        lines.append(f"**Subject:** {email.get('subject', 'No Subject')}")

        if real_attachments:
            att_list = ', '.join([f"{a.get('filename', 'Unknown')} ({a.get('mimeType', 'unknown')})" for a in real_attachments])
            lines.append(f"**Attachments:** {att_list}")

        lines.append(f"**Body:**")
        lines.append(body)
        lines.append("")
        lines.append("---")
        lines.append("")

    return "\n".join(lines)


def parse_claude_response(response_text: str) -> List[Dict[str, str]]:
    """Parse Claude's JSON response containing summaries.

    Args:
        response_text: JSON array string from Claude

    Returns:
        List of summary dictionaries with 'id' and 'summary' keys
    """
    # Find JSON array in response
    text = response_text.strip()
    start = text.find('[')
    end = text.rfind(']') + 1

    if start >= 0 and end > start:
        json_str = text[start:end]
        try:
            summaries = json.loads(json_str)
            if isinstance(summaries, list):
                return summaries
        except json.JSONDecodeError as e:
            raise ValueError(f"Failed to parse JSON response: {e}")

    raise ValueError("No valid JSON array found in response")


def apply_summaries_to_emails(emails: List[Dict[str, Any]], summaries: List[Dict[str, str]]) -> None:
    """Apply summaries to emails by matching IDs.

    Args:
        emails: List of email dictionaries (modified in place)
        summaries: List of summary dictionaries with 'id' and 'summary'
    """
    # Create ID -> summary lookup
    summary_map = {s['id']: s['summary'] for s in summaries}

    # Apply to emails
    for email in emails:
        email_id = email.get('id')
        if email_id in summary_map:
            email['ai_summary'] = summary_map[email_id]
            email['ai_method'] = 'interactive'  # Track that this was batch/interactive mode


def save_summarized_emails(emails: List[Dict[str, Any]], output_path: Path) -> None:
    """Save emails with summaries to JSON file.

    Args:
        emails: List of email dictionaries with ai_summary field
        output_path: Path to save JSON file
    """
    output_data = {
        "data": emails,
        "meta": {
            "total": len(emails),
            "summarized": sum(1 for e in emails if e.get('ai_summary')),
            "method": "interactive"
        }
    }

    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(output_data, f, indent=2, ensure_ascii=False)


def create_enhanced_report(emails: List[Dict[str, Any]], output_path: Path) -> None:
    """Create markdown report with summaries and attachments.

    Args:
        emails: List of email dictionaries with ai_summary field
        output_path: Path to save markdown report
    """
    from gwark.core.dates import format_short_date
    from gwark.core.email_utils import extract_name
    from datetime import datetime

    lines = []
    lines.append("# Email Report with AI Summaries\n")
    lines.append(f"**Generated:** {datetime.now().strftime('%Y-%m-%d %H:%M')}\n")
    lines.append(f"**Total Emails:** {len(emails)}\n")
    lines.append("")

    # Table header
    lines.append("| Date | From | Subject | Summary | Attachments | Link |")
    lines.append("|------|------|---------|---------|-------------|------|")

    for email in emails:
        date = format_short_date(email.get('date', ''))
        from_name = extract_name(email.get('from', ''))
        subject = email.get('subject', 'No Subject').replace('|', '\\|')[:60]
        summary = email.get('ai_summary', '').replace('|', '\\|').replace('\n', ' ')[:200]
        email_id = email.get('id', '')
        link = f"[View](https://mail.google.com/mail/u/0/#all/{email_id})"

        # Filter attachments (exclude signature images)
        attachments = email.get('attachments', [])
        real_attachments = [
            att for att in attachments
            if att.get('size', 0) > 100000  # >100KB
            or att.get('mimeType', '').startswith('application/')
            or att.get('filename', '').endswith(('.pdf', '.doc', '.docx', '.xls', '.xlsx', '.zip', '.ics'))
        ]

        if real_attachments:
            att_text = ', '.join([a.get('filename', 'Unknown') for a in real_attachments])
        else:
            att_text = 'None'

        lines.append(f"| {date} | {from_name} | {subject} | {summary} | {att_text} | {link} |")

    lines.append("")
    lines.append("---")
    lines.append(f"\n*Summaries generated in interactive batch mode*")

    with open(output_path, 'w', encoding='utf-8') as f:
        f.write('\n'.join(lines))


# Workflow instructions for CLI command
USAGE_INSTRUCTIONS = """
# Interactive Batch Email Summarization

Summarize emails without an API key using Claude Code interactive mode.

## Usage:

1. Export emails to JSON:
   gwark email search --domain example.com --days 120 --format json -o emails.json

2. Run interactive summarization:
   gwark email summarize emails.json --interactive

3. Claude receives emails in batches and generates summaries
4. Enhanced report generated automatically

## Advantages:
- No API key required (uses Claude Code session)
- Batch processing for large email sets
- Interactive review and control
"""
