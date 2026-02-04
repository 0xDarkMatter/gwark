# gwark Themes Reference

Complete specification for Google Docs themes in gwark.

## Theme File Location

Themes are YAML files stored in:
- Project: `.gwark/themes/<name>.yaml`
- Global: `~/.gwark/themes/<name>.yaml`

## Theme Structure

```yaml
name: theme-name
description: Theme description

# Paragraph styles (applied to headings, body text, etc.)
styles:
  TITLE:
    font_family: Roboto
    font_size: 32
    bold: true
    color: "#1a1a2e"
    space_after: 24

  HEADING_1:
    font_family: Roboto
    font_size: 24
    bold: true
    color: "#16213e"
    space_before: 28
    space_after: 14

  HEADING_2:
    font_family: Roboto
    font_size: 18
    bold: true
    color: "#0f3460"
    space_before: 20
    space_after: 10

  HEADING_3:
    font_family: Roboto
    font_size: 14
    bold: true
    color: "#1a1a2e"
    space_before: 14
    space_after: 6

  NORMAL_TEXT:
    font_family: Roboto
    font_size: 11
    color: "#333333"
    line_spacing: 1.15
    space_after: 8

  QUOTE:
    font_family: Roboto
    font_size: 11
    italic: true
    color: "#555555"
    indent_start: 36
    space_before: 8
    space_after: 8

  CODE_BLOCK:
    font_family: Roboto Mono
    font_size: 10
    color: "#2d2d2d"
    space_before: 8
    space_after: 8

# Inline styles (applied to bold, italic, code spans, links)
inline:
  bold:
    bold: true

  italic:
    italic: true

  code:
    font_family: Roboto Mono
    font_size: 10
    background_color: "#f5f5f5"

  link:
    color: "#1a73e8"
    underline: true

  strikethrough:
    strikethrough: true
```

## Style Properties

### Text Properties

| Property | Type | Description | Example |
|----------|------|-------------|---------|
| `font_family` | string | Font name | `"Roboto"`, `"Arial"`, `"Georgia"` |
| `font_size` | int | Size in points | `11`, `14`, `24` |
| `bold` | bool | Bold weight | `true`, `false` |
| `italic` | bool | Italic style | `true`, `false` |
| `underline` | bool | Underline | `true`, `false` |
| `strikethrough` | bool | Strikethrough | `true`, `false` |
| `color` | string | Hex color | `"#1a1a2e"`, `"#333333"` |
| `background_color` | string | Background hex | `"#f5f5f5"`, `"#ffffcc"` |

### Paragraph Properties

| Property | Type | Description | Example |
|----------|------|-------------|---------|
| `space_before` | int | Space above (PT) | `24`, `14` |
| `space_after` | int | Space below (PT) | `12`, `8` |
| `line_spacing` | float | Line height multiplier | `1.15`, `1.5` |
| `alignment` | string | Text alignment | `"START"`, `"CENTER"`, `"END"`, `"JUSTIFIED"` |
| `indent_first_line` | int | First line indent (PT) | `36` |
| `indent_start` | int | Left indent (PT) | `36` |

## Named Style Types

These map to Google Docs built-in styles:

| Style Name | Usage |
|------------|-------|
| `TITLE` | Document title |
| `HEADING_1` | Top-level heading |
| `HEADING_2` | Second-level heading |
| `HEADING_3` | Third-level heading |
| `NORMAL_TEXT` | Body paragraphs |
| `QUOTE` | Block quotes |
| `CODE_BLOCK` | Code blocks |

## Built-in Theme: Professional

```yaml
name: professional
description: Clean professional style with Roboto font

styles:
  TITLE:
    font_family: Roboto
    font_size: 28
    bold: true
    color: "#1a1a2e"
    space_after: 20

  HEADING_1:
    font_family: Roboto
    font_size: 20
    bold: true
    color: "#16213e"
    space_before: 24
    space_after: 12

  HEADING_2:
    font_family: Roboto
    font_size: 16
    bold: true
    color: "#0f3460"
    space_before: 18
    space_after: 8

  HEADING_3:
    font_family: Roboto
    font_size: 14
    bold: true
    color: "#1a1a2e"
    space_before: 14
    space_after: 6

  NORMAL_TEXT:
    font_family: Roboto
    font_size: 11
    color: "#333333"
    line_spacing: 1.15
    space_after: 8

  QUOTE:
    font_family: Roboto
    font_size: 11
    italic: true
    color: "#555555"
    indent_start: 36
    space_before: 8
    space_after: 8

  CODE_BLOCK:
    font_family: Roboto Mono
    font_size: 10
    color: "#2d2d2d"
    space_before: 8
    space_after: 8

inline:
  bold:
    bold: true
  italic:
    italic: true
  code:
    font_family: Roboto Mono
    font_size: 10
    background_color: "#f5f5f5"
  link:
    color: "#1a73e8"
    underline: true
  strikethrough:
    strikethrough: true
```

## Example: Brand Theme

```yaml
# .gwark/themes/evolution7.yaml
name: evolution7
description: Evolution 7 brand theme - Roboto with E7 teal/navy palette

styles:
  TITLE:
    font_family: Roboto
    font_size: 32
    bold: true
    color: "#002d3c"        # Dark navy
    space_after: 24

  HEADING_1:
    font_family: Roboto
    font_size: 24
    bold: false
    color: "#60b2d3"        # Light teal
    space_before: 28
    space_after: 14

  HEADING_2:
    font_family: Roboto
    font_size: 18
    bold: false
    color: "#60b2d3"        # Light teal
    space_before: 20
    space_after: 10

  HEADING_3:
    font_family: Roboto
    font_size: 14
    bold: true
    color: "#002d3c"        # Dark navy
    space_before: 16
    space_after: 8

  NORMAL_TEXT:
    font_family: Roboto
    font_size: 11
    color: "#333333"
    line_spacing: 1.15
    space_after: 8

  QUOTE:
    font_family: Roboto
    font_size: 11
    italic: true
    color: "#002d3c"
    indent_start: 36

  CODE_BLOCK:
    font_family: Roboto Mono
    font_size: 10
    color: "#002d3c"

inline:
  bold:
    bold: true
  italic:
    italic: true
  code:
    font_family: Roboto Mono
    font_size: 10
    background_color: "#e8f4f8"
  link:
    color: "#60b2d3"
    underline: true
```

## Theme Application

### Apply to Existing Document

```bash
gwark docs theme --apply evolution7 --doc DOC_ID
```

### Create Document with Theme

```bash
gwark docs create "Report Title" --file report.md --theme evolution7
```

### Check Available Themes

```bash
gwark docs theme --list
```

### Inspect Theme Details

```bash
gwark docs theme --show evolution7
```

## Inline Formatting Behavior

When applying themes, gwark preserves inline formatting (bold, italic) within NORMAL_TEXT paragraphs. This prevents theme application from overwriting intentional inline emphasis.

For heading styles (TITLE, HEADING_1, etc.), the full text style is applied since headings typically shouldn't have mixed formatting.
