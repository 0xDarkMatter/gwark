"""Basic usage examples for Gmail MCP Server."""

import asyncio
from gmail_mcp.gmail import GmailClient, GmailOperations
from gmail_mcp.cache import EmailCache


async def example_search_unread():
    """Search for unread emails."""
    print("Example: Search unread emails\n")

    # Create client and operations
    client = GmailClient(account_id="primary")
    cache = EmailCache()
    await cache.initialize()
    ops = GmailOperations(client=client, cache=cache)

    # Search for unread emails
    results = await ops.search_emails(query="is:unread", page_size=10)

    print(f"Found {results['resultSizeEstimate']} unread emails")
    print(f"Showing {len(results['messages'])} results\n")

    for msg in results["messages"]:
        print(f"  - Message ID: {msg['id']}")

    # Cleanup
    await ops.close()


async def example_read_email():
    """Read a specific email."""
    print("Example: Read an email\n")

    # Create client and operations
    client = GmailClient(account_id="primary")
    ops = GmailOperations(client=client)

    # First, get a message ID from search
    results = await ops.search_emails(query="", page_size=1)
    if not results["messages"]:
        print("No emails found")
        await ops.close()
        return

    message_id = results["messages"][0]["id"]

    # Read the email
    email = await ops.read_email(message_id, format="metadata")

    # Extract headers
    headers = email.get("payload", {}).get("headers", [])
    subject = next((h["value"] for h in headers if h["name"] == "Subject"), "No Subject")
    from_addr = next((h["value"] for h in headers if h["name"] == "From"), "Unknown")

    print(f"Subject: {subject}")
    print(f"From: {from_addr}")
    print(f"Snippet: {email.get('snippet', '')}")

    # Cleanup
    await ops.close()


async def example_filter_emails():
    """Use advanced filters to search emails."""
    print("Example: Advanced filtering\n")

    from gmail_mcp.gmail.filters import EmailFilter

    # Build complex query
    filter = (
        EmailFilter()
        .from_sender("example@gmail.com")
        .last_n_days(7)
        .has_attachment()
        .is_unread()
    )

    query = filter.build()
    print(f"Query: {query}\n")

    # Use the query
    client = GmailClient(account_id="primary")
    ops = GmailOperations(client=client)

    results = await ops.search_emails(query=query, page_size=5)
    print(f"Found {results['resultSizeEstimate']} matching emails")

    # Cleanup
    await ops.close()


async def example_batch_operations():
    """Batch operations on multiple emails."""
    print("Example: Batch operations\n")

    from gmail_mcp.gmail.batch import BatchOperations

    # Create client and batch ops
    client = GmailClient(account_id="primary")
    batch_ops = BatchOperations(client=client)

    # Get some message IDs
    ops = GmailOperations(client=client)
    results = await ops.search_emails(query="is:unread", page_size=5)

    if not results["messages"]:
        print("No unread emails found")
        await ops.close()
        return

    message_ids = [msg["id"] for msg in results["messages"]]

    # Batch read
    batch_results = await batch_ops.batch_read(message_ids, format="metadata")

    print(f"Batch read: {batch_results['success_count']}/{batch_results['total']} successful")

    # Could also batch mark as read:
    # await batch_ops.batch_mark_as_read(message_ids)

    # Cleanup
    await ops.close()


async def main():
    """Run all examples."""
    print("=" * 60)
    print("Gmail MCP Server - Usage Examples")
    print("=" * 60 + "\n")

    try:
        await example_search_unread()
        print("\n" + "-" * 60 + "\n")

        await example_read_email()
        print("\n" + "-" * 60 + "\n")

        await example_filter_emails()
        print("\n" + "-" * 60 + "\n")

        await example_batch_operations()

    except Exception as e:
        print(f"Error running examples: {e}")
        print("\nMake sure you've run OAuth2 setup first:")
        print("  python scripts/setup_oauth.py")


if __name__ == "__main__":
    asyncio.run(main())
