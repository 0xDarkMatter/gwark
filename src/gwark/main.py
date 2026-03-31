"""Main Typer application for gwark."""

import typer
from rich.console import Console

from gwark import __version__, __app_name__
from gwark.commands import email, calendar, drive, config, workflow, forms, docs, sheets, slides

# Initialize console for rich output
console = Console()

# Main app
app = typer.Typer(
    name=__app_name__,
    help="gwark - Google Workspace CLI",
    no_args_is_help=True,
    rich_markup_mode="rich",
)

# Register subcommand groups
app.add_typer(email.app, name="email", help="Email search, unique senders, sent analysis, AI summarize")
app.add_typer(calendar.app, name="calendar", help="Calendar meetings and events")
app.add_typer(drive.app, name="drive", help="Drive file management (ls, search, move, copy, share)")
app.add_typer(config.app, name="config", help="Configuration and OAuth management")
app.add_typer(workflow.app, name="workflow", help="Workflow automation (triage)")
app.add_typer(forms.app, name="forms", help="Forms management (list, create, responses)")
app.add_typer(docs.app, name="docs", help="Docs create, edit, sections, themes, comments, review")
app.add_typer(sheets.app, name="sheets", help="Sheets read, write, pivot tables, export")
app.add_typer(slides.app, name="slides", help="Slides create, edit, export, templates")


@app.callback(invoke_without_command=True)
def main(
    ctx: typer.Context,
    version: bool = typer.Option(
        False, "--version", "-v", help="Show version and exit"
    ),
) -> None:
    """gwark - Google Workspace CLI."""
    if version:
        console.print(f"[bold]{__app_name__}[/bold] version [cyan]{__version__}[/cyan]")
        raise typer.Exit()

    if ctx.invoked_subcommand is None:
        console.print(ctx.get_help())


if __name__ == "__main__":
    app()
