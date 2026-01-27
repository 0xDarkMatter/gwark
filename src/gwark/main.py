"""Main Typer application for gwark."""

import typer
from rich.console import Console

from gwark import __version__, __app_name__
from gwark.commands import email, calendar, drive, config, workflow, forms

# Initialize console for rich output
console = Console()

# Main app
app = typer.Typer(
    name=__app_name__,
    help="gwark - Google Workspace CLI for Gmail, Calendar, and Drive",
    no_args_is_help=True,
    rich_markup_mode="rich",
)

# Register subcommand groups
app.add_typer(email.app, name="email", help="Email operations (search, sent, summarize)")
app.add_typer(calendar.app, name="calendar", help="Calendar operations (meetings)")
app.add_typer(drive.app, name="drive", help="Drive operations (activity)")
app.add_typer(config.app, name="config", help="Configuration management")
app.add_typer(workflow.app, name="workflow", help="Workflow automation (triage)")
app.add_typer(forms.app, name="forms", help="Forms operations (list, create, responses)")


@app.callback(invoke_without_command=True)
def main(
    ctx: typer.Context,
    version: bool = typer.Option(
        False, "--version", "-v", help="Show version and exit"
    ),
) -> None:
    """gwark - Google Workspace CLI for Gmail, Calendar, and Drive."""
    if version:
        console.print(f"[bold]{__app_name__}[/bold] version [cyan]{__version__}[/cyan]")
        raise typer.Exit()

    if ctx.invoked_subcommand is None:
        console.print(ctx.get_help())


if __name__ == "__main__":
    app()
