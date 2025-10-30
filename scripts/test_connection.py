#!/usr/bin/env python
"""Test Gmail API connection and authentication."""

import asyncio
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root / "src"))

from gmail_mcp.auth import OAuth2Manager, TokenManager
from gmail_mcp.gmail import GmailClient


def print_success(text: str) -> None:
    """Print a success message."""
    print(f"✓ {text}")


def print_error(text: str) -> None:
    """Print an error message."""
    print(f"✗ {text}", file=sys.stderr)


def print_info(text: str) -> None:
    """Print an info message."""
    print(f"ℹ {text}")


async def test_connection(account_id: str = "primary") -> bool:
    """Test Gmail API connection.

    Args:
        account_id: Account identifier

    Returns:
        True if all tests pass
    """
    print(f"\nTesting Gmail API connection for account: {account_id}\n")

    try:
        # Test 1: Load credentials
        print_info("Loading OAuth2 credentials...")
        token_manager = TokenManager()
        credentials = await token_manager.async_load_credentials(account_id)

        if not credentials:
            print_error("No credentials found")
            print_info(f"Run: python scripts/setup_oauth.py --account-id {account_id}")
            return False

        print_success("OAuth2 credentials loaded")

        # Test 2: Validate credentials
        print_info("Validating credentials...")
        oauth_manager = OAuth2Manager()

        if not oauth_manager.validate_credentials(credentials):
            print_error("Credentials are invalid or expired")
            print_info("Try refreshing or re-running setup")
            return False

        print_success("Credentials are valid")

        # Test 3: Create Gmail client
        print_info("Creating Gmail client...")
        client = GmailClient(account_id=account_id, credentials=credentials)
        print_success("Gmail client created")

        # Test 4: Get user profile
        print_info("Fetching user profile...")
        profile = await client.get_profile()

        email = profile.get("emailAddress", "unknown")
        total_messages = profile.get("messagesTotal", 0)
        total_threads = profile.get("threadsTotal", 0)

        print_success(f"Connected to Gmail: {email}")
        print_info(f"Total messages: {total_messages:,}")
        print_info(f"Total threads: {total_threads:,}")

        # Test 5: List labels
        print_info("Fetching labels...")
        labels_response = await client.list_labels()
        labels = labels_response.get("labels", [])

        print_success(f"Found {len(labels)} labels")

        system_labels = [l["name"] for l in labels if l.get("type") == "system"]
        user_labels = [l["name"] for l in labels if l.get("type") == "user"]

        if system_labels:
            print_info(f"System labels: {', '.join(system_labels[:5])}...")
        if user_labels:
            print_info(f"Custom labels: {', '.join(user_labels[:5])}...")

        # Test 6: Search test
        print_info("Testing search (last 5 emails)...")
        search_response = await client.list_messages(query="", max_results=5)
        messages = search_response.get("messages", [])

        print_success(f"Search successful: {len(messages)} results")

        print("\n" + "=" * 60)
        print("All tests passed! ✓")
        print("=" * 60)
        print(f"\nYour Gmail MCP server is ready to use!")
        print(f"Account: {email}")
        print(f"\nTo start the server, run:")
        print(f"  python -m gmail_mcp")
        print("=" * 60 + "\n")

        return True

    except Exception as e:
        print_error(f"Connection test failed: {e}")
        print_info("Troubleshooting:")
        print_info("  1. Run: python scripts/setup_oauth.py")
        print_info("  2. Check config/oauth2_credentials.json exists")
        print_info("  3. Verify Gmail API is enabled in Google Cloud Console")
        return False


def main() -> int:
    """Main entry point."""
    import argparse

    parser = argparse.ArgumentParser(description="Test Gmail API connection")
    parser.add_argument(
        "--account-id",
        default="primary",
        help="Account identifier to test (default: primary)",
    )

    args = parser.parse_args()

    try:
        success = asyncio.run(test_connection(args.account_id))
        return 0 if success else 1

    except KeyboardInterrupt:
        print_info("\nTest cancelled by user")
        return 1
    except Exception as e:
        print_error(f"Unexpected error: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
