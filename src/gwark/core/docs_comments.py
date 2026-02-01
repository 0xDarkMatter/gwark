"""Google Docs comment management.

Handles creating, listing, replying to, and resolving comments on Google Docs.

IMPORTANT LIMITATION:
The Google Drive API v3 does NOT support creating anchored comments in Google Docs
programmatically. Google Docs uses proprietary 'kix.*' anchor identifiers that are
not exposed through any public API.

What works via API:
    ✓ Create file-level comments (not anchored to specific text)
    ✓ List all comments (including anchored ones created in UI)
    ✓ Reply to any comment (file-level or anchored)
    ✓ Resolve/unresolve any comment

What doesn't work via API:
    ✗ Create NEW anchored comments (must use Google Docs UI)

For more information, see Google Issue Tracker #36763384:
https://issuetracker.google.com/issues/36763384

Hybrid workflow:
    1. Create anchored comments manually in Google Docs UI
    2. Use this API to list, reply to, and manage them
"""

from typing import Optional, List, Dict, Any


class DocsCommentManager:
    """Manage comments on Google Docs with text anchoring support."""

    def __init__(self, docs_service: Any, drive_service: Any):
        """Initialize comment manager with authenticated services.

        Args:
            docs_service: Authenticated Google Docs API service
            drive_service: Authenticated Google Drive API service
        """
        self.docs_service = docs_service
        self.drive_service = drive_service

    def add_comment_to_heading(
        self,
        document_id: str,
        heading_text: str,
        comment_text: str
    ) -> Dict[str, Any]:
        """Add a comment anchored to a specific heading.

        Args:
            document_id: Google Doc ID
            heading_text: Heading text to find and comment on
            comment_text: Comment content

        Returns:
            Created comment resource with id, content, author, etc.

        Raises:
            ValueError: If heading not found
        """
        # Find heading position (1-based indexing from Docs API)
        text_range = self._find_heading(document_id, heading_text)

        # Create anchored comment (convert to 0-based indexing for Drive API)
        return self._create_anchored_comment(
            document_id,
            text_range['startIndex'] - 1,  # Convert to 0-based
            text_range['endIndex'] - 1,
            comment_text
        )

    def add_comment_to_text(
        self,
        document_id: str,
        search_text: str,
        comment_text: str,
        occurrence: int = 1
    ) -> Dict[str, Any]:
        """Add a comment anchored to specific text.

        Args:
            document_id: Google Doc ID
            search_text: Text to find and comment on
            comment_text: Comment content
            occurrence: Which occurrence of the text (1-based)

        Returns:
            Created comment resource

        Raises:
            ValueError: If text not found
        """
        text_range = self._find_text(document_id, search_text, occurrence)

        return self._create_anchored_comment(
            document_id,
            text_range['startIndex'] - 1,  # Convert to 0-based
            text_range['endIndex'] - 1,
            comment_text
        )

    def add_file_comment(
        self,
        document_id: str,
        comment_text: str
    ) -> Dict[str, Any]:
        """Add a general file-level comment (not anchored to text).

        Args:
            document_id: Google Doc ID
            comment_text: Comment content

        Returns:
            Created comment resource
        """
        comment_body = {
            'content': comment_text,
        }

        return self.drive_service.comments().create(
            fileId=document_id,
            body=comment_body,
            fields='id,content,author,createdTime,resolved'
        ).execute()

    def list_comments(
        self,
        document_id: str,
        include_resolved: bool = False
    ) -> List[Dict[str, Any]]:
        """List all comments on a document.

        Args:
            document_id: Google Doc ID
            include_resolved: Whether to include resolved comments

        Returns:
            List of comment resources
        """
        result = self.drive_service.comments().list(
            fileId=document_id,
            includeDeleted=False,
            fields='comments(id,content,author,createdTime,anchor,resolved,replies,quotedFileContent)',
            pageSize=100
        ).execute()

        comments = result.get('comments', [])

        if not include_resolved:
            comments = [c for c in comments if not c.get('resolved', False)]

        return comments

    def reply_to_comment(
        self,
        document_id: str,
        comment_id: str,
        reply_text: str
    ) -> Dict[str, Any]:
        """Add a reply to an existing comment.

        Args:
            document_id: Google Doc ID
            comment_id: Comment ID to reply to
            reply_text: Reply content

        Returns:
            Created reply resource
        """
        reply_body = {'content': reply_text}

        return self.drive_service.replies().create(
            fileId=document_id,
            commentId=comment_id,
            body=reply_body,
            fields='id,content,author,createdTime'
        ).execute()

    def resolve_comment(
        self,
        document_id: str,
        comment_id: str
    ) -> Dict[str, Any]:
        """Mark a comment as resolved.

        Args:
            document_id: Google Doc ID
            comment_id: Comment ID to resolve

        Returns:
            Updated comment resource
        """
        # Get current comment to preserve content (API requires it)
        current = self.drive_service.comments().get(
            fileId=document_id,
            commentId=comment_id,
            fields='content'
        ).execute()

        return self.drive_service.comments().update(
            fileId=document_id,
            commentId=comment_id,
            body={
                'content': current.get('content', ''),  # Preserve original content
                'resolved': True
            },
            fields='id,resolved'
        ).execute()

    def unresolve_comment(
        self,
        document_id: str,
        comment_id: str
    ) -> Dict[str, Any]:
        """Reopen a resolved comment.

        Args:
            document_id: Google Doc ID
            comment_id: Comment ID to reopen

        Returns:
            Updated comment resource
        """
        # Get current comment to preserve content (API requires it)
        current = self.drive_service.comments().get(
            fileId=document_id,
            commentId=comment_id,
            fields='content'
        ).execute()

        return self.drive_service.comments().update(
            fileId=document_id,
            commentId=comment_id,
            body={
                'content': current.get('content', ''),  # Preserve original content
                'resolved': False
            },
            fields='id,resolved'
        ).execute()

    def _find_heading(
        self,
        document_id: str,
        heading_text: str
    ) -> Dict[str, int]:
        """Find a heading and return its range.

        Args:
            document_id: Google Doc ID
            heading_text: Heading text to search for

        Returns:
            Dict with startIndex and endIndex (1-based)

        Raises:
            ValueError: If heading not found
        """
        doc = self.docs_service.documents().get(documentId=document_id).execute()

        for element in doc.get('body', {}).get('content', []):
            if 'paragraph' not in element:
                continue

            para = element['paragraph']
            style = para.get('paragraphStyle', {}).get('namedStyleType', '')

            # Check if this is a heading
            if style.startswith('HEADING'):
                # Get full text of the paragraph
                full_text = ''.join(
                    run['textRun'].get('content', '')
                    for run in para.get('elements', [])
                    if 'textRun' in run
                )

                # Check if search text matches (case-insensitive, stripped)
                if heading_text.strip().lower() in full_text.strip().lower():
                    return {
                        'startIndex': element['startIndex'],
                        'endIndex': element['endIndex']
                    }

        raise ValueError(f"Heading containing '{heading_text}' not found in document")

    def _find_text(
        self,
        document_id: str,
        search_text: str,
        occurrence: int = 1
    ) -> Dict[str, int]:
        """Find nth occurrence of text in document.

        Args:
            document_id: Google Doc ID
            search_text: Text to search for
            occurrence: Which occurrence to find (1-based)

        Returns:
            Dict with startIndex and endIndex (1-based)

        Raises:
            ValueError: If text not found
        """
        doc = self.docs_service.documents().get(documentId=document_id).execute()

        char_index = 1  # Docs API uses 1-based indexing
        found_count = 0

        for element in doc.get('body', {}).get('content', []):
            if 'paragraph' not in element:
                continue

            para = element['paragraph']
            for text_run in para.get('elements', []):
                if 'textRun' not in text_run:
                    continue

                content = text_run['textRun'].get('content', '')

                # Check if search text is in this run (case-insensitive)
                if search_text.lower() in content.lower():
                    found_count += 1

                    if found_count == occurrence:
                        # Find exact position in content
                        offset = content.lower().index(search_text.lower())
                        return {
                            'startIndex': char_index + offset,
                            'endIndex': char_index + offset + len(search_text)
                        }

                char_index += len(content)

        if found_count == 0:
            raise ValueError(f"Text '{search_text}' not found in document")
        else:
            raise ValueError(
                f"Text '{search_text}' occurrence {occurrence} not found "
                f"(only {found_count} occurrence(s) exist)"
            )

    def _create_anchored_comment(
        self,
        document_id: str,
        start_index: int,
        end_index: int,
        comment_text: str
    ) -> Dict[str, Any]:
        """Create a comment anchored to a specific text range.

        Args:
            document_id: Google Doc ID
            start_index: Start position (0-based for Drive API)
            end_index: End position (0-based for Drive API)
            comment_text: Comment content

        Returns:
            Created comment resource
        """
        # NOTE: This method is kept for completeness but has limited functionality.
        # The Google Drive API v3 does NOT support creating anchored comments in Google Docs.
        # Google Docs uses proprietary 'kix.*' anchors that are not exposed through any API.
        # This method will create a FILE-LEVEL comment regardless of the anchor parameter.
        #
        # For anchored comments:
        #   - Create them manually in the Google Docs UI
        #   - Use list_comments() to read them
        #   - Use reply_to_comment() and resolve_comment() to manage them
        #
        # See: https://issuetracker.google.com/issues/36763384

        comment_body = {
            'content': comment_text,
            'anchor': {
                'r': 'document',  # Resource type
                'a': [
                    {
                        'txt': {
                            's': start_index,  # Already 0-based
                            'e': end_index,
                            'l': 'en'  # Language
                        }
                    }
                ]
            }
        }

        # The anchor parameter will be silently ignored by the API for Google Docs
        return self.drive_service.comments().create(
            fileId=document_id,
            body=comment_body,
            fields='id,content,author,createdTime,anchor,resolved'
        ).execute()
