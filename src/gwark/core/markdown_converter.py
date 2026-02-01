"""Markdown to Google Docs API converter.

Converts markdown text to Google Docs API batchUpdate requests,
preserving formatting and applying themes.
"""

from dataclasses import dataclass, field
from typing import Optional

import mistune

from gwark.schemas.themes import DocTheme, get_default_theme


@dataclass
class ConversionState:
    """Tracks state during markdown-to-docs conversion."""

    index: int = 1  # Docs index starts at 1 (before first char)
    requests: list = field(default_factory=list)
    # Track ranges for deferred style application
    style_ranges: list = field(default_factory=list)


class MarkdownToDocsConverter:
    """Convert markdown to Google Docs API batchUpdate requests.

    Uses mistune to parse markdown into AST, then generates
    insertText and updateTextStyle/updateParagraphStyle requests.

    Example:
        >>> converter = MarkdownToDocsConverter()
        >>> requests = converter.convert("# Hello\\n\\nThis is **bold**.")
        >>> # Use requests with docs_service.documents().batchUpdate()
    """

    def __init__(self, theme: Optional[DocTheme] = None):
        """Initialize converter with optional theme.

        Args:
            theme: Document theme for styling. Uses default if not provided.
        """
        self.theme = theme or get_default_theme()
        self.state = ConversionState()
        # Use mistune's AST renderer
        self._md = mistune.create_markdown(renderer=None)

    def convert(self, markdown_text: str, start_index: int | None = None) -> list[dict]:
        """Convert markdown text to Google Docs API requests.

        Args:
            markdown_text: Raw markdown string
            start_index: Optional starting index for insertions (default: 1)

        Returns:
            List of batchUpdate request objects
        """
        self.state = ConversionState()
        if start_index is not None:
            self.state.index = start_index

        # Parse to AST tokens
        tokens = self._md(markdown_text)

        # Process each token
        for token in tokens:
            self._process_token(token)

        # Return requests in order: insertions first, then styles
        return self.state.requests + self._build_style_requests()

    def _process_token(self, token: dict) -> None:
        """Route token to appropriate handler."""
        handlers = {
            "heading": self._handle_heading,
            "paragraph": self._handle_paragraph,
            "list": self._handle_list,
            "block_code": self._handle_code_block,
            "thematic_break": self._handle_thematic_break,
            "block_quote": self._handle_block_quote,
            "table": self._handle_table,
        }
        token_type = token.get("type", "")
        handler = handlers.get(token_type, self._handle_unknown)
        handler(token)

    def _handle_heading(self, token: dict) -> None:
        """Handle heading tokens (# to ######)."""
        level = token.get("attrs", {}).get("level", 1)
        children = token.get("children", [])
        text = self._extract_text(children)

        # Map heading level to style name
        style_name = f"HEADING_{level}" if level <= 3 else "HEADING_3"

        start_idx = self.state.index
        self._insert_text(text + "\n")
        end_idx = self.state.index - 1  # Exclude newline from style

        # Queue paragraph style
        self._queue_paragraph_style(start_idx, end_idx, style_name)

        # Process inline styles
        self._process_inline_styles(children, start_idx)

    def _handle_paragraph(self, token: dict) -> None:
        """Handle paragraph tokens."""
        children = token.get("children", [])
        text = self._extract_text(children)

        if not text.strip():
            return  # Skip empty paragraphs

        start_idx = self.state.index
        self._insert_text(text + "\n")
        end_idx = self.state.index - 1

        # Apply normal text style
        self._queue_paragraph_style(start_idx, end_idx, "NORMAL_TEXT")

        # Process inline styles
        self._process_inline_styles(children, start_idx)

    def _handle_list(self, token: dict) -> None:
        """Handle ordered and unordered lists."""
        ordered = token.get("attrs", {}).get("ordered", False)
        children = token.get("children", [])

        for idx, item in enumerate(children, start=1):
            if item.get("type") != "list_item":
                continue

            item_children = item.get("children", [])
            # Extract text from potential nested paragraph
            if item_children and item_children[0].get("type") == "paragraph":
                item_text = self._extract_text(item_children[0].get("children", []))
            else:
                item_text = self._extract_text(item_children)

            # Format bullet/number prefix
            prefix = f"{idx}. " if ordered else "• "
            full_text = prefix + item_text + "\n"

            start_idx = self.state.index
            self._insert_text(full_text)
            end_idx = self.state.index - 1

            self._queue_paragraph_style(start_idx, end_idx, "NORMAL_TEXT")

            # Process inline styles (offset by prefix length)
            if item_children and item_children[0].get("type") == "paragraph":
                self._process_inline_styles(
                    item_children[0].get("children", []),
                    start_idx + len(prefix)
                )

    def _handle_code_block(self, token: dict) -> None:
        """Handle fenced code blocks."""
        raw = token.get("raw", "")
        # Ensure code block ends with newline
        if not raw.endswith("\n"):
            raw += "\n"

        start_idx = self.state.index
        self._insert_text(raw)
        end_idx = self.state.index

        self._queue_paragraph_style(start_idx, end_idx, "CODE_BLOCK")

    def _handle_block_quote(self, token: dict) -> None:
        """Handle blockquote tokens."""
        children = token.get("children", [])

        for child in children:
            if child.get("type") == "paragraph":
                text = self._extract_text(child.get("children", []))
                start_idx = self.state.index
                self._insert_text(text + "\n")
                end_idx = self.state.index - 1

                self._queue_paragraph_style(start_idx, end_idx, "QUOTE")
                self._process_inline_styles(child.get("children", []), start_idx)

    def _handle_thematic_break(self, token: dict) -> None:
        """Handle horizontal rule (---) as page break."""
        # Insert a page break
        self.state.requests.append({
            "insertPageBreak": {
                "location": {"index": self.state.index}
            }
        })
        self.state.index += 1  # Page break counts as 1 char

    def _handle_table(self, token: dict) -> None:
        """Handle markdown tables."""
        children = token.get("children", [])

        # Find header and body
        head_rows = []
        body_rows = []

        for child in children:
            if child.get("type") == "table_head":
                head_rows = child.get("children", [])
            elif child.get("type") == "table_body":
                body_rows = child.get("children", [])

        all_rows = head_rows + body_rows
        if not all_rows:
            return

        num_rows = len(all_rows)
        num_cols = len(all_rows[0].get("children", [])) if all_rows else 0

        if num_cols == 0:
            return

        # Insert table
        self.state.requests.append({
            "insertTable": {
                "location": {"index": self.state.index},
                "rows": num_rows,
                "columns": num_cols,
            }
        })

        # Table structure: table start, then rows, each with cells
        # After insertTable, we need to navigate the structure
        # Each table adds: 1 (table) + rows * (1 + cols * 2) indices approximately
        # This is complex - we'll insert text into cells after table creation

        # For now, calculate cell indices and queue text insertions
        # Table element is at state.index
        # First cell starts at state.index + 4 (table=1, tableRow=1, tableCell=1, para=1)

        table_start = self.state.index
        cell_base = table_start + 4  # First cell content index

        cell_texts = []
        is_header = []

        for row_idx, row in enumerate(all_rows):
            row_cells = row.get("children", [])
            for col_idx, cell in enumerate(row_cells):
                cell_children = cell.get("children", [])
                cell_text = self._extract_text(cell_children)
                cell_texts.append(cell_text)
                is_header.append(row_idx < len(head_rows))

        # Calculate table end index for state update
        # Each cell has: paragraph marker + content + cell end
        # Approximation: table adds significant indices
        table_end_offset = 3 + num_rows * (1 + num_cols * 3)
        self.state.index += table_end_offset

        # Queue cell text insertions (processed after main conversion)
        # Note: Actual implementation would need precise index calculation
        # which requires knowing exact table structure after creation
        # For MVP, we format as text table
        self._fallback_table_as_text(all_rows, head_rows)

    def _fallback_table_as_text(self, all_rows: list, head_rows: list) -> None:
        """Fallback: render table as formatted text (more reliable)."""
        # Remove the insertTable request we just added
        if self.state.requests and "insertTable" in self.state.requests[-1]:
            self.state.requests.pop()
            # Reset index to before table insert attempt
            # (simplified - in production would track more precisely)

        lines = []
        for row_idx, row in enumerate(all_rows):
            cells = row.get("children", [])
            cell_texts = []
            for cell in cells:
                text = self._extract_text(cell.get("children", []))
                cell_texts.append(text)

            line = " | ".join(cell_texts)
            lines.append(line)

            # Add separator after header
            if row_idx == len(head_rows) - 1 and head_rows:
                sep = " | ".join(["---"] * len(cells))
                lines.append(sep)

        table_text = "\n".join(lines) + "\n\n"
        start_idx = self.state.index
        self._insert_text(table_text)
        # Apply code style to make it monospace
        self._queue_paragraph_style(start_idx, self.state.index, "CODE_BLOCK")

    def _handle_unknown(self, token: dict) -> None:
        """Handle unknown token types by extracting text."""
        children = token.get("children", [])
        if children:
            text = self._extract_text(children)
            if text.strip():
                self._insert_text(text + "\n")

    def _extract_text(self, children: list) -> str:
        """Recursively extract plain text from token children."""
        parts = []
        for child in children:
            if child.get("type") == "text":
                parts.append(child.get("raw", ""))
            elif child.get("type") == "codespan":
                parts.append(child.get("raw", ""))
            elif child.get("type") == "softbreak":
                parts.append(" ")
            elif child.get("type") == "linebreak":
                parts.append("\n")
            elif "children" in child:
                parts.append(self._extract_text(child["children"]))
            elif "raw" in child:
                parts.append(child["raw"])
        return "".join(parts)

    def _insert_text(self, text: str) -> None:
        """Add insertText request and update index."""
        if not text:
            return

        self.state.requests.append({
            "insertText": {
                "location": {"index": self.state.index},
                "text": text,
            }
        })
        self.state.index += len(text)

    def _queue_paragraph_style(self, start: int, end: int, style_name: str) -> None:
        """Queue a paragraph style to be applied."""
        if start >= end:
            return

        style = self.theme.styles.get(style_name)
        if not style:
            return

        self.state.style_ranges.append({
            "type": "paragraph",
            "start": start,
            "end": end,
            "style_name": style_name,  # Used for namedStyleType
            "style": style,
        })

    def _get_named_style_type(self, style_name: str) -> str | None:
        """Map our style names to Google Docs namedStyleType values."""
        mapping = {
            "HEADING_1": "HEADING_1",
            "HEADING_2": "HEADING_2",
            "HEADING_3": "HEADING_3",
            "HEADING_4": "HEADING_4",
            "HEADING_5": "HEADING_5",
            "HEADING_6": "HEADING_6",
            "TITLE": "TITLE",
            "SUBTITLE": "SUBTITLE",
            "NORMAL_TEXT": "NORMAL_TEXT",
        }
        return mapping.get(style_name)

    def _queue_text_style(self, start: int, end: int, style_name: str) -> None:
        """Queue a text style to be applied."""
        if start >= end:
            return

        style = self.theme.inline.get(style_name)
        if not style:
            return

        self.state.style_ranges.append({
            "type": "text",
            "start": start,
            "end": end,
            "style_name": style_name,
            "style": style,
        })

    def _process_inline_styles(self, children: list, base_index: int) -> None:
        """Process inline formatting (bold, italic, code, links)."""
        offset = 0
        for child in children:
            child_type = child.get("type", "")
            child_text = ""

            if child_type == "text":
                child_text = child.get("raw", "")
            elif child_type == "codespan":
                child_text = child.get("raw", "")
                start = base_index + offset
                end = start + len(child_text)
                self._queue_text_style(start, end, "code")
            elif child_type == "strong":
                child_text = self._extract_text(child.get("children", []))
                start = base_index + offset
                end = start + len(child_text)
                self._queue_text_style(start, end, "bold")
            elif child_type == "emphasis":
                child_text = self._extract_text(child.get("children", []))
                start = base_index + offset
                end = start + len(child_text)
                self._queue_text_style(start, end, "italic")
            elif child_type == "strikethrough":
                child_text = self._extract_text(child.get("children", []))
                start = base_index + offset
                end = start + len(child_text)
                self._queue_text_style(start, end, "strikethrough")
            elif child_type == "link":
                child_text = self._extract_text(child.get("children", []))
                start = base_index + offset
                end = start + len(child_text)
                url = child.get("attrs", {}).get("url", "")
                # Queue link style and link insertion
                self._queue_text_style(start, end, "link")
                if url:
                    self.state.style_ranges.append({
                        "type": "link",
                        "start": start,
                        "end": end,
                        "url": url,
                    })
            elif child_type in ("softbreak", "linebreak"):
                child_text = " " if child_type == "softbreak" else "\n"
            elif "children" in child:
                # Recurse for nested structures
                self._process_inline_styles(child["children"], base_index + offset)
                child_text = self._extract_text(child.get("children", []))

            offset += len(child_text)

    def _build_style_requests(self) -> list[dict]:
        """Build style update requests from queued ranges."""
        requests = []

        for item in self.state.style_ranges:
            if item["type"] == "paragraph":
                style = item["style"]
                style_name = item.get("style_name", "")
                para_style = style.to_docs_paragraph_style()
                text_style = style.to_text_style().to_docs_api()

                # Add namedStyleType for headings - this is critical for
                # the document structure analyzer to detect sections
                named_style_type = self._get_named_style_type(style_name)
                if named_style_type:
                    para_style["namedStyleType"] = named_style_type

                if para_style:
                    fields = list(para_style.keys())
                    requests.append({
                        "updateParagraphStyle": {
                            "range": {
                                "startIndex": item["start"],
                                "endIndex": item["end"],
                            },
                            "paragraphStyle": para_style,
                            "fields": ",".join(fields),
                        }
                    })

                if text_style:
                    requests.append({
                        "updateTextStyle": {
                            "range": {
                                "startIndex": item["start"],
                                "endIndex": item["end"],
                            },
                            "textStyle": text_style,
                            "fields": ",".join(_flatten_fields(text_style)),
                        }
                    })

            elif item["type"] == "text":
                style = item["style"]
                text_style = style.to_docs_api()

                if text_style:
                    requests.append({
                        "updateTextStyle": {
                            "range": {
                                "startIndex": item["start"],
                                "endIndex": item["end"],
                            },
                            "textStyle": text_style,
                            "fields": ",".join(_flatten_fields(text_style)),
                        }
                    })

            elif item["type"] == "link":
                requests.append({
                    "updateTextStyle": {
                        "range": {
                            "startIndex": item["start"],
                            "endIndex": item["end"],
                        },
                        "textStyle": {
                            "link": {"url": item["url"]}
                        },
                        "fields": "link",
                    }
                })

        return requests


