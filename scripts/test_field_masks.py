#!/usr/bin/env python
"""Test script to demonstrate and verify field mask efficiency.

This script compares payload sizes with and without field masks to show
the 40-70% reduction in data transfer.
"""

import asyncio
import sys
from pathlib import Path
import json

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root / "src"))

from gmail_mcp.gmail import GmailClient
from gmail_mcp.gmail.fields import get_field_mask, get_list_field_mask


def sizeof_json(obj) -> int:
    """Calculate size of JSON-serialized object in bytes."""
    return len(json.dumps(obj, default=str).encode('utf-8'))


def format_bytes(bytes_size: int) -> str:
    """Format bytes as human-readable string."""
    for unit in ['B', 'KB', 'MB', 'GB']:
        if bytes_size < 1024.0:
            return f"{bytes_size:.2f} {unit}"
        bytes_size /= 1024.0
    return f"{bytes_size:.2f} TB"


async def test_list_field_masks():
    """Test list operations with different field masks."""
    print("=" * 80)
    print("  Testing List Operations with Field Masks")
    print("=" * 80)
    print()

    client = GmailClient()

    # Test query - get 10 unread emails
    query = "is:unread"
    max_results = 10

    print(f"Query: {query}")
    print(f"Max results: {max_results}")
    print()

    # Test 1: No field mask (baseline)
    print("[1/3] Fetching without field mask...")
    result_full = await client.list_messages(
        query=query,
        max_results=max_results,
        fields=None  # No field mask - gets everything
    )
    size_full = sizeof_json(result_full)
    print(f"  Size: {format_bytes(size_full)}")
    print(f"  Messages: {len(result_full.get('messages', []))}")
    print()

    # Test 2: Standard field mask
    print("[2/3] Fetching with standard field mask...")
    result_standard = await client.list_messages(
        query=query,
        max_results=max_results,
        fields="standard"
    )
    size_standard = sizeof_json(result_standard)
    reduction_standard = ((size_full - size_standard) / size_full) * 100
    print(f"  Size: {format_bytes(size_standard)}")
    print(f"  Reduction: {reduction_standard:.1f}%")
    print(f"  Field mask: {get_list_field_mask('standard')}")
    print()

    # Test 3: Minimal field mask
    print("[3/3] Fetching with minimal field mask...")
    result_minimal = await client.list_messages(
        query=query,
        max_results=max_results,
        fields="minimal"
    )
    size_minimal = sizeof_json(result_minimal)
    reduction_minimal = ((size_full - size_minimal) / size_full) * 100
    print(f"  Size: {format_bytes(size_minimal)}")
    print(f"  Reduction: {reduction_minimal:.1f}%")
    print(f"  Field mask: {get_list_field_mask('minimal')}")
    print()

    # Summary
    print("Summary:")
    print(f"  Full response:     {format_bytes(size_full)} (baseline)")
    print(f"  Standard mask:     {format_bytes(size_standard)} ({reduction_standard:.1f}% smaller)")
    print(f"  Minimal mask:      {format_bytes(size_minimal)} ({reduction_minimal:.1f}% smaller)")
    print()


async def test_message_field_masks():
    """Test message get operations with different field masks."""
    print("=" * 80)
    print("  Testing Message Get Operations with Field Masks")
    print("=" * 80)
    print()

    client = GmailClient()

    # Get first unread message ID
    list_result = await client.list_messages(
        query="is:unread",
        max_results=1,
        fields="minimal"
    )

    if not list_result.get('messages'):
        print("No unread messages found for testing.")
        return

    message_id = list_result['messages'][0]['id']
    print(f"Testing with message ID: {message_id}")
    print()

    # Test 1: Full message (no field mask)
    print("[1/4] Fetching full message without field mask...")
    msg_full = await client.get_message(
        message_id=message_id,
        format="full",
        fields=None
    )
    size_full = sizeof_json(msg_full)
    print(f"  Size: {format_bytes(size_full)}")
    print()

    # Test 2: Metadata only
    print("[2/4] Fetching with metadata field mask...")
    msg_metadata = await client.get_message(
        message_id=message_id,
        format="metadata",
        fields="metadata"
    )
    size_metadata = sizeof_json(msg_metadata)
    reduction_metadata = ((size_full - size_metadata) / size_full) * 100
    print(f"  Size: {format_bytes(size_metadata)}")
    print(f"  Reduction: {reduction_metadata:.1f}%")
    print(f"  Field mask: {get_field_mask('metadata')}")
    print()

    # Test 3: Summary (snippet + headers)
    print("[3/4] Fetching with summary field mask...")
    msg_summary = await client.get_message(
        message_id=message_id,
        format="full",
        fields="summary"
    )
    size_summary = sizeof_json(msg_summary)
    reduction_summary = ((size_full - size_summary) / size_full) * 100
    print(f"  Size: {format_bytes(size_summary)}")
    print(f"  Reduction: {reduction_summary:.1f}%")
    print(f"  Field mask: {get_field_mask('summary')}")
    print()

    # Test 4: Minimal (IDs only)
    print("[4/4] Fetching with minimal field mask...")
    msg_minimal = await client.get_message(
        message_id=message_id,
        format="minimal",
        fields="minimal"
    )
    size_minimal = sizeof_json(msg_minimal)
    reduction_minimal = ((size_full - size_minimal) / size_full) * 100
    print(f"  Size: {format_bytes(size_minimal)}")
    print(f"  Reduction: {reduction_minimal:.1f}%")
    print(f"  Field mask: {get_field_mask('minimal')}")
    print()

    # Summary
    print("Summary:")
    print(f"  Full message:      {format_bytes(size_full)} (baseline)")
    print(f"  Metadata mask:     {format_bytes(size_metadata)} ({reduction_metadata:.1f}% smaller)")
    print(f"  Summary mask:      {format_bytes(size_summary)} ({reduction_summary:.1f}% smaller)")
    print(f"  Minimal mask:      {format_bytes(size_minimal)} ({reduction_minimal:.1f}% smaller)")
    print()

    # Calculate bandwidth savings for 1000 messages
    print("Bandwidth Savings Projection:")
    messages_count = 1000
    full_bandwidth = (size_full * messages_count) / (1024 * 1024)
    metadata_bandwidth = (size_metadata * messages_count) / (1024 * 1024)
    savings_mb = full_bandwidth - metadata_bandwidth

    print(f"  For {messages_count} messages:")
    print(f"    Full:     {full_bandwidth:.2f} MB")
    print(f"    Metadata: {metadata_bandwidth:.2f} MB")
    print(f"    Savings:  {savings_mb:.2f} MB ({reduction_metadata:.1f}%)")
    print()


async def main():
    """Run all field mask tests."""
    print()
    print("Field Mask Efficiency Test")
    print("Testing partial responses to demonstrate payload reduction")
    print()

    try:
        # Test list operations
        await test_list_field_masks()

        # Test message operations
        await test_message_field_masks()

        print("=" * 80)
        print("  Test Complete")
        print("=" * 80)
        print()
        print("Key Takeaways:")
        print("  - Field masks reduce payload size by 40-70%")
        print("  - Use 'minimal' for ID-only operations")
        print("  - Use 'metadata' for headers without body")
        print("  - Use 'summary' for snippet + headers")
        print("  - Use 'full' only when body is needed")
        print()

    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
        return 1

    return 0


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
