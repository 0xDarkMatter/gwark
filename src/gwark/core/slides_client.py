"""Google Slides client wrapper.

High-level wrapper around Google Slides API for elegant presentation operations.
Uses gwark's OAuth system for authentication.

Example:
    >>> from gwark.core.slides_client import SlidesClient
    >>> client = SlidesClient.from_gwark_auth()
    >>> presentations = client.list_presentations()
    >>> structure = client.get_presentation_structure("PRESENTATION_ID")
"""

import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple


@dataclass
class SlideElement:
    """Represents an element on a slide."""
    object_id: str
    element_type: str  # "SHAPE", "IMAGE", "TABLE", "VIDEO", "LINE", "GROUP"
    placeholder_type: Optional[str] = None  # "TITLE", "BODY", "SUBTITLE", etc.
    text_content: str = ""
    position: Dict[str, float] = field(default_factory=dict)
    size: Dict[str, float] = field(default_factory=dict)


@dataclass
class SlideInfo:
    """Information about a single slide."""
    slide_id: str
    object_id: str
    index: int
    title: str = ""
    speaker_notes: str = ""
    layout_name: str = ""
    elements: List[SlideElement] = field(default_factory=list)

    @property
    def element_count(self) -> int:
        return len(self.elements)


@dataclass
class PresentationStructure:
    """Parsed presentation structure."""
    presentation_id: str
    title: str
    revision_id: str
    locale: str
    page_width: float  # Points
    page_height: float  # Points
    slides: List[SlideInfo] = field(default_factory=list)

    @property
    def slide_count(self) -> int:
        return len(self.slides)

    def get_slide(self, index: int) -> Optional[SlideInfo]:
        """Get slide by index (0-based)."""
        if 0 <= index < len(self.slides):
            return self.slides[index]
        return None

    def find_slide_by_title(self, title: str) -> Optional[SlideInfo]:
        """Find slide by title (partial match, case-insensitive)."""
        title_lower = title.lower()
        for slide in self.slides:
            if title_lower in slide.title.lower():
                return slide
        return None


