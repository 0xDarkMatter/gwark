"""Workflow commands for gwark CLI."""

from datetime import datetime
from pathlib import Path
from typing import Optional

import typer
from rich.console import Console
from rich.table import Table

from gwark.core.output import print_header, print_info, print_success, print_error
from gwark.workflows.base import get_workflow, list_workflows

console = Console()
app = typer.Typer(no_args_is_help=True)


@app.command()
def run(
    name: str = typer.Argument(..., help="Workflow name (e.g., 'triage')"),
    account: str = typer.Option(..., "--account", "-a", help="Email account to analyze"),
    since: str = typer.Option(..., "--since", "-s", help="Start date (YYYY-MM-DD)"),
    profile: str = typer.Option("work", "--profile", "-p", help="Filter profile to use"),
    output: Optional[Path] = typer.Option(None, "--output", "-o", help="Output file path"),
    max_results: int = typer.Option(500, "--max-results", "-m", help="Maximum emails to fetch"),
    dry_run: bool = typer.Option(False, "--dry-run", help="Preview without AI classification"),
    skip_ai: bool = typer.Option(False, "--skip-ai", help="Skip AI classification step"),
    export_data: Optional[Path] = typer.Option(None, "--export-data", "-e", help="Export triage data to JSON for Claude Code classification"),
) -> None:
    """Run a saved workflow.

    Example:
        gwark workflow run triage --account user@company.com --since 2024-12-01
    """
    # Parse date
    try:
        since_date = datetime.strptime(since, "%Y-%m-%d")
    except ValueError:
        print_error(f"Invalid date format: {since}. Use YYYY-MM-DD.")
        raise typer.Exit(1)

    # Get workflow
    workflow_class = get_workflow(name)
    if not workflow_class:
        print_error(f"Unknown workflow: {name}")
        print_info("Available workflows:")
        for wf in list_workflows():
            print_info(f"  - {wf['name']}: {wf['description']}")
        raise typer.Exit(1)

    print_header(f"gwark workflow: {name}")
    print_info(f"Account: {account}")
    print_info(f"Since: {since_date.strftime('%Y-%m-%d')}")
    print_info(f"Profile: {profile}")

    if dry_run:
        print_info("[DRY RUN] Will not call AI APIs")

    # Run workflow
    try:
        workflow = workflow_class()
        result = workflow.run(
            account=account,
            since=since_date,
            profile=profile,
            output=output,
            max_results=max_results,
            dry_run=dry_run,
            skip_ai=skip_ai or bool(export_data),  # Skip AI if exporting for Claude Code
            export_data=export_data,
        )

        if result.success:
            print_success(f"Workflow completed in {result.duration_seconds:.1f}s")
            if result.output_path:
                print_success(f"Report saved to: {result.output_path}")

            # Show stats
            if result.stats:
                console.print("\n[bold]Summary:[/bold]")
                for key, value in result.stats.items():
                    console.print(f"  {key}: {value}")
        else:
            print_error(f"Workflow failed: {result.error}")
            raise typer.Exit(1)

    except Exception as e:
        print_error(f"Workflow error: {e}")
        raise typer.Exit(1)


@app.command("list")
def list_cmd() -> None:
    """List available workflows."""
    print_header("Available Workflows")

    workflows = list_workflows()
    if not workflows:
        print_info("No workflows registered.")
        return

    table = Table(show_header=True)
    table.add_column("Name", style="cyan")
    table.add_column("Description")

    for wf in workflows:
        table.add_row(wf["name"], wf["description"])

    console.print(table)


@app.command()
def show(
    name: str = typer.Argument(..., help="Workflow name"),
) -> None:
    """Show workflow details."""
    workflow_class = get_workflow(name)
    if not workflow_class:
        print_error(f"Unknown workflow: {name}")
        raise typer.Exit(1)

    print_header(f"Workflow: {name}")
    console.print(f"[bold]Description:[/bold] {workflow_class.description}")
    console.print(f"[bold]Stages:[/bold] {', '.join(s.value for s in workflow_class.stages)}")
