"""Markdown to Google Docs API converter.

Converts markdown text to Google Docs API batchUpdate requests,
preserving formatting and applying themes.

Three-phase request model:
  Phase 1: insertText, insertTable, insertPageBreak  (state.requests)
  Phase 2: createParagraphBullets                     (state.bullet_ranges)
  Phase 3: updateParagraphStyle, updateTextStyle      (state.style_ranges)
"""

import re
from dataclasses import dataclass, field
from typing import Optional

import mistune

from gwark.schemas.themes import DocTheme, get_default_theme


@dataclass
class ConversionState:
    """Tracks state during markdown-to-docs conversion."""

    index: int = 1  # Docs index starts at 1 (before first char)
    requests: list = field(default_factory=list)
    bullet_ranges: list = field(default_factory=list)
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

    def __init__(
        self,
        theme: Optional[DocTheme] = None,
        use_native_tables: bool = True,
    ):
        self.theme = theme or get_default_theme()
        self.use_native_tables = use_native_tables
        self.state = ConversionState()
        # Use mistune's AST renderer with plugins for tables, strikethrough, task lists
        self._md = mistune.create_markdown(
            renderer=None,
            plugins=['table', 'strikethrough', 'task_lists'],
        )

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

        # Pre-process: convert bare checkbox lines to task list syntax
        # [ ] Item or [x] Item → - [ ] Item or - [x] Item
        processed = re.sub(
            r'^(\[[ xX]\])', r'- \1', markdown_text, flags=re.MULTILINE
        )

        # Pre-process: mark *** as page breaks (distinct from --- dividers)
        processed = re.sub(
            r'^\*{3,}\s*$', '<!-- GWARK_PAGE_BREAK -->', processed, flags=re.MULTILINE
        )

        # Parse to AST tokens
        tokens = self._md(processed)

        # Process each token
        for token in tokens:
            self._process_token(token)

        # Three-phase return: insertions → bullets → styles
        return (
            self.state.requests
            + self._build_bullet_requests()
            + self._build_style_requests()
        )

    def _process_token(self, token: dict) -> None:
        """Route token to appropriate handler."""
        handlers = {
            "heading": self._handle_heading,
            "paragraph": self._handle_paragraph,
            "list": self._handle_list,
            "block_code": self._handle_code_block,
            "thematic_break": self._handle_thematic_break,
            "block_quote": self._handle_block_quote,
            "block_html": self._handle_block_html,
            "table": self._handle_table,
        }
        token_type = token.get("type", "")
        handler = handlers.get(token_type, self._handle_unknown)
        handler(token)

    # ── Block handlers ──────────────────────────────────────────────

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
        """Handle paragraph tokens, with answer field detection."""
        children = token.get("children", [])
        text = self._extract_text(children)

        if not text.strip():
            return  # Skip empty paragraphs

        # Answer field: line of 3+ underscores only → styled answer area
        if re.match(r'^_{3,}$', text.strip()):
            start_idx = self.state.index
            self._insert_text(" \n")
            end_idx = self.state.index - 1
            self._queue_paragraph_style(start_idx, end_idx, "ANSWER_FIELD")
            return

        start_idx = self.state.index
        self._insert_text(text + "\n")
        end_idx = self.state.index - 1

        # Apply normal text style
        self._queue_paragraph_style(start_idx, end_idx, "NORMAL_TEXT")

        # Process inline styles
        self._process_inline_styles(children, start_idx)

    def _handle_list(self, token: dict, nesting_level: int = 0) -> None:
        """Handle ordered and unordered lists with native Google Docs bullets."""
        ordered = token.get("attrs", {}).get("ordered", False)
        default_preset = "NUMBERED_DECIMAL_NESTED" if ordered else "BULLET_DISC_CIRCLE_SQUARE"
        children = token.get("children", [])

        for item in children:
            item_type = item.get("type", "")
            if item_type not in ("list_item", "task_list_item"):
                continue

            item_children = item.get("children", [])

            # Determine preset — task_list_item (from mistune plugin) uses checkbox
            is_task = item_type == "task_list_item"
            is_checked = item.get("attrs", {}).get("checked", False) if is_task else False
            preset = "BULLET_CHECKBOX" if is_task else default_preset

            # Extract text from nested paragraph or block_text
            first_child_type = item_children[0].get("type", "") if item_children else ""
            if first_child_type in ("paragraph", "block_text"):
                item_text = self._extract_text(item_children[0].get("children", []))
                inline_children = item_children[0].get("children", [])
            else:
                item_text = self._extract_text(item_children)
                inline_children = item_children

            # Prepend ☑ for checked task items (API can't set checked state)
            if is_checked:
                item_text = "☑ " + item_text

            start_idx = self.state.index
            self._insert_text(item_text + "\n")
            end_idx = self.state.index  # Include newline for bullet range

            # Queue bullet creation
            self.state.bullet_ranges.append({
                "start": start_idx,
                "end": end_idx,
                "preset": preset,
                "nesting_level": nesting_level,
            })

            # Queue paragraph style
            self._queue_paragraph_style(start_idx, end_idx - 1, "NORMAL_TEXT")

            # Process inline styles
            self._process_inline_styles(inline_children, start_idx)

            # Handle nested lists (remaining children after first content)
            for sub_child in item_children[1:]:
                if sub_child.get("type") == "list":
                    self._handle_list(sub_child, nesting_level=nesting_level + 1)

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
        """Handle --- as a styled horizontal divider."""
        start_idx = self.state.index
        self._insert_text(" \n")
        end_idx = self.state.index - 1
        self._queue_paragraph_style(start_idx, end_idx, "DIVIDER")

    def _handle_block_html(self, token: dict) -> None:
        """Handle HTML blocks — specifically our page break sentinel."""
        raw = token.get("raw", "")
        if "GWARK_PAGE_BREAK" in raw:
            self.state.requests.append({
                "insertPageBreak": {
                    "location": {"index": self.state.index}
                }
            })
            self.state.index += 1

    def _handle_table(self, token: dict) -> None:
        """Handle markdown tables with native Google Docs tables."""
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
        num_cols = max(len(row.get("children", [])) for row in all_rows) if all_rows else 0

        if num_cols == 0:
            return

        if not self.use_native_tables:
            self._fallback_table_as_text(all_rows, head_rows)
            return

        table_start = self.state.index

        # Insert the table structure
        self.state.requests.append({
            "insertTable": {
                "location": {"index": table_start},
                "rows": num_rows,
                "columns": num_cols,
            }
        })

        # Google Docs table index structure:
        # table(1) + per row: tableRow(1) + per cell: tableCell(1) + paragraph_newline(1)
        # Total structural size = 1 + num_rows * (1 + 2 * num_cols)
        # Cell(r, c) content index = table_start + 3 + r * (1 + 2*num_cols) + 2*c
        table_size = 1 + num_rows * (1 + 2 * num_cols)

        # Collect cell data with target indices
        cell_insertions = []  # (index, text, is_header)

        for r, row in enumerate(all_rows):
            cells = row.get("children", [])
            for c, cell in enumerate(cells):
                cell_children = cell.get("children", [])
                cell_text = self._extract_text(cell_children)
                if cell_text:
                    idx = table_start + 3 + r * (1 + 2 * num_cols) + 2 * c
                    cell_insertions.append((idx, cell_text, r < len(head_rows)))

        # Insert cell content in REVERSE order to preserve index stability
        for idx, text, is_header in reversed(cell_insertions):
            self.state.requests.append({
                "insertText": {
                    "location": {"index": idx},
                    "text": text,
                }
            })
            # Bold header cells
            if is_header:
                self.state.style_ranges.append({
                    "type": "text",
                    "start": idx,
                    "end": idx + len(text),
                    "style_name": "bold",
                    "style": self.theme.inline.get("bold"),
                })

        # Advance state index past the table
        total_text_len = sum(len(t) for _, t, _ in cell_insertions)
        self.state.index += table_size + total_text_len

    def _fallback_table_as_text(self, all_rows: list, head_rows: list) -> None:
        """Fallback: render table as formatted text (more reliable)."""
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

    # ── Text extraction ─────────────────────────────────────────────

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

    # ── Style queueing ──────────────────────────────────────────────

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

    # ── Request builders ────────────────────────────────────────────

    def _build_bullet_requests(self) -> list[dict]:
        """Build createParagraphBullets requests from queued ranges (Phase 2)."""
        requests = []
        for item in self.state.bullet_ranges:
            requests.append({
                "createParagraphBullets": {
                    "range": {
                        "startIndex": item["start"],
                        "endIndex": item["end"],
                    },
                    "bulletPreset": item["preset"],
                }
            })
            # Set nesting indentation for nested lists
            if item["nesting_level"] > 0:
                indent_pt = 36 * (item["nesting_level"] + 1)
                requests.append({
                    "updateParagraphStyle": {
                        "range": {
                            "startIndex": item["start"],
                            "endIndex": item["end"],
                        },
                        "paragraphStyle": {
                            "indentStart": {"magnitude": indent_pt, "unit": "PT"},
                            "indentFirstLine": {"magnitude": indent_pt, "unit": "PT"},
                        },
                        "fields": "indentStart,indentFirstLine",
                    }
                })
        return requests

    def _build_style_requests(self) -> list[dict]:
        """Build style update requests from queued ranges (Phase 3)."""
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
                if style is None:
                    continue
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