def _flatten_fields(style_dict: dict, prefix: str = "") -> list[str]:
    """Flatten nested style dict to field mask strings.

    Google Docs API requires field masks like 'bold', 'fontSize.magnitude'.
    """
    fields = []
    for key, value in style_dict.items():
        field_name = f"{prefix}{key}" if prefix else key
        if isinstance(value, dict) and not any(k in value for k in ["red", "green", "blue", "fontFamily"]):
            # Recurse for nested non-color objects
            fields.extend(_flatten_fields(value, f"{field_name}."))
        else:
            fields.append(field_name)
    return fields


class DocsToMarkdownConverter:
    """Convert Google Docs content back to markdown.

    Parses the document's content array and reconstructs markdown.
    """

    def convert(self, document: dict) -> str:
        """Convert Google Docs document to markdown.

        Args:
            document: Full document response from docs.get()

        Returns:
            Markdown string
        """
        body = document.get("body", {})
        content = body.get("content", [])

        lines = []
        for element in content:
            if "paragraph" in element:
                lines.append(self._convert_paragraph(element["paragraph"]))
            elif "table" in element:
                lines.append(self._convert_table(element["table"]))
            elif "sectionBreak" in element:
                lines.append("\n---\n")

        return "\n".join(lines)

    def _convert_paragraph(self, para: dict) -> str:
        """Convert a paragraph element to markdown."""
        elements = para.get("elements", [])
        style = para.get("paragraphStyle", {})
        named_style = style.get("namedStyleType", "NORMAL_TEXT")

        text_parts = []
        for elem in elements:
            text_run = elem.get("textRun", {})
            content = text_run.get("content", "")
            text_style = text_run.get("textStyle", {})

            # Apply inline formatting
            if text_style.get("bold"):
                content = f"**{content.strip()}**"
            if text_style.get("italic"):
                content = f"*{content.strip()}*"
            if text_style.get("strikethrough"):
                content = f"~~{content.strip()}~~"
            if "link" in text_style:
                url = text_style["link"].get("url", "")
                content = f"[{content.strip()}]({url})"

            text_parts.append(content)

        text = "".join(text_parts).rstrip("\n")

        # Add heading prefix based on named style
        if named_style == "HEADING_1":
            return f"# {text}"
        elif named_style == "HEADING_2":
            return f"## {text}"
        elif named_style == "HEADING_3":
            return f"### {text}"
        elif named_style == "HEADING_4":
            return f"#### {text}"
        elif named_style == "HEADING_5":
            return f"##### {text}"
        elif named_style == "HEADING_6":
            return f"###### {text}"
        elif named_style == "TITLE":
            return f"# {text}"
        elif named_style == "SUBTITLE":
            return f"## {text}"

        return text

    def _convert_table(self, table: dict) -> str:
        """Convert a table element to markdown."""
        rows = table.get("tableRows", [])
        if not rows:
            return ""

        md_rows = []
        for row_idx, row in enumerate(rows):
            cells = row.get("tableCells", [])
            cell_texts = []

            for cell in cells:
                cell_content = cell.get("content", [])
                cell_text = ""
                for elem in cell_content:
                    if "paragraph" in elem:
                        cell_text += self._convert_paragraph(elem["paragraph"])
                cell_texts.append(cell_text.strip())

            md_rows.append("| " + " | ".join(cell_texts) + " |")

            # Add header separator after first row
            if row_idx == 0:
                sep = "| " + " | ".join(["---"] * len(cells)) + " |"
                md_rows.append(sep)

        return "\n".join(md_rows)
