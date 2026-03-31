"""Unit tests for gwark.core.email_utils."""

import pytest
from gwark.core.email_utils import (
    extract_name,
    extract_email_address,
    build_gmail_query,
    extract_email_details,
    get_gmail_category,
)


class TestExtractName:
    def test_name_from_angle_bracket_format(self):
        assert extract_name("John Doe <john@example.com>") == "John Doe"

    def test_name_from_quoted_format(self):
        assert extract_name('"Jane Smith" <jane@example.com>') == "Jane Smith"

    def test_name_from_email_only(self):
        assert extract_name("john.doe@example.com") == "John Doe"

    def test_name_from_underscore_email(self):
        assert extract_name("john_doe@example.com") == "John Doe"

    def test_empty_string(self):
        assert extract_name("") == "Unknown"

    def test_none_input(self):
        assert extract_name(None) == "Unknown"

    def test_name_with_extra_spaces(self):
        assert extract_name("  John Doe  <john@example.com>") == "John Doe"


class TestExtractEmailAddress:
    def test_from_angle_bracket_format(self):
        assert extract_email_address("John Doe <john@example.com>") == "john@example.com"

    def test_plain_email(self):
        assert extract_email_address("john@example.com") == "john@example.com"

    def test_empty_string(self):
        assert extract_email_address("") == ""

    def test_none_input(self):
        assert extract_email_address(None) == ""

    def test_no_email_returns_empty(self):
        assert extract_email_address("not an email at all") == ""

    def test_malformed_header_returns_empty(self):
        assert extract_email_address("Broken Header =") == ""

    def test_quoted_name_with_email(self):
        assert extract_email_address('"Smith, John" <john@corp.com>') == "john@corp.com"


class TestBuildGmailQuery:
    def test_domain_query(self):
        q = build_gmail_query(domain="example.com")
        assert "(from:@example.com OR to:@example.com)" in q

    def test_sender_query(self):
        q = build_gmail_query(sender="john@example.com")
        assert "from:john@example.com" in q

    def test_recipient_query(self):
        q = build_gmail_query(recipient="bob@example.com")
        assert "to:bob@example.com" in q

    def test_subject_query(self):
        q = build_gmail_query(subject="invoice")
        assert 'subject:"invoice"' in q

    def test_date_range(self):
        q = build_gmail_query(after_date="2025/01/01", before_date="2025/02/01")
        assert "after:2025/01/01" in q
        assert "before:2025/02/01" in q

    def test_has_attachment(self):
        q = build_gmail_query(has_attachment=True)
        assert "has:attachment" in q

    def test_custom_query_overrides_all(self):
        q = build_gmail_query(domain="example.com", custom_query="is:starred")
        assert q == "is:starred"

    def test_empty_query(self):
        q = build_gmail_query()
        assert q == ""

    def test_combined_query(self):
        q = build_gmail_query(sender="alice@example.com", after_date="2025/01/01")
        assert "from:alice@example.com" in q
        assert "after:2025/01/01" in q


class TestExtractEmailDetails:
    def test_basic_extraction(self, sample_email_content):
        details = extract_email_details(sample_email_content)
        assert details["id"] == "test_message_123"
        assert details["subject"] == "Test Email"
        assert details["from"] == "sender@example.com"
        assert details["to"] == "recipient@example.com"

    def test_summary_mode_no_body(self, sample_email_content):
        details = extract_email_details(sample_email_content, detail_level="summary")
        assert "body_full" not in details
        assert "cc" not in details

    def test_full_mode_includes_body(self, sample_email_content):
        details = extract_email_details(sample_email_content, detail_level="full")
        assert "body_full" in details
        assert "body_preview" in details
        assert "cc" in details

    def test_missing_headers(self):
        email = {
            "id": "test_1",
            "payload": {"headers": []},
        }
        details = extract_email_details(email)
        assert details["subject"] == "No Subject"
        assert details["from"] == "Unknown"


class TestGetGmailCategory:
    def test_updates(self):
        assert get_gmail_category(["CATEGORY_UPDATES"]) == "Updates"

    def test_promotions(self):
        assert get_gmail_category(["CATEGORY_PROMOTIONS"]) == "Promotions"

    def test_social(self):
        assert get_gmail_category(["CATEGORY_SOCIAL"]) == "Social"

    def test_forums(self):
        assert get_gmail_category(["CATEGORY_FORUMS"]) == "Forums"

    def test_primary_default(self):
        assert get_gmail_category(["INBOX", "UNREAD"]) == "Primary"

    def test_empty_labels(self):
        assert get_gmail_category([]) == "Primary"
