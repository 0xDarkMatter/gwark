"""Email classification using Claude API for priority and category triage."""

import json
import os
from pathlib import Path
from typing import List, Dict, Optional, Any

from anthropic import Anthropic

# Load environment variables from .env file
try:
    from dotenv import load_dotenv
    env_path = Path(__file__).parent.parent.parent.parent / ".env"
    load_dotenv(dotenv_path=env_path)
except ImportError:
    pass


CLASSIFICATION_PROMPT = """Classify each email by priority. Respond with JSON only.

Priority levels (5-tier system):
- urgent: Deadlines within days, payment failures, penalties, ATO notices, service at risk - ACT NOW
- important: Compliance matters, tax/BAS, HR issues, account closures, approval requests - ACT SOON
- respond: Genuine emails from known/prior senders that warrant a reply - REPLY WHEN ABLE
- noise: Receipts, digests, newsletters, project updates, automated notifications - ARCHIVE/IGNORE
- sales: Cold outreach from unknown senders, LinkedIn sales, lead gen pitches, M&A spam - BULK DELETE

SENDER QUALITY SIGNALS:
- "known" = sender is in Google Contacts → likely respond/important, NOT sales
- "prior" = user has previously emailed this sender → likely genuine, NOT sales
- "unknown" = no prior relationship → likely sales or noise

GMAIL CATEGORY SIGNALS:
- "Primary" = Gmail thinks it's important → more likely respond/important/urgent
- "Updates" = automated updates → strong signal for noise
- "Promotions" = marketing → should have been filtered, but if here → noise or sales
- "Social" = social notifications → noise
- "Forums" = mailing lists → noise

Key distinctions:
- "respond" = real person expecting a reply (known/prior sender, Primary tab, conversational)
- "noise" = automated stuff that isn't spam (receipts, digests, tool notifications, Updates tab)
- "sales" = unknown sender trying to sell/pitch something
- Newsletters from tools → noise (unless critical service notice → important)
- Unknown sender + partnership/M&A/services pitch → sales
- Prior sender + genuine M&A interest → important

For each email, provide:
{
  "priority": "urgent|important|respond|noise|sales",
  "reasoning": "Brief 5-10 word explanation",
  "summary": "For urgent/important/respond only: 1-2 sentence summary of what's needed. Null for noise/sales."
}

Respond with a JSON array of classifications, one per email in order.
"""


def classify_emails(
    emails: List[Dict[str, Any]],
    api_key: Optional[str] = None,
    batch_size: int = 10,
) -> List[Dict[str, Any]]:
    """Classify emails by priority using Claude Sonnet (5-tier system).

    Args:
        emails: List of email dictionaries with 'subject', 'from', 'to', 'snippet'
        api_key: Anthropic API key (reads from ANTHROPIC_API_KEY if not provided)
        batch_size: Number of emails to classify per API call (default: 10)

    Returns:
        List of email dicts with added fields:
        - ai_priority: "urgent" | "important" | "respond" | "noise" | "sales"
        - ai_reasoning: Brief explanation
        - ai_summary: 1-2 sentence summary (only for urgent/important/respond)

    Priority definitions:
        - urgent: Deadlines, payment failures, penalties - act now
        - important: Compliance, approvals, HR - act soon
        - respond: Genuine emails from known senders - reply when able
        - noise: Receipts, digests, automated updates - archive/ignore
        - sales: Cold outreach from unknown senders - bulk delete

    Raises:
        ValueError: If no API key is provided or found in environment
    """
    if api_key is None:
        api_key = os.getenv("ANTHROPIC_API_KEY")

    if not api_key:
        raise ValueError("No API key provided. Set ANTHROPIC_API_KEY environment variable.")

    client: Anthropic = Anthropic(api_key=api_key)

    for i in range(0, len(emails), batch_size):
        batch = emails[i:i + batch_size]
        _classify_batch(client, batch)

    return emails


def _classify_batch(client: Anthropic, batch: List[Dict[str, Any]]) -> None:
    """Classify a batch of emails."""
    # Build email list for prompt
    email_texts = []
    for idx, email in enumerate(batch, 1):
        body = email.get("body_preview") or email.get("snippet", "")
        body = body[:500] if len(body) > 500 else body  # Shorter for classification

        # Include sender quality signal if available
        sender_quality = email.get("sender_quality", "unknown")

        # Include Gmail category if available
        gmail_category = email.get("gmail_category", "Primary")

        email_texts.append(
            f"Email {idx}:\n"
            f"From: {email.get('from', 'Unknown')}\n"
            f"To: {email.get('to', 'Unknown')}\n"
            f"Subject: {email.get('subject', 'No Subject')}\n"
            f"Sender Quality: {sender_quality}\n"
            f"Gmail Category: {gmail_category}\n"
            f"Preview: {body}\n"
        )

    prompt = CLASSIFICATION_PROMPT + "\n\nEmails to classify:\n\n" + "\n".join(email_texts)

    print(f"[INFO] Classifying batch of {len(batch)} emails...")

    try:
        message = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=4000,
            messages=[{"role": "user", "content": prompt}],
        )

        response_text = message.content[0].text

        # Parse JSON response
        classifications = _parse_classifications(response_text, len(batch))

        # Apply to emails
        for email, classification in zip(batch, classifications):
            email["ai_priority"] = classification.get("priority", "noise")
            email["ai_reasoning"] = classification.get("reasoning", "")
            email["ai_summary"] = classification.get("summary")  # None for noise/sales

        print(f"[OK] Successfully classified {len(batch)} emails")

    except Exception as e:
        print(f"[ERROR] Failed to classify batch: {e}")
        # Set defaults on failure
        for email in batch:
            email["ai_priority"] = "noise"
            email["ai_reasoning"] = f"[Classification failed: {str(e)}]"
            email["ai_summary"] = None


def _parse_classifications(response_text: str, expected_count: int) -> List[Dict[str, Any]]:
    """Parse JSON classifications from response text."""
    # Try to find JSON array in response
    text = response_text.strip()

    # Find the JSON array
    start = text.find("[")
    end = text.rfind("]") + 1

    if start >= 0 and end > start:
        json_str = text[start:end]
        try:
            result = json.loads(json_str)
            if isinstance(result, list):
                # Pad or trim to expected count
                while len(result) < expected_count:
                    result.append({"priority": "informational", "reasoning": "No classification"})
                return result[:expected_count]
        except json.JSONDecodeError:
            pass

    # Fallback: return defaults
    return [{"priority": "informational", "reasoning": "Parse error"}] * expected_count


def get_priority_order(priority: str) -> int:
    """Get numeric order for priority (lower = more urgent)."""
    order = {"urgent": 0, "important": 1, "respond": 2, "noise": 3, "sales": 4}
    return order.get(priority, 3)


def sort_by_priority(emails: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Sort emails by priority (urgent first)."""
    return sorted(emails, key=lambda e: get_priority_order(e.get("ai_priority", "informational")))


def group_by_priority(emails: List[Dict[str, Any]]) -> Dict[str, List[Dict[str, Any]]]:
    """Group emails by priority level (5-tier system)."""
    groups: Dict[str, List[Dict[str, Any]]] = {
        "urgent": [],
        "important": [],
        "respond": [],
        "noise": [],
        "sales": [],
    }

    for email in emails:
        priority = email.get("ai_priority", "noise")
        if priority in groups:
            groups[priority].append(email)
        else:
            groups["noise"].append(email)

    return groups
