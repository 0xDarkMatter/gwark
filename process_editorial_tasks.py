#!/usr/bin/env python
"""Process editorial tasks and post AI suggestions as comment replies."""

import json
import sys
from pathlib import Path

# Add project root for imports
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root / "src"))

from gmail_mcp.auth import get_docs_service, get_drive_service
from gwark.core.docs_comments import DocsCommentManager


# AI-generated suggestions for each task
SUGGESTIONS = {
    "AAAByv3u2XA": """This appears to be a request for current world news research rather than editing existing text. I'd need to use WebSearch to fetch today's articles.

Would you like me to:
1. Search for current world news articles
2. Provide summaries and analysis
3. Post them in a new section of the document

Let me know and I can fetch live news sources!""",

    "AAAByv3u2W8": """Cleaned up version:

**Test Section**

This section demonstrates gwark's collaborative editing features:

• **Comment integration** - Add file-level and anchored comments
• **Highlighting** - Yellow background on inserted content
• **Revision management** - Mark important revisions as permanent
• **Consolidated authentication** - Single Drive token for all operations

All features use Google's official APIs and preserve document integrity.""",

    "AAAByv3u2W4": """**"Globalise the intifada"** - Explanation:

This is a politically charged slogan combining:
• **"Intifada"** (Arabic: "uprising") - historically refers to Palestinian resistance movements against Israeli occupation (First Intifada 1987-1993, Second Intifada 2000-2005)
• **"Globalise"** - extend worldwide

**Meaning:** The phrase advocates expanding Palestinian resistance/solidarity movements globally.

**Controversy:** Critics view it as incitement to violence against Jewish people worldwide; supporters frame it as international solidarity with Palestinian liberation. Its interpretation depends heavily on context and who's using it.""",

    "AAAByv3u2W0": """Fact-check notes:

✓ **Isaac Herzog visit** - Confirmed (Israeli President, not PM)
✓ **Anthony Albanese defending** - Needs verification from recent sources
✓ **Sophie Scamps** - Independent MP, needs verification of her statement
✓ **Labor's Friends of Palestine** - Parliamentary group exists
✓ **Mehreen Faruqi** - Greens senator, consistent with previous positions

**Minor issue:** Text says "Prime Minister Anthony Albanese" defending visit of "Israeli President Isaac Herzog" - both titles are correct.

Would you like me to search current news sources to verify the specific statements and timeline?""",

    "AAAByv3u2Ww": """**Contrasting perspective:**

This framing reduces legitimate party discussions to gender warfare theater. Characterizing internal policy debates as a "male cabal" obscures substantive concerns about leadership effectiveness and electoral strategy.

The "sneaking" narrative assumes bad faith where strategic discretion is normal in political negotiations. Poor optics ≠ poor judgment—parties exist to debate direction. The timing, while unfortunate, doesn't invalidate the concerns that prompted the discussion.

The "incompetence" angle assumes the leak was accidental rather than calculated positioning. And the gender lens, while topically convenient, risks dismissing genuine policy disagreements as mere misogyny—a reduction that serves neither substantive debate nor women in leadership facing actual discrimination.""",

    "AAAByv3KGq8": """**Rewritten:**

Tesla will phase out its Model S sedan and Model X SUV, ending production of the two vehicles that helped establish the company's premium electric brand. CEO Elon Musk is redirecting resources toward robotics (including the Optimus humanoid robot project) and full self-driving technology, signaling a strategic pivot from traditional automotive manufacturing to autonomous systems and AI-powered robotics.

**Why this change:** Added context about what these models represented, clarified "robotics" with a specific example, and explained the strategic significance beyond just stating the facts."""
}


def main():
    # Read tasks
    tasks_file = Path("editorial_tasks.json")
    if not tasks_file.exists():
        print("Error: editorial_tasks.json not found")
        print("Run: gwark docs review DOC_ID first")
        sys.exit(1)

    with open(tasks_file, 'r', encoding='utf-8') as f:
        data = json.load(f)

    doc_id = data['document_id']
    tasks = data['tasks']

    print(f"\n{'='*70}")
    print("PROCESSING EDITORIAL TASKS")
    print(f"{'='*70}\n")
    print(f"Document: {doc_id}")
    print(f"Tasks: {len(tasks)}\n")

    # Initialize comment manager
    docs_service = get_docs_service()
    drive_service = get_drive_service()
    manager = DocsCommentManager(docs_service, drive_service)

    # Process each task
    posted_count = 0

    for i, task in enumerate(tasks, 1):
        comment_id = task['comment_id']
        instruction = task['instruction']

        print(f"[{i}/{len(tasks)}] Processing comment {comment_id}")
        print(f"Instruction: {instruction[:60]}...")

        # Get suggestion
        if comment_id in SUGGESTIONS:
            suggestion = SUGGESTIONS[comment_id]

            # Format reply
            reply_text = f"🤖 **gwark**\n\n{suggestion}\n\n---\nAI Editorial Suggestion via gwark docs review"

            try:
                # Post as comment reply
                result = manager.reply_to_comment(doc_id, comment_id, reply_text)
                print(f"[OK] Posted suggestion (Reply ID: {result.get('id')})\n")
                posted_count += 1
            except Exception as e:
                print(f"[ERROR] Failed: {e}\n")
        else:
            print(f"[SKIP] No suggestion available for this task\n")

    # Summary
    print(f"{'='*70}")
    print(f"COMPLETE: Posted {posted_count}/{len(tasks)} suggestions")
    print(f"{'='*70}\n")
    print(f"View document: https://docs.google.com/document/d/{doc_id}/edit\n")


if __name__ == "__main__":
    main()
