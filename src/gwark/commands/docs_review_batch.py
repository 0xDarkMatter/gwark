"""Batch process editorial comment replies.

Helper script to post AI-generated suggestions as comment replies.
"""

import sys
import json
from pathlib import Path

# Add project root for imports
project_root = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(project_root))


def post_suggestions(doc_id: str, suggestions: dict):
    """Post AI suggestions as comment replies.

    Args:
        doc_id: Document ID
        suggestions: Dict mapping comment_id -> suggestion_text
    """
    from gmail_mcp.auth import get_docs_service, get_drive_service
    from gwark.core.docs_comments import DocsCommentManager

    docs_service = get_docs_service()
    drive_service = get_drive_service()
    manager = DocsCommentManager(docs_service, drive_service)

    print(f"\nPosting {len(suggestions)} suggestions...\n")

    for comment_id, suggestion in suggestions.items():
        try:
            reply_text = f"🤖 **gwark**\n\n{suggestion}\n\n---\nAI Editorial Suggestion via gwark docs review"
            result = manager.reply_to_comment(doc_id, comment_id, reply_text)
            print(f"✓ Posted to {comment_id} (reply ID: {result.get('id')})")
        except Exception as e:
            print(f"✗ Failed to post to {comment_id}: {e}")

    print(f"\nDone! Posted {len(suggestions)} suggestions")


if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("Usage: python -m gwark.commands.docs_review_batch DOC_ID suggestions.json")
        sys.exit(1)

    doc_id = sys.argv[1]
    suggestions_file = sys.argv[2]

    with open(suggestions_file, 'r', encoding='utf-8') as f:
        suggestions = json.load(f)

    post_suggestions(doc_id, suggestions)
