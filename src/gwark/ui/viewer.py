"""Interactive results viewer using Textual or Rich."""

import re
import webbrowser
from typing import Any

from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.text import Text

# Textual imports (lazy loaded for --tui mode)
def _get_textual_imports():
    from textual.app import App, ComposeResult
    from textual.binding import Binding
    from textual.containers import Container
    from textual.widgets import DataTable, Footer, Header, Static
    from textual.screen import ModalScreen
    return App, ComposeResult, Binding, Container, DataTable, Footer, Header, Static, ModalScreen


def extract_name(email_str: str) -> str:
    """Extract just the name from 'Name <email>' format."""
    if not email_str:
        return ""
    # Try to extract name from "Name <email@domain.com>" format
    match = re.match(r'^"?([^"<]+)"?\s*<', email_str)
    if match:
        return match.group(1).strip()
    # Try email prefix if no name
    match = re.match(r'^([^@<]+)@', email_str)
    if match:
        return match.group(1).strip()
    # Just return first part
    return email_str.split('<')[0].strip()[:20]


def short_date(date_str: str) -> str:
    """Extract short date like 'Jan 08' from various formats."""
    if not date_str:
        return ""
    # Parse "Thu, 08 Jan 2026" or similar formats
    import re
    # Match day and month: "08 Jan" or "Jan 08"
    match = re.search(r'(\d{1,2})\s+(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)', date_str, re.I)
    if match:
        return f"{match.group(2)} {int(match.group(1)):02d}"
    # Try reverse: "Jan 08"
    match = re.search(r'(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\s+(\d{1,2})', date_str, re.I)
    if match:
        return f"{match.group(1)} {int(match.group(2)):02d}"
    # Try numeric date
    match = re.match(r'(\d{1,2})[/-](\d{1,2})', date_str)
    if match:
        return f"{match.group(1)}/{match.group(2)}"
    # Already short enough
    if len(date_str) <= 8:
        return date_str
    return date_str[:8]


# =============================================================================
# Rich Terminal Viewer (default - matches terminal theme)
# =============================================================================

def strip_html(html: str) -> str:
    """Convert HTML to plain text, preserving links."""
    import re
    if not html or '<' not in html:
        return html

    # Extract links before stripping
    links = []
    for match in re.finditer(r'<a[^>]+href=["\']([^"\']+)["\'][^>]*>([^<]*)</a>', html, re.I):
        url, text = match.groups()
        if text.strip():
            links.append(f"{text.strip()} ({url})")

    # Remove script/style content
    text = re.sub(r'<(script|style)[^>]*>.*?</\1>', '', html, flags=re.DOTALL | re.I)
    # Replace br/p/div with newlines
    text = re.sub(r'<br\s*/?>', '\n', text, flags=re.I)
    text = re.sub(r'</?(p|div|tr|li)[^>]*>', '\n', text, flags=re.I)
    # Remove all other tags
    text = re.sub(r'<[^>]+>', '', text)
    # Decode entities
    text = re.sub(r'&nbsp;', ' ', text)
    text = re.sub(r'&amp;', '&', text)
    text = re.sub(r'&lt;', '<', text)
    text = re.sub(r'&gt;', '>', text)
    text = re.sub(r'&#\d+;', '', text)
    # Clean up whitespace
    text = re.sub(r'\n{3,}', '\n\n', text)
    text = re.sub(r' {2,}', ' ', text)

    # Append extracted links at end if any
    if links:
        text = text.strip() + "\n\n[Links]\n" + "\n".join(links[:10])

    return text.strip()


