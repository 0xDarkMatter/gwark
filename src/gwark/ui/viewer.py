"""Interactive results viewer using Textual."""

from typing import Any

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Container, Vertical
from textual.widgets import DataTable, Footer, Header, Static
from textual.screen import ModalScreen
from rich.text import Text


class EmailDetailScreen(ModalScreen):
    """Modal screen showing email details."""

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
        text.append(f"From: ", style="bold cyan")
        text.append(f"{self.email.get('from', 'Unknown')}\n")
        text.append(f"To: ", style="bold cyan")
        text.append(f"{self.email.get('to', 'Unknown')}\n")
        text.append(f"Subject: ", style="bold cyan")
        text.append(f"{self.email.get('subject', 'No subject')}\n")
        text.append(f"Date: ", style="bold cyan")
        text.append(f"{self.email.get('date', 'Unknown')}\n")
        text.append("\n")

        if self.email.get("snippet"):
            text.append("Preview:\n", style="bold yellow")
            text.append(self.email["snippet"])

        if self.email.get("body"):
            text.append("\n\nBody:\n", style="bold yellow")
            text.append(self.email["body"][:2000])

        return text


class ResultsViewer(App):
    """Interactive viewer for search results."""

    CSS = """
    #results-table {
        height: 100%;
    }

    #detail-container {
        align: center middle;
        width: 80%;
        height: 80%;
        background: $surface;
        border: thick $primary;
        padding: 1 2;
    }

    #email-detail {
        height: 100%;
        overflow-y: auto;
    }

    #status-bar {
        dock: bottom;
        height: 1;
        background: $primary;
        color: $text;
        padding: 0 1;
    }
    """

    BINDINGS = [
        Binding("q", "quit", "Quit"),
        Binding("escape", "quit", "Quit"),
        Binding("enter", "view_detail", "View"),
        Binding("j", "cursor_down", "Down", show=False),
        Binding("k", "cursor_up", "Up", show=False),
        Binding("g", "scroll_top", "Top", show=False),
        Binding("G", "scroll_bottom", "Bottom", show=False),
        Binding("/", "search", "Search"),
        Binding("o", "open_link", "Open in Gmail"),
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
        yield Static(f" {len(self.results)} results | Enter: view | o: open | q: quit", id="status-bar")
        yield Footer()

    def on_mount(self) -> None:
        """Set up the data table on mount."""
        table = self.query_one(DataTable)
        table.cursor_type = "row"
        table.zebra_stripes = True

        # Add columns
        for col in self.columns:
            table.add_column(col, key=col.lower())

        # Add link column
        table.add_column("", key="link", width=6)

        # Add rows
        for i, result in enumerate(self.results):
            row_data = []
            for col in self.columns:
                value = result.get(col.lower(), "")
                # Truncate long values
                if isinstance(value, str) and len(value) > 50:
                    value = value[:47] + "..."
                row_data.append(value)

            # Add link indicator
            if result.get("link") or result.get("id"):
                row_data.append("[link]")
            else:
                row_data.append("")

            table.add_row(*row_data, key=str(i))

        # Focus table
        table.focus()

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
            if link:
                webbrowser.open(link)
                self.notify(f"Opening in browser...")
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


def view_results(results: list[dict[str, Any]], title: str = "Results") -> None:
    """Launch the interactive results viewer."""
    app = ResultsViewer(results, title=title)
    app.run()


def view_emails(emails: list[dict[str, Any]], title: str = "Email Results") -> None:
    """Launch the interactive email viewer."""
    app = EmailViewer(emails, title=title)
    app.run()
