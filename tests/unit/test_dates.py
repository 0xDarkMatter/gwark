"""Unit tests for gwark.core.dates."""

import pytest
from datetime import datetime
from gwark.core.dates import (
    parse_email_date,
    format_short_date,
    format_datetime,
    date_to_gmail_query,
    get_date_timestamp,
    parse_date_range,
)


class TestParseEmailDate:
    def test_rfc2822_format(self):
        dt = parse_email_date("Mon, 1 Jan 2024 12:00:00 +0000")
        assert dt is not None
        assert dt.year == 2024
        assert dt.month == 1
        assert dt.day == 1

    def test_invalid_date(self):
        assert parse_email_date("not a date") is None

    def test_empty_string(self):
        assert parse_email_date("") is None


class TestFormatShortDate:
    def test_valid_date(self):
        result = format_short_date("Mon, 1 Jan 2024 12:00:00 +0000")
        assert result == "01/01/2024"

    def test_invalid_date_returns_original(self):
        assert format_short_date("garbage") == "garbage"

    def test_empty_string(self):
        assert format_short_date("") == ""


class TestFormatDatetime:
    def test_valid_date(self):
        result = format_datetime("Mon, 1 Jan 2024 12:00:00 +0000")
        # Time depends on local timezone conversion, just check format
        assert "/01/2024" in result
        assert ":" in result

    def test_invalid_date(self):
        assert format_datetime("nope") == "nope"


class TestDateToGmailQuery:
    def test_format(self):
        dt = datetime(2025, 3, 15)
        assert date_to_gmail_query(dt) == "2025/03/15"


class TestGetDateTimestamp:
    def test_valid_date(self):
        ts = get_date_timestamp("Mon, 1 Jan 2024 12:00:00 +0000")
        assert ts > 0

    def test_invalid_date(self):
        assert get_date_timestamp("not a date") == 0.0

    def test_empty_string(self):
        assert get_date_timestamp("") == 0.0


class TestParseDateRange:
    def test_default_30_days(self):
        start, end = parse_date_range(days_back=30)
        delta = end - start
        assert delta.days == 30

    def test_explicit_dates(self):
        start = datetime(2025, 1, 1)
        end = datetime(2025, 2, 1)
        result_start, result_end = parse_date_range(start_date=start, end_date=end)
        assert result_start == start
        assert result_end == end