class SlidesClient:
    """High-level client for Google Slides operations.

    Provides a clean, Pythonic interface for presentation operations.
    Supports both simple operations and batch operations for efficiency.
    """

    # EMU to points conversion (914400 EMU = 1 inch = 72 points)
    EMU_TO_POINTS = 72 / 914400

    # Standard slide layouts
    LAYOUTS = {
        "BLANK": "BLANK",
        "TITLE": "TITLE",
        "TITLE_AND_BODY": "TITLE_AND_BODY",
        "TITLE_ONLY": "TITLE_ONLY",
        "SECTION_HEADER": "SECTION_HEADER",
        "TITLE_AND_TWO_COLUMNS": "TITLE_AND_TWO_COLUMNS",
        "ONE_COLUMN_TEXT": "ONE_COLUMN_TEXT",
        "MAIN_POINT": "MAIN_POINT",
        "BIG_NUMBER": "BIG_NUMBER",
    }

    def __init__(self, slides_service, drive_service):
        """Initialize with authenticated services.

        Args:
            slides_service: Authenticated Slides API service
            drive_service: Authenticated Drive API service (for listing)
        """
        self.slides = slides_service
        self.drive = drive_service

    @classmethod
    def from_gwark_auth(cls) -> "SlidesClient":
        """Create client using gwark's OAuth system.

        This is the recommended way to create a SlidesClient.
        Uses existing OAuth tokens from .gwark/tokens/ or triggers
        OAuth flow if needed.

        Returns:
            SlidesClient: Authenticated client ready for use

        Example:
            >>> client = SlidesClient.from_gwark_auth()
            >>> presentations = client.list_presentations()
        """
        from gmail_mcp.auth import get_slides_service, get_drive_service
        return cls(get_slides_service(), get_drive_service())

    # =========================================================================
    # LIST OPERATIONS (via Drive API - Slides API has no list endpoint)
    # =========================================================================

    def list_presentations(
        self,
        max_results: int = 50,
        query: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """List all accessible presentations.

        Uses Drive API since Slides API doesn't have a list endpoint.

        Args:
            max_results: Maximum number of results to return
            query: Optional search query to filter by name

        Returns:
            List of dicts with id, name, createdTime, modifiedTime
        """
        results = []
        page_token = None
        mime_type = "application/vnd.google-apps.presentation"

        while len(results) < max_results:
            # Build Drive API query
            q = f"mimeType='{mime_type}'"
            if query:
                q += f" and name contains '{query}'"

            response = self.drive.files().list(
                q=q,
                pageSize=min(100, max_results - len(results)),
                pageToken=page_token,
                fields="nextPageToken, files(id, name, createdTime, modifiedTime)",
                orderBy="modifiedTime desc",
            ).execute()

            files = response.get("files", [])
            results.extend(files)

            page_token = response.get("nextPageToken")
            if not page_token:
                break

        return [
            {
                "id": f.get("id"),
                "name": f.get("name"),
                "createdTime": f.get("createdTime"),
                "modifiedTime": f.get("modifiedTime"),
            }
            for f in results[:max_results]
        ]

    # =========================================================================
    # READ OPERATIONS
    # =========================================================================

    def get_presentation(self, presentation_id: str) -> Dict[str, Any]:
        """Get full presentation data.

        Args:
            presentation_id: Presentation ID or full URL

        Returns:
            Full presentation resource from API
        """
        presentation_id = self._extract_id(presentation_id)
        return self.slides.presentations().get(
            presentationId=presentation_id
        ).execute()

    def get_presentation_structure(
        self,
        presentation_id: str
    ) -> PresentationStructure:
        """Get parsed presentation structure.

        Parses the raw API response into a structured object
        with slide info, titles, and element details.

        Args:
            presentation_id: Presentation ID or URL

        Returns:
            PresentationStructure with parsed slide data
        """
        presentation = self.get_presentation(presentation_id)
        page_size = presentation.get("pageSize", {})

        structure = PresentationStructure(
            presentation_id=presentation.get("presentationId", ""),
            title=presentation.get("title", "Untitled"),
            revision_id=presentation.get("revisionId", ""),
            locale=presentation.get("locale", "en"),
            page_width=self._emu_to_points(
                page_size.get("width", {}).get("magnitude", 9144000)
            ),
            page_height=self._emu_to_points(
                page_size.get("height", {}).get("magnitude", 5143500)
            ),
        )

        for idx, slide in enumerate(presentation.get("slides", [])):
            structure.slides.append(self._parse_slide(slide, idx))

        return structure

    def _parse_slide(self, slide: Dict, index: int) -> SlideInfo:
        """Parse single slide from API response."""
        info = SlideInfo(
            slide_id=slide.get("objectId", ""),
            object_id=slide.get("objectId", ""),
            index=index,
            layout_name=self._get_layout_name(slide),
        )

        # Extract elements
        for element in slide.get("pageElements", []):
            elem_info = self._parse_element(element)
            if elem_info:
                info.elements.append(elem_info)

                # Check for title
                if elem_info.placeholder_type == "TITLE":
                    info.title = elem_info.text_content
                elif elem_info.placeholder_type == "CENTERED_TITLE":
                    info.title = elem_info.text_content

        # Extract speaker notes
        info.speaker_notes = self._extract_speaker_notes(slide)

        return info

    def _parse_element(self, element: Dict) -> Optional[SlideElement]:
        """Parse page element from API response."""
        object_id = element.get("objectId", "")
        transform = element.get("transform", {})
        size = element.get("size", {})

        # Determine element type
        if "shape" in element:
            shape = element["shape"]
            placeholder = shape.get("placeholder", {})
            text = self._extract_shape_text(shape)

            return SlideElement(
                object_id=object_id,
                element_type="SHAPE",
                placeholder_type=placeholder.get("type"),
                text_content=text,
                position={
                    "x": self._emu_to_points(transform.get("translateX", 0)),
                    "y": self._emu_to_points(transform.get("translateY", 0)),
                },
                size={
                    "width": self._emu_to_points(
                        size.get("width", {}).get("magnitude", 0)
                    ),
                    "height": self._emu_to_points(
                        size.get("height", {}).get("magnitude", 0)
                    ),
                },
            )

        elif "image" in element:
            return SlideElement(
                object_id=object_id,
                element_type="IMAGE",
            )

        elif "table" in element:
            return SlideElement(
                object_id=object_id,
                element_type="TABLE",
            )

        elif "video" in element:
            return SlideElement(
                object_id=object_id,
                element_type="VIDEO",
            )

        elif "line" in element:
            return SlideElement(
                object_id=object_id,
                element_type="LINE",
            )

        return None

    def _extract_shape_text(self, shape: Dict) -> str:
        """Extract text content from shape."""
        text_elements = shape.get("text", {}).get("textElements", [])
        parts = []
        for elem in text_elements:
            text_run = elem.get("textRun", {})
            content = text_run.get("content", "")
            if content.strip():
                parts.append(content)
        return "".join(parts).strip()

    def _extract_speaker_notes(self, slide: Dict) -> str:
        """Extract speaker notes from slide."""
        notes_page = slide.get("slideProperties", {}).get("notesPage", {})
        for element in notes_page.get("pageElements", []):
            if "shape" in element:
                shape = element["shape"]
                placeholder = shape.get("placeholder", {})
                if placeholder.get("type") == "BODY":
                    return self._extract_shape_text(shape)
        return ""

    def _get_layout_name(self, slide: Dict) -> str:
        """Get layout object ID for slide."""
        return slide.get("slideProperties", {}).get("layoutObjectId", "")

    # =========================================================================
    # CREATE OPERATIONS
    # =========================================================================

    def create_presentation(self, title: str) -> Dict[str, Any]:
        """Create a new empty presentation.

        Args:
            title: Title for the presentation

        Returns:
            Created presentation resource with id, url, etc.
        """
        body = {"title": title}
        presentation = self.slides.presentations().create(body=body).execute()
        return {
            "id": presentation.get("presentationId"),
            "title": presentation.get("title"),
            "url": f"https://docs.google.com/presentation/d/{presentation.get('presentationId')}/edit",
            "revisionId": presentation.get("revisionId"),
        }

    def create_from_template(
        self,
        title: str,
        template_id: str,
        folder_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Create presentation by copying a template.

        Args:
            title: Title for the new presentation
            template_id: ID of template presentation to copy
            folder_id: Optional folder ID to place the copy in

        Returns:
            Created presentation info with id and url
        """
        template_id = self._extract_id(template_id)

        # Use Drive API to copy
        body = {"name": title}
        if folder_id:
            body["parents"] = [folder_id]

        copied = self.drive.files().copy(
            fileId=template_id,
            body=body,
        ).execute()

        return {
            "id": copied.get("id"),
            "title": title,
            "url": f"https://docs.google.com/presentation/d/{copied.get('id')}/edit",
        }

    def add_slide(
        self,
        presentation_id: str,
        layout: str = "BLANK",
        position: Optional[int] = None,
    ) -> str:
        """Add a new slide to presentation.

        Args:
            presentation_id: Presentation ID or URL
            layout: Slide layout (BLANK, TITLE, TITLE_AND_BODY, etc.)
            position: Insert position (0-based, None = end)

        Returns:
            Created slide's object ID
        """
        presentation_id = self._extract_id(presentation_id)

        # Generate unique object ID
        import uuid
        slide_id = f"slide_{uuid.uuid4().hex[:8]}"

        request = {
            "createSlide": {
                "objectId": slide_id,
                "slideLayoutReference": {
                    "predefinedLayout": layout
                },
            }
        }

        if position is not None:
            request["createSlide"]["insertionIndex"] = position

        self.slides.presentations().batchUpdate(
            presentationId=presentation_id,
            body={"requests": [request]}
        ).execute()

        return slide_id

    # =========================================================================
    # UPDATE OPERATIONS (batchUpdate)
    # =========================================================================

    def batch_update(
        self,
        presentation_id: str,
        requests: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """Execute batch update with multiple requests.

        Args:
            presentation_id: Presentation ID or URL
            requests: List of batchUpdate request objects

        Returns:
            batchUpdate response
        """
        presentation_id = self._extract_id(presentation_id)
        return self.slides.presentations().batchUpdate(
            presentationId=presentation_id,
            body={"requests": requests}
        ).execute()

    def insert_text(
        self,
        presentation_id: str,
        shape_id: str,
        text: str,
        insertion_index: int = 0,
    ) -> None:
        """Insert text into a shape.

        Args:
            presentation_id: Presentation ID or URL
            shape_id: Target shape's object ID
            text: Text to insert
            insertion_index: Position to insert at (0 = start)
        """
        self.batch_update(presentation_id, [{
            "insertText": {
                "objectId": shape_id,
                "text": text,
                "insertionIndex": insertion_index,
            }
        }])

    def add_speaker_notes(
        self,
        presentation_id: str,
        slide_id: str,
        notes: str,
    ) -> None:
        """Add speaker notes to a slide.

        Args:
            presentation_id: Presentation ID or URL
            slide_id: Target slide's object ID
            notes: Speaker notes text
        """
        # Speaker notes shape has predictable ID pattern
        notes_shape_id = f"{slide_id}_speakerNotesPage_speakerNotesShape"
        self.insert_text(presentation_id, notes_shape_id, notes)

    def delete_slide(
        self,
        presentation_id: str,
        slide_id: str,
    ) -> None:
        """Delete a slide.

        Args:
            presentation_id: Presentation ID or URL
            slide_id: Slide's object ID to delete
        """
        self.batch_update(presentation_id, [{
            "deleteObject": {
                "objectId": slide_id
            }
        }])

    def move_slide(
        self,
        presentation_id: str,
        slide_id: str,
        new_position: int,
    ) -> None:
        """Move slide to a new position.

        Args:
            presentation_id: Presentation ID or URL
            slide_id: Slide's object ID
            new_position: New position (0-based index)
        """
        self.batch_update(presentation_id, [{
            "updateSlidesPosition": {
                "slideObjectIds": [slide_id],
                "insertionIndex": new_position
            }
        }])

    def replace_all_text(
        self,
        presentation_id: str,
        old_text: str,
        new_text: str,
        match_case: bool = True,
    ) -> int:
        """Replace all occurrences of text in presentation.

        Args:
            presentation_id: Presentation ID or URL
            old_text: Text to find
            new_text: Text to replace with
            match_case: Whether to match case

        Returns:
            Number of replacements made
        """
        response = self.batch_update(presentation_id, [{
            "replaceAllText": {
                "containsText": {
                    "text": old_text,
                    "matchCase": match_case,
                },
                "replaceText": new_text,
            }
        }])

        # Extract replacement count from response
        replies = response.get("replies", [])
        if replies:
            return replies[0].get("replaceAllText", {}).get("occurrencesChanged", 0)
        return 0

    # =========================================================================
    # EXPORT OPERATIONS
    # =========================================================================

    def export_as_pdf(
        self,
        presentation_id: str,
    ) -> bytes:
        """Export presentation as PDF.

        Uses Drive API export since Slides API doesn't support direct export.

        Args:
            presentation_id: Presentation ID or URL

        Returns:
            PDF file content as bytes
        """
        presentation_id = self._extract_id(presentation_id)
        return self.drive.files().export(
            fileId=presentation_id,
            mimeType="application/pdf"
        ).execute()

    # =========================================================================
    # HELPERS
    # =========================================================================

    @staticmethod
    def _extract_id(id_or_url: str) -> str:
        """Extract presentation ID from URL or return as-is.

        Handles:
        - https://docs.google.com/presentation/d/{ID}/edit
        - https://docs.google.com/presentation/d/{ID}/view
        - Raw presentation ID

        Args:
            id_or_url: Presentation ID or Google Slides URL

        Returns:
            Extracted presentation ID
        """
        match = re.search(r'/presentation/d/([a-zA-Z0-9_-]+)', id_or_url)
        return match.group(1) if match else id_or_url

    def _emu_to_points(self, emu: float) -> float:
        """Convert EMU (English Metric Units) to points."""
        return emu * self.EMU_TO_POINTS

    def get_presentation_url(self, presentation_id: str) -> str:
        """Get edit URL for presentation.

        Args:
            presentation_id: Presentation ID or URL

        Returns:
            Full Google Slides edit URL
        """
        presentation_id = self._extract_id(presentation_id)
        return f"https://docs.google.com/presentation/d/{presentation_id}/edit"
