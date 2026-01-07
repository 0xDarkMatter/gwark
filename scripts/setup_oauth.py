#!/usr/bin/env python
"""Interactive OAuth2 setup script for Gmail MCP Server."""

import argparse
import asyncio
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root / "src"))

from gmail_mcp.auth import OAuth2Manager, TokenManager
from gmail_mcp.config import get_settings


def print_header(text: str) -> None:
    """Print a formatted header."""
    print(f"\n{'=' * 60}")
    print(f"  {text}")
    print(f"{'=' * 60}\n")


def print_success(text: str) -> None:
    """Print a success message."""
    print(f"[OK] {text}")


def print_error(text: str) -> None:
    """Print an error message."""
    print(f"[X] {text}", file=sys.stderr)


def print_info(text: str) -> None:
    """Print an info message."""
    print(f"[i] {text}")


async def setup_oauth(account_id: str = "primary", manual: bool = False) -> bool:
    """Run OAuth2 setup flow.

    Args:
        account_id: Account identifier
        manual: Use manual authorization flow

    Returns:
        True if successful
    """
    print_header("Gmail MCP Server - OAuth2 Setup")

    try:
        # Initialize managers
        oauth_manager = OAuth2Manager()
        token_manager = TokenManager()

        print_info(f"Setting up account: {account_id}")

        if manual:
            # Manual flow with authorization code
            print_info("Manual authorization flow selected")
            auth_url, state = oauth_manager.get_authorization_url()

            print("\n1. Open this URL in your browser:")
            print(f"\n   {auth_url}\n")
            print("2. Sign in and authorize the application")
            print("3. Copy the authorization code from the browser\n")

            auth_code = input("Enter the authorization code: ").strip()

            if not auth_code:
                print_error("No authorization code provided")
                return False

            print_info("Exchanging authorization code for tokens...")
            credentials = oauth_manager.exchange_code_for_token(auth_code)

        else:
            # Local server flow (automatic)
            print_info("Opening browser for authentication...")
            print_info("A browser window will open. Please sign in and authorize the app.")
            print_info("This window will close automatically after authorization.")

            credentials = oauth_manager.run_local_server_flow()

        # Save credentials
        print_info("Saving encrypted credentials...")
        await token_manager.async_save_credentials(credentials, account_id)

        print_success(f"OAuth2 setup complete for account: {account_id}")
        print_info(f"Tokens saved to: {token_manager.storage_path / account_id}.token")

        return True

    except FileNotFoundError as e:
        print_error(f"OAuth2 credentials file not found")
        print_info("Please download credentials from Google Cloud Console:")
        print_info("  1. Go to https://console.cloud.google.com/")
        print_info("  2. Navigate to APIs & Services > Credentials")
        print_info("  3. Create OAuth 2.0 Client ID (Desktop App)")
        print_info("  4. Download JSON and save as .gwark/credentials/oauth2_credentials.json")
        return False

    except Exception as e:
        print_error(f"Setup failed: {e}")
        return False


async def list_accounts() -> None:
    """List all configured accounts."""
    print_header("Configured Accounts")

    token_manager = TokenManager()
    accounts = token_manager.list_accounts()

    if not accounts:
        print_info("No accounts configured yet")
        print_info("Run: python scripts/setup_oauth.py")
        return

    print(f"Found {len(accounts)} account(s):\n")
    for account in accounts:
        print(f"  • {account}")


async def remove_account(account_id: str) -> bool:
    """Remove an account's credentials.

    Args:
        account_id: Account identifier

    Returns:
        True if successful
    """
    print_header(f"Remove Account: {account_id}")

    token_manager = TokenManager()

    if not token_manager.has_credentials(account_id):
        print_error(f"No credentials found for account: {account_id}")
        return False

    # Confirm deletion
    response = input(f"Are you sure you want to remove '{account_id}'? (yes/no): ")
    if response.lower() != "yes":
        print_info("Cancelled")
        return False

    if token_manager.delete_credentials(account_id):
        print_success(f"Removed account: {account_id}")
        return True
    else:
        print_error(f"Failed to remove account: {account_id}")
        return False


def main() -> int:
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="OAuth2 setup for Gmail MCP Server",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Setup primary account (automatic browser flow)
  python scripts/setup_oauth.py

  # Setup with manual authorization code
  python scripts/setup_oauth.py --manual

  # Setup additional account
  python scripts/setup_oauth.py --account-id work

  # List configured accounts
  python scripts/setup_oauth.py --list

  # Remove an account
  python scripts/setup_oauth.py --remove work
        """,
    )

    parser.add_argument(
        "--account-id",
        default="primary",
        help="Account identifier (default: primary)",
    )

    parser.add_argument(
        "--manual",
        action="store_true",
        help="Use manual authorization code flow",
    )

    parser.add_argument(
        "--list",
        action="store_true",
        help="List all configured accounts",
    )

    parser.add_argument(
        "--remove",
        metavar="ACCOUNT_ID",
        help="Remove an account's credentials",
    )

    args = parser.parse_args()

    # Handle different commands
    try:
        if args.list:
            asyncio.run(list_accounts())
            return 0

        elif args.remove:
            success = asyncio.run(remove_account(args.remove))
            return 0 if success else 1

        else:
            # Run OAuth setup
            success = asyncio.run(setup_oauth(args.account_id, args.manual))
            return 0 if success else 1

    except KeyboardInterrupt:
        print_info("\nSetup cancelled by user")
        return 1
    except Exception as e:
        print_error(f"Unexpected error: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
