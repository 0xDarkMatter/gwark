"""Document theme schemas for gwark Google Docs integration."""

from typing import Optional

from pydantic import BaseModel, Field


class TextStyle(BaseModel):
    """Text formatting style for inline elements."""

    font_family: Optional[str] = Field(default=None, description="Font family name")
    font_size: Optional[int] = Field(default=None, description="Font size in points")
    bold: Optional[bool] = Field(default=None, description="Bold text")
    italic: Optional[bool] = Field(default=None, description="Italic text")
    underline: Optional[bool] = Field(default=None, description="Underline text")
    strikethrough: Optional[bool] = Field(default=None, description="Strikethrough text")
    color: Optional[str] = Field(default=None, description="Text color as hex (e.g., #1a1a2e)")
    background_color: Optional[str] = Field(default=None, description="Background color as hex")

    def to_docs_api(self) -> dict:
        """Convert to Google Docs API textStyle format."""
        style: dict = {}

        if self.bold is not None:
            style["bold"] = self.bold
        if self.italic is not None:
            style["italic"] = self.italic
        if self.underline is not None:
            style["underline"] = self.underline
        if self.strikethrough is not None:
            style["strikethrough"] = self.strikethrough

        if self.font_family:
            style["weightedFontFamily"] = {"fontFamily": self.font_family}

        if self.font_size:
            style["fontSize"] = {"magnitude": self.font_size, "unit": "PT"}

        if self.color:
            style["foregroundColor"] = {"color": {"rgbColor": _hex_to_rgb(self.color)}}

        if self.background_color:
            style["backgroundColor"] = {"color": {"rgbColor": _hex_to_rgb(self.background_color)}}

        return style


class ParagraphStyle(BaseModel):
    """Paragraph formatting style including text and spacing."""

    # Inherit text styles for convenience
    font_family: Optional[str] = Field(default=None, description="Font family name")
    font_size: Optional[int] = Field(default=None, description="Font size in points")
    bold: Optional[bool] = Field(default=None, description="Bold text")
    italic: Optional[bool] = Field(default=None, description="Italic text")
    color: Optional[str] = Field(default=None, description="Text color as hex")

    # Paragraph-specific
    space_before: Optional[int] = Field(default=None, description="Space before paragraph in PT")
    space_after: Optional[int] = Field(default=None, description="Space after paragraph in PT")
    line_spacing: Optional[float] = Field(default=None, description="Line spacing multiplier (e.g., 1.15)")
    alignment: Optional[str] = Field(
        default=None,
        description="Text alignment: START, CENTER, END, JUSTIFIED"
    )
    indent_first_line: Optional[int] = Field(default=None, description="First line indent in PT")
    indent_start: Optional[int] = Field(default=None, description="Start indent in PT")

    # Border (bottom only for dividers/answer fields)
    border_bottom_color: Optional[str] = Field(default=None, description="Bottom border color as hex")
    border_bottom_width: Optional[float] = Field(default=None, description="Bottom border width in PT")
    border_bottom_style: Optional[str] = Field(default=None, description="Border style: SOLID, DOTTED, DASHED")

    def to_text_style(self) -> TextStyle:
        """Extract text style portion."""
        return TextStyle(
            font_family=self.font_family,
            font_size=self.font_size,
            bold=self.bold,
            italic=self.italic,
            color=self.color,
        )

    def to_docs_paragraph_style(self) -> dict:
        """Convert to Google Docs API paragraphStyle format."""
        style: dict = {}

        if self.alignment:
            style["alignment"] = self.alignment

        if self.line_spacing:
            style["lineSpacing"] = self.line_spacing * 100  # API uses percentage

        if self.space_before is not None:
            style["spaceAbove"] = {"magnitude": self.space_before, "unit": "PT"}

        if self.space_after is not None:
            style["spaceBelow"] = {"magnitude": self.space_after, "unit": "PT"}

        if self.indent_first_line is not None:
            style["indentFirstLine"] = {"magnitude": self.indent_first_line, "unit": "PT"}

        if self.indent_start is not None:
            style["indentStart"] = {"magnitude": self.indent_start, "unit": "PT"}

        if self.border_bottom_color:
            style["borderBottom"] = {
                "color": {"color": {"rgbColor": _hex_to_rgb(self.border_bottom_color)}},
                "width": {"magnitude": self.border_bottom_width or 1, "unit": "PT"},
                "dashStyle": self.border_bottom_style or "SOLID",
                "padding": {"magnitude": 4, "unit": "PT"},
            }

        return style


