"""Entry point for running Gwark server as a module."""

import asyncio
import sys

from gmail_mcp.server.mcp_server import main


def cli() -> None:
    """Command-line interface entry point."""
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nShutting down Gwark Server...", file=sys.stderr)
        sys.exit(0)
    except Exception as e:
        print(f"Fatal error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    cli()
