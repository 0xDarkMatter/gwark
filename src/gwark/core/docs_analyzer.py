"""Document structure analyzer for Google Docs.

Parses Google Docs API responses to extract semantic structure (headings, sections)
for collaborative-friendly editing operations.
"""

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class Section:
    """Represents a document section (heading + content until next heading)."""

    heading_text: str
    heading_level: int  # 0=TITLE, 1-6=HEADING_1-6, 99=not a heading
    start_index: int  # Where heading starts
    end_index: int  # Where section ends (start of next heading or doc end)
    content_start: int  # Where content starts (after heading newline)

    @property
    def content_length(self) -> int:
        """Length of section content (excluding heading)."""
        return self.end_index - self.content_start

    @property
    def total_length(self) -> int:
        """Total length of section (including heading)."""
        return self.end_index - self.start_index


@dataclass
class DocumentStructure:
    """Parsed document structure for semantic operations."""

    title: str
    revision_id: str
    sections: list[Section] = field(default_factory=list)
    total_length: int = 0

    def find_section(self, heading_text: str) -> Optional[Section]:
        """Find section by heading text (case-insensitive partial match).

        Args:
            heading_text: Text to search for in section headings

        Returns:
            First matching Section or None
        """
        heading_lower = heading_text.lower().strip()
        for section in self.sections:
            if heading_lower in section.heading_text.lower():
                return section
        return None

    def find_section_exact(self, heading_text: str) -> Optional[Section]:
        """Find section by exact heading text match (case-insensitive).

        Args:
            heading_text: Exact heading text to match

        Returns:
            Matching Section or None
        """
        heading_lower = heading_text.lower().strip()
        for section in self.sections:
            if section.heading_text.lower().strip() == heading_lower:
                return section
        return None

    def get_section_content_range(self, heading_text: str) -> Optional[tuple[int, int]]:
        """Get content range for a section (excluding heading).

        Args:
            heading_text: Text to search for in section headings

        Returns:
            Tuple of (start_index, end_index) for content, or None
        """
        section = self.find_section(heading_text)
        if section:
            return (section.content_start, section.end_index)
        return None

    def get_section_by_index(self, index: int) -> Optional[Section]:
        """Get section at the given index (0-based).

        Args:
            index: Section index

        Returns:
            Section at index or None if out of bounds
        """
        if 0 <= index < len(self.sections):
            return self.sections[index]
        return None

    def get_section_index(self, heading_text: str) -> int:
        """Get index of section by heading text.

        Args:
            heading_text: Text to search for in section headings

        Returns:
            Section index or -1 if not found
        """
        heading_lower = heading_text.lower().strip()
        for i, section in enumerate(self.sections):
            if heading_lower in section.heading_text.lower():
                return i
        return -1


class DocsStructureAnalyzer:
    """Analyze Google Docs structure for semantic operations.

    Parses a Google Docs API document response and extracts the heading/section
    structure with precise index positions for targeted editing.

    Example:
        >>> analyzer = DocsStructureAnalyzer()
        >>> structure = analyzer.analyze(doc_response)
        >>> intro = structure.find_section("Introduction")
        >>> print(f"Insert after intro at index {intro.end_index}")
    """

    def analyze(self, document: dict) -> DocumentStructure:
        """Parse document and extract section structure.

        Args:
            document: Full document response from docs.documents().get()

        Returns:
            DocumentStructure with parsed sections
        """
        body = document.get("body", {})
        content = body.get("content", [])

        structure = DocumentStructure(
            title=document.get("title", "Untitled"),
            revision_id=document.get("revisionId", ""),
        )

        current_section: Optional[Section] = None

        for element in content:
            if "paragraph" not in element:
                continue

            para = element["paragraph"]
            style = para.get("paragraphStyle", {})
            named_style = style.get("namedStyleType", "NORMAL_TEXT")

            start_idx = element.get("startIndex", 0)
            end_idx = element.get("endIndex", 0)

            # Check if this is a heading
            if named_style.startswith("HEADING_") or named_style == "TITLE":
                # Close previous section
                if current_section:
                    current_section.end_index = start_idx
                    structure.sections.append(current_section)

                # Extract heading text
                heading_text = self._extract_paragraph_text(para)
                level = self._get_heading_level(named_style)

                current_section = Section(
                    heading_text=heading_text,
                    heading_level=level,
                    start_index=start_idx,
                    end_index=0,  # Will be set when next section found
                    content_start=end_idx,  # Content starts after heading
                )

            structure.total_length = max(structure.total_length, end_idx)

        # Close final section
        if current_section:
            current_section.end_index = structure.total_length
            structure.sections.append(current_section)

        return structure

    def _extract_paragraph_text(self, para: dict) -> str:
        """Extract text from paragraph elements.

        Args:
            para: Paragraph element from document content

        Returns:
            Plain text content of the paragraph
        """
        text_parts = []
        for elem in para.get("elements", []):
            text_run = elem.get("textRun", {})
            text_parts.append(text_run.get("content", ""))
        return "".join(text_parts).strip()

    def _get_heading_level(self, named_style: str) -> int:
        """Convert named style to heading level.

        Args:
            named_style: Google Docs namedStyleType

        Returns:
            Heading level: 0=TITLE, 1-6=HEADING_X, 99=not a heading
        """
        if named_style == "TITLE":
            return 0
        if named_style.startswith("HEADING_"):
            try:
                return int(named_style.split("_")[1])
            except (IndexError, ValueError):
                return 1
        return 99  # Not a heading


def format_structure_table(structure: DocumentStructure) -> str:
    """Format document structure as a readable table.

    Args:
        structure: Parsed document structure

    Returns:
        Formatted table string
    """
    lines = []
    lines.append(f"Document: {structure.title}")
    lines.append(f"Revision: {structure.revision_id[:12]}..." if len(structure.revision_id) > 12 else f"Revision: {structure.revision_id}")
    lines.append("")

    # Table header
    lines.append("| # | Level | Heading | Start | End | Size |")
    lines.append("|---|-------|---------|-------|-----|------|")

    for i, section in enumerate(structure.sections):
        level_str = "TITLE" if section.heading_level == 0 else f"H{section.heading_level}"
        heading = section.heading_text[:30] + "..." if len(section.heading_text) > 30 else section.heading_text
        lines.append(
            f"| {i} | {level_str} | {heading} | {section.start_index} | {section.end_index} | {section.total_length} |"
        )

    lines.append("")
    lines.append(f"Total sections: {len(structure.sections)}")
    lines.append(f"Document length: {structure.total_length} characters")

    return "\n".join(lines)


def format_structure_tree(structure: DocumentStructure) -> str:
    """Format document structure as an indented tree.

    Args:
        structure: Parsed document structure

    Returns:
        Tree-formatted string
    """
    lines = []
    lines.append(f"[doc] {structure.title}")
    lines.append("")

    for i, section in enumerate(structure.sections):
        # Indent based on heading level
        level = section.heading_level if section.heading_level > 0 else 1
        indent = "  " * (level - 1)

        # Use ASCII-safe tree characters
        is_last = i == len(structure.sections) - 1
        prefix = "`-" if is_last else "+-"

        size_info = f"({section.total_length} chars)"
        level_tag = f"H{section.heading_level}" if section.heading_level > 0 else "TITLE"
        lines.append(f"{indent}{prefix} [{level_tag}] {section.heading_text} {size_info}")

    return "\n".join(lines)
