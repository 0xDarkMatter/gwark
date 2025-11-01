#!/usr/bin/env python
"""Email summarization using Claude API."""

import os
from pathlib import Path
from typing import List, Dict, Optional, Any
from anthropic import Anthropic

# Load environment variables from .env file
try:
    from dotenv import load_dotenv
    # Load from project root
    env_path = Path(__file__).parent.parent.parent.parent / ".env"
    load_dotenv(dotenv_path=env_path)
except ImportError:
    # python-dotenv not installed, will rely on system env vars
    pass


def batch_summarize_emails(
    emails: List[Dict[str, Any]],
    api_key: Optional[str] = None,
    batch_size: int = 10
) -> List[Dict[str, Any]]:
    """Summarize emails in batches using Claude API.

    Args:
        emails: List of email dictionaries with 'subject', 'from', 'to', 'body_preview' or 'body_full'
        api_key: Anthropic API key (reads from ANTHROPIC_API_KEY env var if not provided)
        batch_size: Number of emails to summarize per API call (default: 10)

    Returns:
        List of email dicts with added 'ai_summary' field

    Raises:
        ValueError: If no API key is provided or found in environment
    """
    # Get API key
    if api_key is None:
        api_key = os.getenv("ANTHROPIC_API_KEY")

    if not api_key:
        raise ValueError("No API key provided. Set ANTHROPIC_API_KEY environment variable or pass api_key parameter.")

    # Initialize Claude client
    client: Anthropic = Anthropic(api_key=api_key)

    # Process emails in batches
    for i in range(0, len(emails), batch_size):
        batch: List[Dict[str, Any]] = emails[i:i + batch_size]

        # Build prompt for batch
        prompt_parts: List[str] = [
            "Summarize each email below. For each email:\n",
            "1. Write 1-2 sentence overview starting with '- Overview:'\n",
            "2. Then list 2-4 key points as bullets (start each with '- ')\n",
            "3. Label each email as 'Email 1:', 'Email 2:', etc.\n",
            "Do NOT add any header lines like 'Key points:' - just the bullets.\n",
            "Focus on action items, decisions, requests, and important information.\n\n"
        ]

        for idx, email in enumerate(batch, 1):
            # Get body text (prefer body_full, fallback to body_preview, then snippet)
            body: str = email.get('body_full') or email.get('body_preview') or email.get('snippet', '')

            # Use more content for longer emails (up to 2500 chars)
            body = body[:2500] if len(body) > 2500 else body

            prompt_parts.append(f"Email {idx}:")
            prompt_parts.append(f"From: {email.get('from', 'Unknown')}")
            prompt_parts.append(f"To: {email.get('to', 'Unknown')}")
            prompt_parts.append(f"Subject: {email.get('subject', 'No Subject')}")
            prompt_parts.append(f"Body: {body}")
            prompt_parts.append("\n")

        prompt_parts.append("\nPlease respond with summaries numbered 1 through " + str(len(batch)) + ", with no additional formatting or commentary.")

        prompt: str = "\n".join(prompt_parts)

        # Call Claude API
        print(f"[INFO] Summarizing batch of {len(batch)} emails...")

        try:
            message = client.messages.create(
                model="claude-3-haiku-20240307",  # Haiku - fast and cheap
                max_tokens=4000,  # Enough for longer summaries (1-2 paragraphs per email)
                messages=[
                    {"role": "user", "content": prompt}
                ]
            )

            # Parse response - should be labeled emails (Email 1:, Email 2:, etc.)
            response_text: str = message.content[0].text

            # Split by "Email X:" markers (may have numbers like "1. Email 1:")
            summaries: List[str] = []
            current_summary: List[str] = []

            for line in response_text.split('\n'):
                # Check if line starts a new email section (handles "Email 1:" or "1. Email 1:" etc)
                stripped: str = line.strip()
                is_email_marker: bool = ('Email ' in stripped and ':' in stripped and
                                 any(char.isdigit() for char in stripped.split(':')[0]))

                if is_email_marker:
                    # Save previous summary if exists
                    if current_summary:
                        # Join with newlines to preserve bullet formatting
                        # Remove leading/trailing empty lines
                        summary_text: str = '\n'.join(current_summary).strip()
                        if summary_text:
                            summaries.append(summary_text)
                        current_summary = []
                    # Skip the "Email X:" line itself
                    continue
                else:
                    # Add line to current summary
                    current_summary.append(line.rstrip())

            # Don't forget the last summary
            if current_summary:
                summary_text = '\n'.join(current_summary).strip()
                if summary_text:
                    summaries.append(summary_text)

            # Assign summaries to emails
            for email, summary in zip(batch, summaries):
                email['ai_summary'] = summary

            print(f"[OK] Successfully summarized {len(summaries)} emails")

        except Exception as e:
            print(f"[ERROR] Failed to summarize batch: {e}")
            # Add error placeholders
            for email in batch:
                email['ai_summary'] = f"[Summarization failed: {str(e)}]"

    return emails


def test_summarization() -> None:
    """Test the summarization with sample emails."""
    sample_emails: List[Dict[str, str]] = [
        {
            "subject": "Meeting Tomorrow",
            "from": "john@example.com",
            "to": "jane@example.com",
            "body_preview": "Hey Jane, just wanted to confirm our meeting tomorrow at 2pm. We'll be discussing the Q4 roadmap and budget allocation. Please bring the latest financial projections."
        },
        {
            "subject": "Project Update",
            "from": "alice@company.com",
            "to": "bob@company.com",
            "body_full": "Hi Bob, The new feature is 80% complete. We hit a snag with the database migration but found a workaround. Should be ready for QA by Friday."
        }
    ]

    # Test
    summarized: List[Dict[str, Any]] = batch_summarize_emails(sample_emails)

    print("\nSummarization Results:")
    print("=" * 80)
    for email in summarized:
        print(f"\nSubject: {email['subject']}")
        print(f"Summary: {email.get('ai_summary', 'No summary')}")


if __name__ == "__main__":
    test_summarization()
