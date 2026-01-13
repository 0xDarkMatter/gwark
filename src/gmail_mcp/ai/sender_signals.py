"""Sender quality signals for email classification.

Provides signals to help distinguish known contacts from cold outreach:
1. Is sender in Google Contacts (My Contacts)?
2. Is sender in Other Contacts (auto-saved from interactions)?

Uses local caching to avoid fetching contacts on every run.
"""

import json
import re
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

# Cache settings
CACHE_DIR = Path.home() / ".gwark" / "cache"
CONTACTS_CACHE_FILE = CACHE_DIR / "contacts_cache.json"
CACHE_TTL_DAYS = 7  # Contacts rarely change


def extract_email_address(from_header: str) -> Optional[str]:
    """Extract email address from From header.

    Args:
        from_header: e.g., "John Smith <john@example.com>" or "john@example.com"

    Returns:
        Lowercase email address or None
    """
    if not from_header:
        return None

    # Try to extract from angle brackets first
    match = re.search(r'<([^>]+)>', from_header)
    if match:
        return match.group(1).lower().strip()

    # Check if it's just an email address
    match = re.search(r'[\w.+-]+@[\w.-]+\.\w+', from_header)
    if match:
        return match.group(0).lower().strip()

    return None


def fetch_contact_emails(people_service: Any) -> Set[str]:
    """Fetch all email addresses from Google Contacts (My Contacts).

    Args:
        people_service: Authenticated People API service

    Returns:
        Set of lowercase email addresses from contacts
    """
    contact_emails: Set[str] = set()

    try:
        # Fetch all contacts with email addresses
        page_token = None
        while True:
            results = people_service.people().connections().list(
                resourceName='people/me',
                pageSize=1000,
                personFields='emailAddresses',
                pageToken=page_token,
            ).execute()

            connections = results.get('connections', [])
            for person in connections:
                emails = person.get('emailAddresses', [])
                for email_obj in emails:
                    email = email_obj.get('value', '').lower().strip()
                    if email:
                        contact_emails.add(email)

            page_token = results.get('nextPageToken')
            if not page_token:
                break

        print(f"[INFO] Loaded {len(contact_emails)} email addresses from My Contacts")

    except Exception as e:
        print(f"[WARN] Failed to fetch contacts: {e}")

    return contact_emails


def fetch_other_contacts(people_service: Any) -> Set[str]:
    """Fetch email addresses from Other Contacts (auto-saved from interactions).

    This is much faster than scanning sent mail and captures everyone
    you've emailed who isn't in My Contacts.

    Args:
        people_service: Authenticated People API service

    Returns:
        Set of lowercase email addresses from Other Contacts
    """
    other_emails: Set[str] = set()

    try:
        # Fetch Other Contacts (auto-saved from email interactions)
        page_token = None
        while True:
            results = people_service.otherContacts().list(
                pageSize=1000,
                readMask='emailAddresses',
                pageToken=page_token,
            ).execute()

            contacts = results.get('otherContacts', [])
            for person in contacts:
                emails = person.get('emailAddresses', [])
                for email_obj in emails:
                    email = email_obj.get('value', '').lower().strip()
                    if email:
                        other_emails.add(email)

            page_token = results.get('nextPageToken')
            if not page_token:
                break

        print(f"[INFO] Loaded {len(other_emails)} email addresses from Other Contacts")

    except Exception as e:
        print(f"[WARN] Failed to fetch Other Contacts: {e}")

    return other_emails


def load_contacts_cache() -> Optional[Dict[str, Any]]:
    """Load contacts from local cache if valid.

    Returns:
        Cache data dict or None if cache is missing/expired
    """
    if not CONTACTS_CACHE_FILE.exists():
        return None

    try:
        cache_data = json.loads(CONTACTS_CACHE_FILE.read_text(encoding="utf-8"))
        cached_at = datetime.fromisoformat(cache_data.get("cached_at", ""))
        if datetime.now() - cached_at < timedelta(days=CACHE_TTL_DAYS):
            return cache_data
        print(f"[INFO] Contacts cache expired (>{CACHE_TTL_DAYS} days old)")
    except Exception as e:
        print(f"[WARN] Failed to load contacts cache: {e}")

    return None


def save_contacts_cache(my_contacts: Set[str], other_contacts: Set[str]) -> None:
    """Save contacts to local cache.

    Args:
        my_contacts: Set of emails from My Contacts
        other_contacts: Set of emails from Other Contacts
    """
    try:
        CACHE_DIR.mkdir(parents=True, exist_ok=True)
        cache_data = {
            "cached_at": datetime.now().isoformat(),
            "my_contacts": list(my_contacts),
            "other_contacts": list(other_contacts),
        }
        CONTACTS_CACHE_FILE.write_text(json.dumps(cache_data, indent=2), encoding="utf-8")
        print(f"[INFO] Contacts cache saved ({len(my_contacts)} + {len(other_contacts)} emails)")
    except Exception as e:
        print(f"[WARN] Failed to save contacts cache: {e}")


def enrich_with_sender_signals(
    emails: List[Dict[str, Any]],
    people_service: Optional[Any] = None,
) -> List[Dict[str, Any]]:
    """Add sender quality signals to emails.

    Uses local cache (refreshed every 24h) to avoid API calls on every run.

    Adds to each email:
    - is_contact: True if sender is in My Contacts
    - is_prior_sender: True if sender is in Other Contacts (auto-saved)
    - sender_quality: "known" | "prior" | "unknown"

    Args:
        emails: List of email dictionaries
        people_service: Authenticated People API service (optional, needed for cache refresh)

    Returns:
        Emails with sender signals added
    """
    my_contacts: Set[str] = set()
    other_contacts: Set[str] = set()

    # Try to load from cache first
    cache = load_contacts_cache()
    if cache:
        my_contacts = set(cache.get("my_contacts", []))
        other_contacts = set(cache.get("other_contacts", []))
        print(f"[INFO] Loaded contacts from cache ({len(my_contacts)} + {len(other_contacts)} emails)")
    elif people_service:
        # Fetch fresh and cache
        print(f"[INFO] Fetching contacts from Google (will cache for {CACHE_TTL_DAYS} days)...")
        my_contacts = fetch_contact_emails(people_service)
        other_contacts = fetch_other_contacts(people_service)
        save_contacts_cache(my_contacts, other_contacts)
    else:
        print("[WARN] No People API service and no cache - sender signals unavailable")

    # Combine for lookup
    all_known = my_contacts | other_contacts

    # Enrich emails
    for email in emails:
        sender_email = extract_email_address(email.get('from', ''))

        is_contact = sender_email in my_contacts if sender_email else False
        is_prior = sender_email in other_contacts if sender_email else False

        email['is_contact'] = is_contact
        email['is_prior_sender'] = is_prior

        # Determine quality tier
        if is_contact:
            email['sender_quality'] = 'known'  # In My Contacts
        elif is_prior:
            email['sender_quality'] = 'prior'  # In Other Contacts (emailed before)
        else:
            email['sender_quality'] = 'unknown'

    # Stats
    known = sum(1 for e in emails if e.get('sender_quality') == 'known')
    prior = sum(1 for e in emails if e.get('sender_quality') == 'prior')
    unknown = sum(1 for e in emails if e.get('sender_quality') == 'unknown')
    print(f"[INFO] Sender signals: {known} contacts, {prior} prior, {unknown} unknown")

    return emails
