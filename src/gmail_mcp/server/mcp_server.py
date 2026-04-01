"""Gwark Server implementation."""

import asyncio
import logging
from typing import Any

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent

from gmail_mcp.config import get_settings
from gmail_mcp.server.handlers import GmailToolHandlers
from gmail_mcp.utils.logging import setup_logging

logger = logging.getLogger(__name__)


class GmailMCPServer:
    """Gwark Server for Model Context Protocol."""

    def __init__(self):
        """Initialize Gwark server."""
        self.settings = get_settings()
        self.server = Server(self.settings.server_name)
        self.handlers = GmailToolHandlers()

        # Register tools
        self._register_tools()

        logger.info(f"Gwark Server initialized: {self.settings.server_name}")

    def _register_tools(self) -> None:
        """Register all MCP tools."""

        @self.server.list_tools()
        async def list_tools() -> list[Tool]:
            """List available Gmail tools."""
            return [
                Tool(
                    name="search_emails",
                    description="Search emails using Gmail query syntax. Supports pagination for large result sets.",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "query": {
                                "type": "string",
                                "description": "Gmail search query (e.g., 'from:example@gmail.com is:unread')",
                            },
                            "max_results": {
                                "type": "integer",
                                "description": "Maximum total results to return",
                            },
                            "page_size": {
                                "type": "integer",
                                "description": "Results per page (default: 100)",
                            },
                            "page_token": {
                                "type": "string",
                                "description": "Page token for pagination",
                            },
                            "account_id": {
                                "type": "string",
                                "description": "Account identifier (default: primary)",
                                "default": "primary",
                            },
                        },
                        "required": ["query"],
                    },
                ),
                Tool(
                    name="read_email",
                    description="Read a specific email by message ID. Returns full content and metadata.",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "message_id": {
                                "type": "string",
                                "description": "Gmail message ID",
                            },
                            "format": {
                                "type": "string",
                                "description": "Response format: full, metadata, minimal",
                                "enum": ["full", "metadata", "minimal"],
                                "default": "full",
                            },
                            "account_id": {
                                "type": "string",
                                "description": "Account identifier",
                                "default": "primary",
                            },
                        },
                        "required": ["message_id"],
                    },
                ),
                Tool(
                    name="list_labels",
                    description="List all Gmail labels for the account.",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "account_id": {
                                "type": "string",
                                "description": "Account identifier",
                                "default": "primary",
                            },
                        },
                    },
                ),
                Tool(
                    name="apply_labels",
                    description="Add or remove labels from an email.",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "message_id": {
                                "type": "string",
                                "description": "Gmail message ID",
                            },
                            "label_ids": {
                                "type": "array",
                                "items": {"type": "string"},
                                "description": "Label IDs to add",
                            },
                            "remove_labels": {
                                "type": "array",
                                "items": {"type": "string"},
                                "description": "Label IDs to remove",
                            },
                            "account_id": {
                                "type": "string",
                                "description": "Account identifier",
                                "default": "primary",
                            },
                        },
                        "required": ["message_id", "label_ids"],
                    },
                ),
                Tool(
                    name="remove_labels",
                    description="Remove labels from an email.",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "message_id": {
                                "type": "string",
                                "description": "Gmail message ID",
                            },
                            "label_ids": {
                                "type": "array",
                                "items": {"type": "string"},
                                "description": "Label IDs to remove",
                            },
                            "account_id": {
                                "type": "string",
                                "description": "Account identifier",
                                "default": "primary",
                            },
                        },
                        "required": ["message_id", "label_ids"],
                    },
                ),
                Tool(
                    name="mark_as_read",
                    description="Mark an email as read.",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "message_id": {
                                "type": "string",
                                "description": "Gmail message ID",
                            },
                            "account_id": {
                                "type": "string",
                                "description": "Account identifier",
                                "default": "primary",
                            },
                        },
                        "required": ["message_id"],
                    },
                ),
                Tool(
                    name="mark_as_unread",
                    description="Mark an email as unread.",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "message_id": {
                                "type": "string",
                                "description": "Gmail message ID",
                            },
                            "account_id": {
                                "type": "string",
                                "description": "Account identifier",
                                "default": "primary",
                            },
                        },
                        "required": ["message_id"],
                    },
                ),
                Tool(
                    name="archive",
                    description="Archive an email (remove from INBOX).",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "message_id": {
                                "type": "string",
                                "description": "Gmail message ID",
                            },
                            "account_id": {
                                "type": "string",
                                "description": "Account identifier",
                                "default": "primary",
                            },
                        },
                        "required": ["message_id"],
                    },
                ),
                Tool(
                    name="star",
                    description="Star an email.",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "message_id": {
                                "type": "string",
                                "description": "Gmail message ID",
                            },
                            "account_id": {
                                "type": "string",
                                "description": "Account identifier",
                                "default": "primary",
                            },
                        },
                        "required": ["message_id"],
                    },
                ),
                Tool(
                    name="unstar",
                    description="Unstar an email.",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "message_id": {
                                "type": "string",
                                "description": "Gmail message ID",
                            },
                            "account_id": {
                                "type": "string",
                                "description": "Account identifier",
                                "default": "primary",
                            },
                        },
                        "required": ["message_id"],
                    },
                ),
                Tool(
                    name="batch_read",
                    description="Read multiple emails in parallel (up to 50).",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "message_ids": {
                                "type": "array",
                                "items": {"type": "string"},
                                "description": "List of message IDs to read",
                            },
                            "format": {
                                "type": "string",
                                "description": "Response format",
                                "enum": ["full", "metadata", "minimal"],
                                "default": "metadata",
                            },
                            "account_id": {
                                "type": "string",
                                "description": "Account identifier",
                                "default": "primary",
                            },
                        },
                        "required": ["message_ids"],
                    },
                ),
                Tool(
                    name="batch_apply_labels",
                    description="Apply or remove labels from multiple emails in parallel.",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "message_ids": {
                                "type": "array",
                                "items": {"type": "string"},
                                "description": "List of message IDs",
                            },
                            "add_label_ids": {
                                "type": "array",
                                "items": {"type": "string"},
                                "description": "Labels to add",
                            },
                            "remove_label_ids": {
                                "type": "array",
                                "items": {"type": "string"},
                                "description": "Labels to remove",
                            },
                            "account_id": {
                                "type": "string",
                                "description": "Account identifier",
                                "default": "primary",
                            },
                        },
                        "required": ["message_ids"],
                    },
                ),
                Tool(
                    name="get_profile",
                    description="Get Gmail user profile information.",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "account_id": {
                                "type": "string",
                                "description": "Account identifier",
                                "default": "primary",
                            },
                        },
                    },
                ),
            ]

        @self.server.call_tool()
        async def call_tool(name: str, arguments: dict[str, Any]) -> list[TextContent]:
            """Handle tool calls."""
            try:
                # Route to appropriate handler
                if name == "search_emails":
                    result = await self.handlers.search_emails(arguments)
                elif name == "read_email":
                    result = await self.handlers.read_email(arguments)
                elif name == "list_labels":
                    result = await self.handlers.list_labels(arguments)
                elif name == "apply_labels":
                    result = await self.handlers.apply_labels(arguments)
                elif name == "remove_labels":
                    result = await self.handlers.remove_labels(arguments)
                elif name == "mark_as_read":
                    result = await self.handlers.mark_as_read(arguments)
                elif name == "mark_as_unread":
                    result = await self.handlers.mark_as_unread(arguments)
                elif name == "archive":
                    result = await self.handlers.archive(arguments)
                elif name == "star":
                    result = await self.handlers.star(arguments)
                elif name == "unstar":
                    result = await self.handlers.unstar(arguments)
                elif name == "batch_read":
                    result = await self.handlers.batch_read(arguments)
                elif name == "batch_apply_labels":
                    result = await self.handlers.batch_apply_labels(arguments)
                elif name == "get_profile":
                    result = await self.handlers.get_profile(arguments)
                else:
                    raise ValueError(f"Unknown tool: {name}")

                # Return result as text content
                import json

                return [TextContent(type="text", text=json.dumps(result, indent=2))]

            except Exception as e:
                logger.error(f"Tool {name} failed: {e}", exc_info=True)
                error_response = {
                    "error": str(e),
                    "error_type": type(e).__name__,
                    "tool": name,
                }
                import json

                return [TextContent(type="text", text=json.dumps(error_response, indent=2))]

    async def run(self) -> None:
        """Run the MCP server."""
        logger.info("Starting Gwark Server...")

        try:
            async with stdio_server() as (read_stream, write_stream):
                await self.server.run(
                    read_stream,
                    write_stream,
                    self.server.create_initialization_options(),
                )
        except KeyboardInterrupt:
            logger.info("Server interrupted by user")
        except Exception as e:
            logger.error(f"Server error: {e}", exc_info=True)
        finally:
            await self.cleanup()

    async def cleanup(self) -> None:
        """Cleanup server resources."""
        logger.info("Cleaning up Gwark Server...")
        await self.handlers.cleanup()
        logger.info("Gwark Server stopped")


async def main() -> None:
    """Main entry point for Gwark server."""
    # Setup logging
    setup_logging()

    # Create and run server
    server = GmailMCPServer()
    await server.run()


if __name__ == "__main__":
    asyncio.run(main())
