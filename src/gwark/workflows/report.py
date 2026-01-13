"""Report generator for triage workflow."""

from datetime import datetime
from typing import Any, Dict, List

from gwark.core.dates import format_short_date
from gwark.core.email_utils import extract_name


def generate_triage_report(
    account: str,
    since: datetime,
    kept: List[Dict[str, Any]],
    filtered: List[Dict[str, Any]],
    stats: Dict[str, Any],
) -> str:
    """Generate a markdown triage report.

    Args:
        account: Email account analyzed
        since: Start date of analysis
        kept: Emails kept after filtering
        filtered: Emails filtered out
        stats: Workflow statistics

    Returns:
        Markdown formatted report string
    """
    lines = []

    # Header
    lines.append("# Email Triage Report")
    lines.append("")
    lines.append(f"**Account**: {account}")
    lines.append(f"**Period**: {since.strftime('%b %d, %Y')} - {datetime.now().strftime('%b %d, %Y')}")
    lines.append(f"**Generated**: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    lines.append("")

    # Summary table with priority breakdown if available
    lines.append("## Summary")
    lines.append("")
    lines.append("| Category | Count |")
    lines.append("|----------|-------|")

    # Show priority breakdown if stats exist
    if stats.get('urgent', 0) or stats.get('important', 0) or stats.get('respond', 0):
        lines.append(f"| **Urgent** | **{stats.get('urgent', 0)}** |")
        lines.append(f"| **Important** | **{stats.get('important', 0)}** |")
        lines.append(f"| **Respond** | **{stats.get('respond', 0)}** |")
        lines.append(f"| Noise | {stats.get('noise', 0)} |")
        lines.append(f"| Sales | {stats.get('sales', 0)} |")
    else:
        lines.append(f"| Needs Response | {stats.get('needs_response', 0)} |")

    lines.append(f"| Awaiting Reply | {stats.get('awaiting_reply', 0)} |")
    lines.append(f"| Already Replied | {stats.get('replied', 0)} |")
    lines.append(f"| Filtered (rules) | {stats.get('filtered_out', 0)} |")
    lines.append(f"| **Total Analyzed** | **{stats.get('total_fetched', 0)}** |")
    lines.append("")

    # Group emails by status and priority (5-tier: urgent, important, respond, noise, sales)
    needs_response = [e for e in kept if e.get("response_status") == "needs_response"]
    awaiting_reply = [e for e in kept if e.get("response_status") == "awaiting_reply"]
    already_replied = [e for e in kept if e.get("response_status") == "replied"]

    # Needs Response section (with priority breakdown)
    if needs_response:
        lines.append("---")
        lines.append("")
        lines.append(f"## Needs Response ({len(needs_response)})")
        lines.append("")

        # Group by priority (5-tier system)
        urgent = [e for e in needs_response if e.get("ai_priority") == "urgent"]
        important = [e for e in needs_response if e.get("ai_priority") == "important"]
        respond = [e for e in needs_response if e.get("ai_priority") == "respond"]
        noise = [e for e in needs_response if e.get("ai_priority") == "noise"]
        sales = [e for e in needs_response if e.get("ai_priority") == "sales"]
        other = [e for e in needs_response if e.get("ai_priority") not in ("urgent", "important", "respond", "noise", "sales")]

        if urgent:
            lines.append(f"### Urgent ({len(urgent)})")
            lines.append("")
            lines.append("*Act now - deadlines, payment failures, penalties*")
            lines.append("")
            lines.extend(_format_email_table(urgent, include_reason=True, include_summary=True))
            lines.append("")

        if important:
            lines.append(f"### Important ({len(important)})")
            lines.append("")
            lines.append("*Act soon - compliance, approvals, HR matters*")
            lines.append("")
            lines.extend(_format_email_table(important, include_reason=True, include_summary=True))
            lines.append("")

        if respond or other:
            respond_emails = respond + other
            lines.append(f"### Respond ({len(respond_emails)})")
            lines.append("")
            lines.append("*Reply when able - genuine emails from known senders*")
            lines.append("")
            lines.extend(_format_email_table(respond_emails, include_reason=True, include_summary=True))
            lines.append("")

        if noise:
            lines.append(f"### Noise ({len(noise)})")
            lines.append("")
            lines.append("*Archive/ignore - receipts, digests, automated updates*")
            lines.append("")
            lines.append("<details>")
            lines.append("<summary>Click to expand</summary>")
            lines.append("")
            lines.extend(_format_email_table(noise, include_reason=True))
            lines.append("")
            lines.append("</details>")
            lines.append("")

        if sales:
            lines.append(f"### Sales ({len(sales)})")
            lines.append("")
            lines.append("*Bulk delete - cold outreach from unknown senders*")
            lines.append("")
            lines.append("<details>")
            lines.append("<summary>Click to expand</summary>")
            lines.append("")
            lines.extend(_format_email_table(sales, include_reason=True))
            lines.append("")
            lines.append("</details>")
            lines.append("")

    # Awaiting Reply section
    if awaiting_reply:
        lines.append("---")
        lines.append("")
        lines.append(f"## Awaiting Reply ({len(awaiting_reply)})")
        lines.append("")
        lines.append("*Emails you've responded to, waiting for their reply*")
        lines.append("")
        lines.extend(_format_email_table(awaiting_reply, include_reason=False, show_your_reply=True))
        lines.append("")

    # Already Replied section (collapsed)
    if already_replied:
        lines.append("---")
        lines.append("")
        lines.append(f"## Already Replied ({len(already_replied)})")
        lines.append("")
        lines.append("*Emails where you've responded but they sent another message*")
        lines.append("")
        lines.append("<details>")
        lines.append("<summary>Click to expand</summary>")
        lines.append("")
        lines.extend(_format_email_table(already_replied, include_reason=False))
        lines.append("")
        lines.append("</details>")
        lines.append("")

    # Filtered section (collapsed)
    if filtered:
        lines.append("---")
        lines.append("")
        lines.append(f"## Filtered ({len(filtered)})")
        lines.append("")
        lines.append("*Auto-filtered by rules (notifications, newsletters)*")
        lines.append("")
        lines.append("<details>")
        lines.append("<summary>Click to expand</summary>")
        lines.append("")
        lines.extend(_format_filtered_table(filtered))
        lines.append("")
        lines.append("</details>")
        lines.append("")

    return "\n".join(lines)


def _format_email_table(
    emails: List[Dict[str, Any]],
    include_reason: bool = False,
    include_summary: bool = False,
    show_your_reply: bool = False,
) -> List[str]:
    """Format emails as a markdown table.

    Args:
        emails: List of email dicts
        include_reason: Show AI reasoning column
        include_summary: Show AI summary below each row (for actionable emails)
        show_your_reply: Show date of your reply
    """
    lines = []

    if include_reason:
        lines.append("| Date | From | Subject | Why | Link |")
        lines.append("|------|------|---------|-----|------|")
    elif show_your_reply:
        lines.append("| Date | From | Subject | Your Reply | Link |")
        lines.append("|------|------|---------|------------|------|")
    else:
        lines.append("| Date | From | Subject | Link |")
        lines.append("|------|------|---------|------|")

    for email in emails:
        date = format_short_date(email.get("date", ""))
        from_name = extract_name(email.get("from", ""))[:25]
        subject = email.get("subject", "No Subject").replace("|", "\\|")[:50]
        email_id = email.get("id", "")
        link = f"[View](https://mail.google.com/mail/u/0/#all/{email_id})"

        if include_reason:
            reason = email.get("ai_reasoning", "")[:30]
            lines.append(f"| {date} | {from_name} | {subject} | {reason} | {link} |")
        elif show_your_reply:
            reply_date = format_short_date(email.get("user_last_replied", ""))
            lines.append(f"| {date} | {from_name} | {subject} | {reply_date} | {link} |")
        else:
            lines.append(f"| {date} | {from_name} | {subject} | {link} |")

        # Add summary line for actionable emails
        if include_summary:
            summary = email.get("ai_summary")
            if summary:
                lines.append(f"| | | *{summary}* | | |")

    return lines


def _format_filtered_table(emails: List[Dict[str, Any]]) -> List[str]:
    """Format filtered emails as a markdown table with filter reason."""
    lines = []
    lines.append("| Date | From | Subject | Filter |")
    lines.append("|------|------|---------|--------|")

    for email in emails[:50]:  # Limit to 50 for readability
        date = format_short_date(email.get("date", ""))
        from_name = extract_name(email.get("from", ""))[:20]
        subject = email.get("subject", "No Subject").replace("|", "\\|")[:40]
        reason = email.get("filter_reason", "rule")

        lines.append(f"| {date} | {from_name} | {subject} | {reason} |")

    if len(emails) > 50:
        lines.append(f"| ... | ... | *{len(emails) - 50} more filtered* | ... |")

    return lines