class TerminalEmailViewer:
    """Interactive terminal viewer using Rich with arrow key navigation."""

    def __init__(self, emails: list[dict[str, Any]], title: str = "Email Results") -> None:
        self.emails = self._normalize_emails(emails)
        self.title = title
        self.console = Console()
        self.selected = 0
        self.page_size = 20  # Visible rows

    def _normalize_emails(self, emails: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Normalize email data to standard format."""
        results = []
        for email in emails:
            # Body can be in body_full, body, or body_preview
            body = email.get("body_full") or email.get("body") or email.get("body_preview") or ""
            results.append({
                "date": email.get("date", email.get("formatted_date", "")),
                "from": email.get("from", email.get("sender", "")),
                "to": email.get("to", email.get("recipient", "")),
                "subject": email.get("subject", ""),
                "snippet": email.get("snippet", ""),
                "body": body,
                "link": email.get("link", email.get("gmail_link", "")),
                "id": email.get("id", email.get("message_id", "")),
            })
        return results

    def _build_table(self) -> Table:
        """Build Rich table with windowed view around selection."""
        # Calculate visible window
        half_page = self.page_size // 2
        start = max(0, self.selected - half_page)
        end = min(len(self.emails), start + self.page_size)
        # Adjust start if we're near the end
        if end == len(self.emails):
            start = max(0, end - self.page_size)

        table = Table(
            title=f"{self.title} ({self.selected + 1}/{len(self.emails)})",
            show_lines=False, expand=True, box=None
        )
        table.add_column("", width=2)  # Selection indicator
        table.add_column("Date", width=7)
        table.add_column("From", width=16)
        table.add_column("Subject", ratio=1)

        for i in range(start, end):
            email = self.emails[i]
            marker = "▶" if i == self.selected else " "
            style = "reverse" if i == self.selected else None
            table.add_row(
                marker,
                short_date(email["date"]),
                extract_name(email["from"])[:15],
                email["subject"][:70] + ("..." if len(email["subject"]) > 70 else ""),
                style=style,
            )
        return table

    def _show_email(self) -> None:
        """Display full email content."""
        import shutil
        email = self.emails[self.selected]

        # Get terminal height for scrolling
        term_height = shutil.get_terminal_size().lines - 10

        # Get and clean body
        body = email.get('body') or email.get('snippet') or '(No content)'
        body = strip_html(body)

        # Build content lines
        lines = [
            f"[dim]Email {self.selected + 1}/{len(self.emails)}[/]",
            "",
            f"[bold]From:[/] {email['from']}",
            f"[bold]To:[/] {email['to']}",
            f"[bold]Subject:[/] {email['subject']}",
            f"[bold]Date:[/] {email['date']}",
            "─" * 70,
            "",
        ]
        lines.extend(body.split('\n'))
        lines.append("")
        lines.append("─" * 70)

        # Simple scrolling view
        scroll_pos = 0
        while True:
            self.console.clear()
            # Show visible portion
            visible = lines[scroll_pos:scroll_pos + term_height]
            for line in visible:
                self.console.print(line)

            # Show scroll indicator
            if len(lines) > term_height:
                pct = int((scroll_pos / max(1, len(lines) - term_height)) * 100)
                self.console.print(f"\n[dim]↑↓ scroll | q/Esc: back | ({pct}%)[/]")
            else:
                self.console.print(f"\n[dim]q/Esc: back[/]")

            key = self._getch()
            if key in ('q', 'esc', 'enter'):
                break
            elif key == 'up' or key == 'k':
                scroll_pos = max(0, scroll_pos - 3)
            elif key == 'down' or key == 'j':
                scroll_pos = min(max(0, len(lines) - term_height), scroll_pos + 3)
            elif key == 'g':
                scroll_pos = 0
            elif key == 'G':
                scroll_pos = max(0, len(lines) - term_height)

    def _open_email(self) -> None:
        """Open current email in Gmail."""
        email = self.emails[self.selected]
        link = email.get("link")
        if not link and email.get("id"):
            link = f"https://mail.google.com/mail/u/0/#all/{email['id']}"
        if link:
            webbrowser.open(link)

    def _getch(self) -> str:
        """Get a single keypress."""
        import sys
        if sys.platform == 'win32':
            import msvcrt
            ch = msvcrt.getch()
            if ch in (b'\x00', b'\xe0'):  # Arrow key prefix on Windows
                ch2 = msvcrt.getch()
                if ch2 == b'H': return 'up'
                if ch2 == b'P': return 'down'
                if ch2 == b'K': return 'left'
                if ch2 == b'M': return 'right'
            if ch == b'\r': return 'enter'
            if ch == b'\x1b': return 'esc'
            return ch.decode('utf-8', errors='ignore').lower()
        else:
            import tty, termios
            fd = sys.stdin.fileno()
            old = termios.tcgetattr(fd)
            try:
                tty.setraw(fd)
                ch = sys.stdin.read(1)
                if ch == '\x1b':  # Escape sequence
                    ch2 = sys.stdin.read(2)
                    if ch2 == '[A': return 'up'
                    if ch2 == '[B': return 'down'
                    if ch2 == '[C': return 'right'
                    if ch2 == '[D': return 'left'
                    return 'esc'
                if ch == '\r' or ch == '\n': return 'enter'
                return ch.lower()
            finally:
                termios.tcsetattr(fd, termios.TCSADRAIN, old)

    def _render(self) -> None:
        """Render the current view."""
        self.console.clear()
        self.console.print(self._build_table())
        self.console.print()
        self.console.print("[dim]↑↓ Navigate | Enter: View | o: Open in Gmail | q: Quit[/]")

    def run(self) -> None:
        """Run the interactive viewer with keyboard navigation."""
        try:
            while True:
                self._render()
                key = self._getch()

                if key in ('q', 'esc'):
                    break
                elif key == 'up' or key == 'k':
                    self.selected = max(0, self.selected - 1)
                elif key == 'down' or key == 'j':
                    self.selected = min(len(self.emails) - 1, self.selected + 1)
                elif key == 'enter':
                    self._show_email()
                elif key == 'o':
                    self._open_email()
                elif key == 'g':  # Go to top
                    self.selected = 0
                elif key == 'G':  # Go to bottom (shift+g)
                    self.selected = len(self.emails) - 1
        except (KeyboardInterrupt, EOFError):
            pass
        finally:
            # Clean exit - hard reset terminal on Windows
            import os
            import sys
            if sys.platform == 'win32':
                os.system('cls')
            else:
                os.system('clear')
            print("Done.")


# =============================================================================
# Textual TUI Viewer (optional - use with --tui flag)
# =============================================================================

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Container
from textual.widgets import DataTable, Footer, Header, Static
from textual.screen import ModalScreen


class EmailDetailScreen(ModalScreen):
    """Modal screen showing email details."""

    CSS = """
    EmailDetailScreen {
        align: center middle;
        background: rgba(0, 0, 0, 0.7);
    }

    #detail-container {
        width: 85%;
        height: 85%;
        background: #1a1a1a;
        border: solid #444444;
        padding: 1 2;
    }

    #email-detail {
        height: 100%;
        overflow-y: auto;
    }
    """

    BINDINGS = [
        Binding("escape", "dismiss", "Close"),
        Binding("q", "dismiss", "Close"),
    ]

    def __init__(self, email: dict[str, Any]) -> None:
        super().__init__()
        self.email = email

    def compose(self) -> ComposeResult:
        with Container(id="detail-container"):
            yield Static(self._format_email(), id="email-detail")

    def _format_email(self) -> Text:
        """Format email for display."""
        text = Text()
        text.append("From: ", style="bold")
        text.append(f"{self.email.get('from', 'Unknown')}\n")
        text.append("To: ", style="bold")
        text.append(f"{self.email.get('to', 'Unknown')}\n")
        text.append("Subject: ", style="bold")
        text.append(f"{self.email.get('subject', 'No subject')}\n")
        text.append("Date: ", style="bold")
        text.append(f"{self.email.get('date', 'Unknown')}\n")
        text.append("\n" + "─" * 60 + "\n\n")

        # Show full body if available, otherwise snippet
        if self.email.get("body"):
            text.append(self.email["body"])
        elif self.email.get("snippet"):
            text.append(self.email["snippet"])
        else:
            text.append("(No content available)")

        return text


class ResultsViewer(App):
    """Interactive viewer for search results."""

    ENABLE_COMMAND_PALETTE = False  # Hide ^p palette
    ANSI_COLOR = True  # Use terminal's ANSI color palette

    # Use terminal's native colors
    CSS = """
    Screen {
        background: $background;
    }

    Header {
        background: $primary;
        color: $text;
        height: 1;
    }

    Footer {
        background: $primary;
    }

    #results-table {
        height: 100%;
    }

    DataTable {
        background: $background;
    }

    DataTable > .datatable--header {
        background: $primary;
        color: $text;
        text-style: bold;
    }

    DataTable > .datatable--cursor {
        background: $secondary;
        color: $text;
    }

    #status-bar {
        dock: bottom;
        height: 1;
        background: $primary;
        color: $text-muted;
        padding: 0 1;
    }
    """

    BINDINGS = [
        Binding("enter", "view_detail", "View"),
        Binding("o", "open_link", "Open in Gmail"),
        Binding("q", "quit", "Quit"),
        Binding("escape", "quit", "Quit", show=False),
        Binding("j", "cursor_down", "Down", show=False),
        Binding("k", "cursor_up", "Up", show=False),
        Binding("g", "scroll_top", "Top", show=False),
        Binding("G", "scroll_bottom", "Bottom", show=False),
    ]

    def __init__(
        self,
        results: list[dict[str, Any]],
        title: str = "Search Results",
        columns: list[str] | None = None,
    ) -> None:
        super().__init__()
        self.results = results
        self.title_text = title
        self.columns = columns or ["Date", "From", "Subject"]

    def compose(self) -> ComposeResult:
        yield Header()
        yield DataTable(id="results-table")
        yield Static(f" {len(self.results)} results", id="status-bar")
        yield Footer()

    def on_mount(self) -> None:
        """Set up the data table on mount."""
        table = self.query_one(DataTable)
        table.cursor_type = "row"
        table.zebra_stripes = True

        # Compact widths: date tight, from medium, subject gets the rest
        column_widths = {"date": 7, "from": 16, "to": 16, "subject": 70}
        for col in self.columns:
            width = column_widths.get(col.lower(), 20)
            table.add_column(col, key=col.lower(), width=width)

        # Add rows
        for i, result in enumerate(self.results):
            row_data = []
            for col in self.columns:
                col_lower = col.lower()
                value = result.get(col_lower, "")

                # Format based on column type
                if col_lower == "date":
                    value = short_date(value)
                elif col_lower in ("from", "to"):
                    value = extract_name(value)[:15]  # Trim to fit
                elif col_lower == "subject":
                    # Subject gets most space
                    if isinstance(value, str) and len(value) > 68:
                        value = value[:65] + "..."
                else:
                    if isinstance(value, str) and len(value) > 18:
                        value = value[:15] + "..."

                row_data.append(value)

            table.add_row(*row_data, key=str(i))

        # Focus table
        table.focus()

    def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        """Handle Enter key on table row."""
        self.action_view_detail()

    def action_view_detail(self) -> None:
        """View selected email details."""
        table = self.query_one(DataTable)
        if table.cursor_row is not None and table.cursor_row < len(self.results):
            email = self.results[table.cursor_row]
            self.push_screen(EmailDetailScreen(email))

    def action_open_link(self) -> None:
        """Open email in Gmail."""
        import webbrowser

        table = self.query_one(DataTable)
        if table.cursor_row is not None and table.cursor_row < len(self.results):
            email = self.results[table.cursor_row]
            link = email.get("link")
            # Construct Gmail link from ID if not set
            if not link and email.get("id"):
                link = f"https://mail.google.com/mail/u/0/#all/{email['id']}"
            if link:
                webbrowser.open(link)
                self.notify("Opening in browser...")
            else:
                self.notify("No link available", severity="warning")

    def action_cursor_down(self) -> None:
        """Move cursor down."""
        table = self.query_one(DataTable)
        table.action_cursor_down()

    def action_cursor_up(self) -> None:
        """Move cursor up."""
        table = self.query_one(DataTable)
        table.action_cursor_up()

    def action_scroll_top(self) -> None:
        """Scroll to top."""
        table = self.query_one(DataTable)
        table.move_cursor(row=0)

    def action_scroll_bottom(self) -> None:
        """Scroll to bottom."""
        table = self.query_one(DataTable)
        table.move_cursor(row=len(self.results) - 1)

    def action_quit(self) -> None:
        """Quit the application cleanly."""
        self.exit()


class EmailViewer(ResultsViewer):
    """Specialized viewer for email results."""

    def __init__(self, emails: list[dict[str, Any]], title: str = "Email Search Results") -> None:
        # Transform emails to standard format
        results = []
        for email in emails:
            results.append({
                "date": email.get("date", email.get("formatted_date", "")),
                "from": email.get("from", email.get("sender", "")),
                "to": email.get("to", email.get("recipient", "")),
                "subject": email.get("subject", ""),
                "snippet": email.get("snippet", ""),
                "body": email.get("body", ""),
                "link": email.get("link", email.get("gmail_link", "")),
                "id": email.get("id", email.get("message_id", "")),
            })

        super().__init__(results, title=title, columns=["Date", "From", "Subject"])


class TerminalCalendarViewer:
    """Week-based calendar viewer with Monday at top."""

    # Consistent separator style (closer dots)
    SEPARATOR = "·" * 45

    def __init__(self, meetings: list[dict[str, Any]], title: str = "Calendar") -> None:
        from datetime import date, timedelta

        self.title = title
        self.console = Console()
        self.meetings = sorted(meetings, key=lambda m: m.get("start", ""))
        self.grouped = self._group_by_day()
        self.flat_list = self._flatten()  # For navigation
        self.selected = 0
        self.show_weekends = True

        # Week navigation - start on Monday of current week
        today = date.today()
        self.current_week_monday = today - timedelta(days=today.weekday())  # Monday

        # Description scroll (for long descriptions)
        self.desc_scroll = 0
        self.desc_max_lines = 6

        # Find first event in current week
        self._select_first_in_week()

    def _get_monday(self, d) -> 'date':
        """Get Monday of the week containing date d."""
        from datetime import timedelta
        return d - timedelta(days=d.weekday())

    def _get_week_events(self) -> list:
        """Get indices of events in current week view."""
        from datetime import datetime, timedelta
        week_end = self.current_week_monday + timedelta(days=6 if self.show_weekends else 4)

        indices = []
        for i, (day_key, _, m) in enumerate(self.flat_list):
            # Use day_key (YYYY-MM-DD) which is already computed
            try:
                event_date = datetime.strptime(day_key, "%Y-%m-%d").date()
                if self.current_week_monday <= event_date <= week_end:
                    indices.append(i)
            except:
                pass
        return indices

    def _select_first_in_week(self) -> None:
        """Select first event in current week."""
        indices = self._get_week_events()
        if indices:
            self.selected = indices[0]

    def _select_last_in_week(self) -> None:
        """Select last event in current week."""
        indices = self._get_week_events()
        if indices:
            self.selected = indices[-1]

    def _is_working_location(self, meeting: dict) -> bool:
        """Check if event is a Working Location (Home/Office), not a real event."""
        summary = (meeting.get("summary") or "").lower().strip()
        # Google Calendar Working Location shows as all-day "Home" or "Office"
        if summary in ("home", "office", "working from home", "wfh"):
            if self._is_all_day(meeting):
                return True
        return False

    def _group_by_day(self) -> dict:
        """Group meetings by day, extracting working location."""
        from datetime import datetime
        grouped = {}
        for m in self.meetings:
            start = m.get("start", "")
            try:
                dt = datetime.fromisoformat(start.replace("Z", "+00:00"))
                day_key = dt.strftime("%Y-%m-%d")
                day_label = dt.strftime("%a, %b %d")
            except:
                day_key = "Unknown"
                day_label = "Unknown Date"

            if day_key not in grouped:
                grouped[day_key] = {"label": day_label, "meetings": [], "location": None}

            # Check if this is a working location indicator
            if self._is_working_location(m):
                grouped[day_key]["location"] = m.get("summary", "").strip()
            else:
                grouped[day_key]["meetings"].append(m)

        return grouped

    def _flatten(self) -> list:
        """Create flat list of (day_key, meeting_index) for navigation."""
        flat = []
        for day_key in sorted(self.grouped.keys()):
            for i, m in enumerate(self.grouped[day_key]["meetings"]):
                flat.append((day_key, i, m))
        return flat

    def _get_selected_meeting(self) -> dict:
        """Get currently selected meeting."""
        if 0 <= self.selected < len(self.flat_list):
            return self.flat_list[self.selected][2]
        return {}

    def _format_time(self, iso_str: str) -> str:
        """Format ISO time to 12hr format with am/pm."""
        try:
            from datetime import datetime
            dt = datetime.fromisoformat(iso_str.replace("Z", "+00:00"))
            return dt.strftime("%I:%M%p").lstrip("0").lower()  # "9:30am" not "09:30AM"
        except:
            return iso_str[:5] if iso_str else "--:--"

    def _format_duration(self, minutes: int) -> str:
        """Format duration nicely, handling multi-day events."""
        if minutes >= 1440:  # 24+ hours = multi-day event
            days = minutes // 1440
            if days >= 7:
                weeks = days // 7
                remaining_days = days % 7
                if remaining_days:
                    return f"{weeks}w {remaining_days}d"
                return f"{weeks} week{'s' if weeks > 1 else ''}"
            return f"{days} day{'s' if days > 1 else ''}"
        if minutes < 60:
            return f"{minutes}m"
        h, m = divmod(minutes, 60)
        return f"{h}h{m}m" if m else f"{h}h"

    def _is_all_day(self, meeting: dict) -> bool:
        """Check if event is an all-day event (no specific time)."""
        start = meeting.get("start", "")
        # All-day events typically have date-only format or 00:00 start
        if "T" not in start:
            return True
        if "T00:00:00" in start:
            return True
        return False

    def _is_multi_day(self, meeting: dict) -> bool:
        """Check if event spans multiple calendar days."""
        from datetime import datetime
        start = meeting.get("start", "")
        end = meeting.get("end", "")
        try:
            start_dt = datetime.fromisoformat(start.replace("Z", "+00:00"))
            end_dt = datetime.fromisoformat(end.replace("Z", "+00:00"))
            # Multi-day if different dates (not just duration > 24h)
            return start_dt.date() != end_dt.date()
        except:
            minutes = meeting.get("duration_minutes", 0)
            return minutes >= 1440

    def _format_date_range(self, start: str, end: str, force_range: bool = False) -> str:
        """Format a date range for multi-day events. Single all-day events just show one date."""
        from datetime import datetime
        try:
            start_dt = datetime.fromisoformat(start.replace("Z", "+00:00"))
            end_dt = datetime.fromisoformat(end.replace("Z", "+00:00"))

            # For single-day all-day events, just show the date
            if start_dt.date() == end_dt.date() or (
                (end_dt - start_dt).days <= 1 and not force_range
            ):
                return start_dt.strftime("%b %d")

            start_str = start_dt.strftime("%b %d")
            end_str = end_dt.strftime("%b %d")
            if start_dt.year != end_dt.year:
                start_str = start_dt.strftime("%b %d %Y")
                end_str = end_dt.strftime("%b %d %Y")
            return f"{start_str} - {end_str}"
        except:
            return ""

    def _build_left_pane(self) -> Panel:
        """Build week view with Monday at top."""
        from rich.text import Text
        from datetime import timedelta, date

        lines = Text()

        # Week header
        week_end = self.current_week_monday + timedelta(days=6)
        week_label = f"{self.current_week_monday.strftime('%b %d')} - {week_end.strftime('%b %d')}"
        lines.append(f" Week of {week_label}\n", style="bold")
        lines.append(self.SEPARATOR + "\n", style="dim")

        # Days to show (Mon-Sun or Mon-Fri)
        days_to_show = 7 if self.show_weekends else 5
        current_idx = 0

        for day_offset in range(days_to_show):
            day_date = self.current_week_monday + timedelta(days=day_offset)
            day_key = day_date.strftime("%Y-%m-%d")
            is_weekend = day_offset >= 5  # Sat=5, Sun=6
            is_today = day_date == date.today()

            # Day styling - today gets reverse highlight
            if is_today:
                day_style = "bold reverse yellow"
            elif is_weekend:
                day_style = "dim"
            else:
                day_style = "bold cyan"
            day_label = day_date.strftime("%a, %b %d")

            # Get working location if any
            day_data = self.grouped.get(day_key, {"label": day_label, "meetings": [], "location": None})
            location = day_data.get("location")
            location_str = f" ({location})" if location else ""
            today_marker = " ★" if is_today else ""

            # Day header with location
            lines.append(f"\n {day_label}{location_str}{today_marker}\n", style=day_style)

            # Events for this day
            meetings = day_data.get("meetings", [])
            if not meetings:
                lines.append("    (no events)\n", style="dim")
            else:
                for m in meetings:
                    # Find this meeting's index in flat_list
                    meeting_idx = None
                    for i, (dk, _, mtg) in enumerate(self.flat_list):
                        if dk == day_key and mtg.get("id") == m.get("id"):
                            meeting_idx = i
                            break

                    is_selected = meeting_idx == self.selected
                    is_all_day = self._is_all_day(m)
                    is_multi = self._is_multi_day(m)

                    # Time display
                    if is_all_day and not is_multi:
                        time_str = "all day"
                    elif is_multi:
                        time_str = self._format_date_range(m.get("start", ""), m.get("end", ""), force_range=True)
                    else:
                        time_str = self._format_time(m.get("start", ""))

                    duration = self._format_duration(m.get("duration_minutes", 0))
                    summary = m.get("summary", "No Title")[:24]

                    marker = "▸" if is_selected else " "
                    base_style = "dim" if is_weekend else None
                    style = "reverse bold" if is_selected else base_style

                    # Calendar color dot
                    cal_color = m.get("calendar_color", "#4285f4")

                    # Build line with color dot
                    lines.append(f"   {marker} ", style=style)
                    lines.append("●", style=cal_color)  # Colored dot
                    lines.append(f" {time_str:>8}  {summary:<24} {duration:>5}\n", style=style)

        # Add trailing space for height
        lines.append("\n")

        # Count for title
        week_events = sum(1 for dk, _, _ in self.flat_list
                        if self.current_week_monday <= self._parse_date(dk) <= week_end)

        return Panel(
            lines,
            title=f"[bold]{self.title}[/] ({week_events} events)",
            border_style="blue",
            padding=(1, 1),
        )

    def _parse_date(self, day_key: str):
        """Parse YYYY-MM-DD to date."""
        from datetime import datetime
        try:
            return datetime.strptime(day_key, "%Y-%m-%d").date()
        except:
            return self.current_week_monday

    def _build_right_pane(self) -> Panel:
        """Build the detail pane for selected meeting."""
        from rich.text import Text

        m = self._get_selected_meeting()
        if not m:
            return Panel("No meeting selected", title="Details", border_style="dim")

        content = Text()

        # Title - prominent and readable
        title = m.get("summary") or "No Title"
        content.append(f"{title}\n", style="bold reverse")
        content.append(self.SEPARATOR + "\n\n", style="dim")

        # Calendar source (with colored dot)
        cal_name = m.get("calendar_name", "Primary")
        cal_color = m.get("calendar_color", "#4285f4")
        content.append("Calendar:   ", style="dim")
        content.append("● ", style=cal_color)
        content.append(f"{cal_name}\n\n")

        # Time / Date Range
        is_all_day = self._is_all_day(m)
        is_multi = self._is_multi_day(m)

        if is_all_day and not is_multi:
            date_str = self._format_date_range(m.get("start", ""), m.get("end", ""))
            content.append("When:       ", style="dim")
            content.append(f"{date_str} (all day)\n\n")
        elif is_multi:
            date_range = self._format_date_range(m.get("start", ""), m.get("end", ""), force_range=True)
            duration = self._format_duration(m.get("duration_minutes", 0))
            content.append("When:       ", style="dim")
            content.append(f"{date_range} ({duration})\n\n")
        else:
            start_time = self._format_time(m.get("start", ""))
            end_time = self._format_time(m.get("end", ""))
            duration = self._format_duration(m.get("duration_minutes", 0))
            content.append("When:       ", style="dim")
            content.append(f"{start_time} - {end_time} ({duration})\n\n")

        # Location - ALWAYS show (even if empty)
        location = m.get("location", "")
        content.append("Location:   ", style="dim")
        content.append(f"{location or '(none)'}\n\n")

        # Google Meet link (if exists)
        meet_link = m.get("meet_link", "")
        if meet_link:
            content.append("Meet:       ", style="dim")
            content.append(f"{meet_link}\n\n", style="cyan underline")

        # Organizer
        organizer = m.get("organizer", "")
        if organizer:
            content.append("Organiser:  ", style="dim")
            org_name = organizer.split("@")[0].replace(".", " ").title() if "@" in organizer else organizer
            content.append(f"{org_name} ")
            content.append(f"({organizer})\n\n", style="dim")

        # Attendees - ONE LINE format: {name} (email)
        attendees = m.get("attendees", [])
        if attendees:
            content.append("Attendees:\n", style="dim")
            for att in attendees[:8]:
                # att is now a dict with name/email/status
                if isinstance(att, dict):
                    name = att.get("name", "Unknown")
                    email = att.get("email", "")
                else:
                    # Fallback for old format (just email string)
                    email = att
                    name = att.split("@")[0].replace(".", " ").title() if "@" in att else att

                content.append(f"  • {name} ", style="white")
                content.append(f"({email})\n", style="dim")
            if len(attendees) > 8:
                content.append(f"  ... +{len(attendees) - 8} more\n", style="dim")
            content.append("\n")

        # Description - FULL with scroll support
        desc = m.get("description", "")
        if desc:
            content.append(self.SEPARATOR + "\n", style="dim")
            desc_clean = strip_html(desc)
            desc_lines = [line for line in desc_clean.split("\n") if line.strip()]

            if len(desc_lines) > self.desc_max_lines:
                # Scrollable description
                visible = desc_lines[self.desc_scroll:self.desc_scroll + self.desc_max_lines]
                for line in visible:
                    content.append(f"{line[:55]}\n", style="dim")
                pct = int((self.desc_scroll / max(1, len(desc_lines) - self.desc_max_lines)) * 100)
                content.append(f"[{pct}% - </>: scroll]\n", style="dim italic")
            else:
                for line in desc_lines:
                    content.append(f"{line[:55]}\n", style="dim")

        return Panel(
            content,
            title="Details",
            border_style="green",
            padding=(1, 1),
        )

    def _render(self) -> None:
        """Render split pane view - simple side by side."""
        from rich.table import Table
        import shutil

        self.console.clear()

        # Get terminal dimensions
        term_size = shutil.get_terminal_size()
        self.page_size = max(8, term_size.lines - 8)  # Dynamic page size

        left = self._build_left_pane()
        right = self._build_right_pane()

        # Simple table layout - no Layout class
        table = Table.grid(expand=True)
        table.add_column(ratio=1)
        table.add_column(ratio=1)
        table.add_row(left, right)

        self.console.print(table)
        wknd = "hide" if self.show_weekends else "show"
        self.console.print(f"[dim]↑↓ Nav | PgUp/Dn: Week | </>: Scroll desc | w={wknd} wknd | t=Today | o=Open | q=Quit[/]")

    def _getch(self) -> str:
        """Get a single keypress."""
        import sys
        if sys.platform == 'win32':
            import msvcrt
            ch = msvcrt.getch()
            if ch in (b'\x00', b'\xe0'):
                ch2 = msvcrt.getch()
                if ch2 == b'H': return 'up'
                if ch2 == b'P': return 'down'
                if ch2 == b'I': return 'pgup'    # Page Up
                if ch2 == b'Q': return 'pgdn'    # Page Down
                if ch2 == b'G': return 'home'    # Home
                if ch2 == b'O': return 'end'     # End
            if ch == b'\r': return 'enter'
            if ch == b'\x1b': return 'esc'
            return ch.decode('utf-8', errors='ignore').lower()
        else:
            import tty, termios
            fd = sys.stdin.fileno()
            old = termios.tcgetattr(fd)
            try:
                tty.setraw(fd)
                ch = sys.stdin.read(1)
                if ch == '\x1b':
                    ch2 = sys.stdin.read(1)
                    if ch2 == '[':
                        ch3 = sys.stdin.read(1)
                        if ch3 == 'A': return 'up'
                        if ch3 == 'B': return 'down'
                        if ch3 == '5':  # Page Up: ESC [ 5 ~
                            sys.stdin.read(1)  # consume ~
                            return 'pgup'
                        if ch3 == '6':  # Page Down: ESC [ 6 ~
                            sys.stdin.read(1)  # consume ~
                            return 'pgdn'
                        if ch3 == 'H': return 'home'
                        if ch3 == 'F': return 'end'
                    return 'esc'
                if ch in ('\r', '\n'): return 'enter'
                return ch.lower()
            finally:
                termios.tcsetattr(fd, termios.TCSADRAIN, old)

    def _open_meeting(self) -> None:
        """Open meeting in browser."""
        m = self._get_selected_meeting()
        link = m.get("link", "")
        if link:
            webbrowser.open(link)

    def _update_rsvp(self, response: str) -> None:
        """Update RSVP for selected meeting (placeholder - needs API call)."""
        m = self._get_selected_meeting()
        if not m:
            return

        response_map = {"y": "accepted", "n": "declined", "m": "tentative"}
        status = response_map.get(response, "accepted")
        event_id = m.get("id", "")

        # For now, just show feedback - actual API call would go here
        # TODO: Implement Calendar API RSVP update
        self.rsvp_feedback = f"RSVP: {status.title()} (API update not yet implemented)"

    def run(self) -> None:
        """Run the calendar viewer."""
        from datetime import timedelta

        if not self.flat_list:
            self.console.print("[yellow]No meetings to display[/]")
            return

        self.rsvp_feedback = None

        try:
            while True:
                self._render()
                if self.rsvp_feedback:
                    self.console.print(f"[yellow]{self.rsvp_feedback}[/]")
                    self.rsvp_feedback = None

                key = self._getch()

                if key in ('q', 'esc'):
                    break
                elif key == 'up' or key == 'k':
                    # Navigate within week only, flip if at boundary
                    week_events = self._get_week_events()
                    old_selected = self.selected
                    if week_events:
                        if self.selected in week_events:
                            current_pos = week_events.index(self.selected)
                            if current_pos > 0:
                                # Move to previous event in week
                                self.selected = week_events[current_pos - 1]
                            else:
                                # At first event of week, flip to previous week
                                self.current_week_monday -= timedelta(days=7)
                                self._select_last_in_week()
                        else:
                            # Selection not in week (shouldn't happen), snap to last
                            self.selected = week_events[-1]
                    else:
                        # No events in week, flip back
                        self.current_week_monday -= timedelta(days=7)
                        self._select_last_in_week()
                    # Reset description scroll when selection changes
                    if self.selected != old_selected:
                        self.desc_scroll = 0
                elif key == 'down' or key == 'j':
                    # Navigate within week only, flip if at boundary
                    week_events = self._get_week_events()
                    old_selected = self.selected
                    if week_events:
                        if self.selected in week_events:
                            current_pos = week_events.index(self.selected)
                            if current_pos < len(week_events) - 1:
                                # Move to next event in week
                                self.selected = week_events[current_pos + 1]
                            else:
                                # At last event of week, flip to next week
                                self.current_week_monday += timedelta(days=7)
                                self._select_first_in_week()
                        else:
                            # Selection not in week (shouldn't happen), snap to first
                            self.selected = week_events[0]
                    else:
                        # No events in week, flip forward
                        self.current_week_monday += timedelta(days=7)
                        self._select_first_in_week()
                    # Reset description scroll when selection changes
                    if self.selected != old_selected:
                        self.desc_scroll = 0
                elif key == 'pgup':
                    # Previous week
                    self.current_week_monday -= timedelta(days=7)
                    self._select_first_in_week()
                    self.desc_scroll = 0
                elif key == 'pgdn':
                    # Next week
                    self.current_week_monday += timedelta(days=7)
                    self._select_first_in_week()
                    self.desc_scroll = 0
                elif key == 'w':
                    # Toggle weekends
                    self.show_weekends = not self.show_weekends
                elif key == 't':
                    # Jump to today's week
                    from datetime import date
                    today = date.today()
                    self.current_week_monday = today - timedelta(days=today.weekday())
                    self._select_first_in_week()
                    self.desc_scroll = 0
                elif key == 'home' or key == 'g':
                    self.selected = 0
                    self.desc_scroll = 0
                elif key == 'end' or key == 'G':
                    self.selected = len(self.flat_list) - 1
                    self.desc_scroll = 0
                elif key in ('enter', 'o'):
                    self._open_meeting()
                elif key in ('y', 'n', 'm'):
                    self._update_rsvp(key)
                elif key in ('<', ','):
                    # Scroll description up
                    self.desc_scroll = max(0, self.desc_scroll - 2)
                elif key in ('>', '.'):
                    # Scroll description down
                    m = self._get_selected_meeting()
                    if m:
                        desc = m.get("description", "")
                        if desc:
                            desc_lines = [l for l in strip_html(desc).split("\n") if l.strip()]
                            max_scroll = max(0, len(desc_lines) - self.desc_max_lines)
                            self.desc_scroll = min(max_scroll, self.desc_scroll + 2)
        except (KeyboardInterrupt, EOFError):
            pass
        finally:
            import os, sys
            if sys.platform == 'win32':
                os.system('cls')
            else:
                os.system('clear')
            print("Done.")


# Keep old class as alias for compatibility
class TerminalMeetingViewer(TerminalCalendarViewer):
    """Alias for backward compatibility."""
    pass


class TerminalDriveViewer(TerminalEmailViewer):
    """Interactive viewer for drive files."""

    def _normalize_emails(self, items: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Normalize file data."""
        results = []
        for f in items:
            # Parse modified time
            mod_time = f.get("modifiedTime", "")
            try:
                from datetime import datetime
                dt = datetime.fromisoformat(mod_time.replace("Z", "+00:00"))
                date_str = dt.strftime("%m/%d %H:%M")
            except:
                date_str = mod_time[:16] if mod_time else ""

            results.append({
                "date": date_str,
                "from": f.get("owner", "Unknown").split("@")[0][:15],
                "to": f.get("type", f.get("mimeType", "File"))[:20],
                "subject": f.get("name", "Untitled"),
                "body": f"Type: {f.get('type', f.get('mimeType', 'Unknown'))}\n"
                       f"Owner: {f.get('owner', 'Unknown')}\n"
                       f"Modified: {mod_time}\n"
                       f"Link: {f.get('link', 'N/A')}\n",
                "link": f.get("link", ""),
                "id": f.get("id", ""),
            })
        return results


