"""CLI smoke tests - verify all commands load and show help without crashing."""

import subprocess
import sys

import pytest

PYTHON = sys.executable


def run_gwark(*args, expect_exit=0):
    """Run a gwark CLI command and return result."""
    result = subprocess.run(
        [PYTHON, "-m", "gwark"] + list(args),
        capture_output=True, text=True, timeout=15,
    )
    if expect_exit is not None:
        assert result.returncode == expect_exit, (
            f"gwark {' '.join(args)} exited {result.returncode}, "
            f"expected {expect_exit}\n{result.stderr}"
        )
    return result


class TestTopLevel:
    def test_help(self):
        r = run_gwark("--help")
        assert "Google Workspace CLI" in r.stdout

    def test_version(self):
        r = run_gwark("--version")
        assert "0.3.5" in r.stdout


class TestEmailHelp:
    def test_email_help(self):
        r = run_gwark("email", "--help")
        assert "search" in r.stdout
        assert "senders" in r.stdout
        assert "sent" in r.stdout
        assert "summarize" in r.stdout

    def test_search_help(self):
        r = run_gwark("email", "search", "--help")
        assert "--domain" in r.stdout
        assert "--sender" in r.stdout

    def test_senders_help(self):
        r = run_gwark("email", "senders", "--help")
        assert "--name" in r.stdout
        assert "--enrich" in r.stdout

    def test_senders_no_args(self):
        r = run_gwark("email", "senders", expect_exit=4)
        assert "Provide at least one" in r.stderr


class TestCalendarHelp:
    def test_calendar_help(self):
        r = run_gwark("calendar", "--help")
        assert "meetings" in r.stdout


class TestDriveHelp:
    def test_drive_help(self):
        r = run_gwark("drive", "--help")
        for cmd in ["ls", "search", "mkdir", "rename", "move", "copy", "rm", "share"]:
            assert cmd in r.stdout


class TestDocsHelp:
    def test_docs_help(self):
        r = run_gwark("docs", "--help")
        for cmd in ["create", "get", "edit", "sections", "theme"]:
            assert cmd in r.stdout


class TestSheetsHelp:
    def test_sheets_help(self):
        r = run_gwark("sheets", "--help")
        for cmd in ["list", "get", "read", "write", "create", "pivot"]:
            assert cmd in r.stdout


class TestSlidesHelp:
    def test_slides_help(self):
        r = run_gwark("slides", "--help")
        for cmd in ["list", "get", "create", "edit", "export"]:
            assert cmd in r.stdout


class TestFormsHelp:
    def test_forms_help(self):
        r = run_gwark("forms", "--help")
        for cmd in ["list", "get", "responses", "create"]:
            assert cmd in r.stdout


class TestConfigHelp:
    def test_config_help(self):
        r = run_gwark("config", "--help")
        for cmd in ["init", "show", "auth", "profile"]:
            assert cmd in r.stdout

    def test_auth_test_help(self):
        r = run_gwark("config", "auth", "test", "--help")
        assert "--all" in r.stdout