class DocTheme(BaseModel):
    """Complete document theme with paragraph and inline styles."""

    name: str = Field(description="Theme name")
    description: str = Field(default="", description="Theme description")

    # Named paragraph styles (TITLE, HEADING_1, HEADING_2, NORMAL_TEXT, etc.)
    styles: dict[str, ParagraphStyle] = Field(
        default_factory=dict,
        description="Named paragraph styles"
    )

    # Inline styles for markdown elements (bold, italic, code, link, etc.)
    inline: dict[str, TextStyle] = Field(
        default_factory=dict,
        description="Inline text styles for markdown elements"
    )

    class Config:
        """Pydantic config."""
        extra = "allow"


def _hex_to_rgb(hex_color: str) -> dict:
    """Convert hex color string to Google Docs RGB format.

    Args:
        hex_color: Color in hex format (e.g., "#1a1a2e" or "1a1a2e")

    Returns:
        Dict with red, green, blue values as floats 0-1
    """
    hex_color = hex_color.lstrip("#")
    return {
        "red": int(hex_color[0:2], 16) / 255,
        "green": int(hex_color[2:4], 16) / 255,
        "blue": int(hex_color[4:6], 16) / 255,
    }


def get_default_theme() -> DocTheme:
    """Return the default professional theme."""
    return DocTheme(
        name="professional",
        description="Clean professional style with Roboto font",
        styles={
            "TITLE": ParagraphStyle(
                font_family="Roboto",
                font_size=28,
                bold=True,
                color="#1a1a2e",
                space_after=20,
            ),
            "HEADING_1": ParagraphStyle(
                font_family="Roboto",
                font_size=20,
                bold=True,
                color="#16213e",
                space_before=24,
                space_after=12,
            ),
            "HEADING_2": ParagraphStyle(
                font_family="Roboto",
                font_size=16,
                bold=True,
                color="#0f3460",
                space_before=18,
                space_after=8,
            ),
            "HEADING_3": ParagraphStyle(
                font_family="Roboto",
                font_size=14,
                bold=True,
                color="#1a1a2e",
                space_before=14,
                space_after=6,
            ),
            "NORMAL_TEXT": ParagraphStyle(
                font_family="Roboto",
                font_size=11,
                color="#333333",
                line_spacing=1.15,
                space_after=8,
            ),
            "QUOTE": ParagraphStyle(
                font_family="Roboto",
                font_size=11,
                italic=True,
                color="#555555",
                indent_start=36,
                space_before=8,
                space_after=8,
            ),
            "CODE_BLOCK": ParagraphStyle(
                font_family="Roboto Mono",
                font_size=10,
                color="#2d2d2d",
                space_before=8,
                space_after=8,
            ),
            "DIVIDER": ParagraphStyle(
                space_before=12,
                space_after=12,
                border_bottom_color="#cccccc",
                border_bottom_width=0.5,
                border_bottom_style="SOLID",
            ),
            "ANSWER_FIELD": ParagraphStyle(
                font_family="Roboto",
                font_size=11,
                color="#999999",
                space_before=4,
                space_after=8,
                border_bottom_color="#cccccc",
                border_bottom_width=1,
                border_bottom_style="SOLID",
            ),
        },
        inline={
            "bold": TextStyle(bold=True),
            "italic": TextStyle(italic=True),
            "code": TextStyle(
                font_family="Roboto Mono",
                font_size=10,
                background_color="#f5f5f5",
            ),
            "link": TextStyle(
                color="#1a73e8",
                underline=True,
            ),
            "strikethrough": TextStyle(strikethrough=True),
        },
    )