def view_meetings(meetings: list[dict[str, Any]], title: str = "Calendar Meetings", tui: bool = False) -> None:
    """Launch the interactive meeting viewer."""
    if tui:
        # Use Textual (not implemented for meetings yet)
        viewer = TerminalMeetingViewer(meetings, title=title)
        viewer.run()
    else:
        viewer = TerminalMeetingViewer(meetings, title=title)
        viewer.run()


def view_files(files: list[dict[str, Any]], title: str = "Drive Files", tui: bool = False) -> None:
    """Launch the interactive file viewer."""
    if tui:
        viewer = TerminalDriveViewer(files, title=title)
        viewer.run()
    else:
        viewer = TerminalDriveViewer(files, title=title)
        viewer.run()


def view_results(results: list[dict[str, Any]], title: str = "Results", tui: bool = False) -> None:
    """Launch the interactive results viewer."""
    if tui:
        app = ResultsViewer(results, title=title)
        app.run()
    else:
        # Rich terminal viewer not implemented for generic results
        app = ResultsViewer(results, title=title)
        app.run()


def view_emails(emails: list[dict[str, Any]], title: str = "Email Results", tui: bool = False) -> None:
    """Launch the interactive email viewer.

    Args:
        emails: List of email dictionaries
        title: Window/table title
        tui: If True, use Textual TUI. If False (default), use Rich terminal viewer.
    """
    if tui:
        app = EmailViewer(emails, title=title)
        app.run()
    else:
        viewer = TerminalEmailViewer(emails, title=title)
        viewer.run()