# ── Reverse converter: Google Docs → Markdown ───────────────────────


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
        self._lists = document.get("lists", {})
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
        bullet = para.get("bullet")

        text_parts = []
        for elem in elements:
            text_run = elem.get("textRun", {})
            content = text_run.get("content", "")
            text_style = text_run.get("textStyle", {})

            # Detect inline code via monospace font
            font_family = text_style.get("weightedFontFamily", {}).get("fontFamily", "")
            is_code = font_family in ("Roboto Mono", "Courier New", "Consolas", "Source Code Pro")

            # Apply inline formatting
            if is_code and not text_style.get("bold"):
                content = f"`{content.strip()}`"
            elif text_style.get("bold"):
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

        # Handle bullet/list paragraphs
        if bullet:
            list_id = bullet.get("listId", "")
            nesting = bullet.get("nestingLevel", 0)
            indent = "  " * nesting

            # Determine ordered vs unordered from document lists
            is_ordered = False
            is_checkbox = False
            if list_id and list_id in self._lists:
                list_props = self._lists[list_id].get("listProperties", {})
                nesting_levels = list_props.get("nestingLevels", [])
                if nesting < len(nesting_levels):
                    glyph_type = nesting_levels[nesting].get("glyphType", "")
                    glyph_symbol = nesting_levels[nesting].get("glyphSymbol", "")
                    if glyph_type in ("DECIMAL", "ALPHA", "UPPER_ALPHA", "ROMAN", "UPPER_ROMAN"):
                        is_ordered = True
                    if glyph_symbol == "☐" or "CHECKBOX" in glyph_type.upper() if glyph_type else False:
                        is_checkbox = True

            if is_checkbox:
                # Detect checked state from ☑ prefix
                if text.startswith("☑ "):
                    return f"{indent}- [x] {text[2:]}"
                return f"{indent}- [ ] {text}"
            elif is_ordered:
                return f"{indent}1. {text}"
            else:
                return f"{indent}- {text}"

        # Detect divider (empty paragraph with bottom border)
        if not text.strip() and style.get("borderBottom"):
            return "\n---\n"

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
