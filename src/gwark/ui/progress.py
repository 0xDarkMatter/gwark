"""Animated progress indicators using Textual."""

import asyncio
from typing import Any, Callable, Coroutine, TypeVar

from rich.console import Console
from rich.progress import (
    Progress,
    SpinnerColumn,
    TextColumn,
    BarColumn,
    TaskProgressColumn,
    TimeElapsedColumn,
)
from rich.live import Live
from rich.panel import Panel
from rich.text import Text

console = Console()

T = TypeVar("T")


class ProgressSpinner:
    """Animated progress spinner for long-running operations."""

    def __init__(self, description: str = "Working..."):
        self.description = description
        self.progress = Progress(
            SpinnerColumn("dots"),
            TextColumn("[bold blue]{task.description}"),
            BarColumn(bar_width=30),
            TaskProgressColumn(),
            TimeElapsedColumn(),
            console=console,
            transient=True,
        )
        self.task_id = None

    def __enter__(self) -> "ProgressSpinner":
        self.progress.start()
        self.task_id = self.progress.add_task(self.description, total=None)
        return self

    def __exit__(self, *args: Any) -> None:
        self.progress.stop()

    def update(self, description: str | None = None, advance: float = 0, total: float | None = None) -> None:
        """Update progress state."""
        if self.task_id is not None:
            updates: dict[str, Any] = {}
            if description:
                updates["description"] = description
            if total is not None:
                updates["total"] = total
            if advance:
                updates["advance"] = advance
            self.progress.update(self.task_id, **updates)

    def set_total(self, total: float) -> None:
        """Set the total for determinate progress."""
        if self.task_id is not None:
            self.progress.update(self.task_id, total=total)

    def advance(self, amount: float = 1) -> None:
        """Advance progress by amount."""
        if self.task_id is not None:
            self.progress.advance(self.task_id, amount)


class MultiStepProgress:
    """Progress tracker for multi-step operations."""

    def __init__(self, steps: list[str]):
        self.steps = steps
        self.current_step = 0
        self.progress = Progress(
            SpinnerColumn("dots"),
            TextColumn("[bold]{task.description}"),
            console=console,
            transient=True,
        )

    def __enter__(self) -> "MultiStepProgress":
        self.progress.start()
        self._update_display()
        return self

    def __exit__(self, *args: Any) -> None:
        self.progress.stop()

    def _update_display(self) -> None:
        """Update the progress display."""
        # Clear existing tasks
        for task_id in list(self.progress.task_ids):
            self.progress.remove_task(task_id)

        # Show all steps with current step highlighted
        for i, step in enumerate(self.steps):
            if i < self.current_step:
                # Completed
                self.progress.add_task(f"[green]✓[/green] {step}", total=1, completed=1)
            elif i == self.current_step:
                # Current
                self.progress.add_task(f"[bold cyan]→ {step}[/bold cyan]", total=None)
            else:
                # Pending
                self.progress.add_task(f"[dim]○ {step}[/dim]", total=1, completed=0)

    def next_step(self) -> None:
        """Move to the next step."""
        if self.current_step < len(self.steps):
            self.current_step += 1
            self._update_display()

    def complete(self) -> None:
        """Mark all steps as complete."""
        self.current_step = len(self.steps)
        self._update_display()


def run_with_progress(
    coro: Coroutine[Any, Any, T],
    description: str = "Working...",
) -> T:
    """Run an async coroutine with a progress spinner.

    Args:
        coro: The coroutine to run
        description: Description to show in spinner

    Returns:
        The result of the coroutine
    """
    async def _run() -> T:
        with ProgressSpinner(description):
            return await coro

    return asyncio.run(_run())


def run_steps_with_progress(
    steps: list[tuple[str, Callable[[], Any]]],
) -> list[Any]:
    """Run a sequence of steps with progress tracking.

    Args:
        steps: List of (description, callable) tuples

    Returns:
        List of results from each step
    """
    results = []
    step_names = [s[0] for s in steps]

    with MultiStepProgress(step_names) as progress:
        for description, func in steps:
            result = func()
            results.append(result)
            progress.next_step()

    return results


class FetchProgress:
    """Progress display for fetching multiple items."""

    def __init__(self, total: int, description: str = "Fetching"):
        self.total = total
        self.description = description
        self.completed = 0
        self.progress = Progress(
            SpinnerColumn("dots"),
            TextColumn("[bold blue]{task.description}"),
            BarColumn(bar_width=40, complete_style="green", finished_style="green"),
            TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
            TextColumn("•"),
            TextColumn("[cyan]{task.completed}/{task.total}[/cyan]"),
            TimeElapsedColumn(),
            console=console,
            transient=True,
        )
        self.task_id = None

    def __enter__(self) -> "FetchProgress":
        self.progress.start()
        self.task_id = self.progress.add_task(self.description, total=self.total)
        return self

    def __exit__(self, *args: Any) -> None:
        self.progress.stop()

    def advance(self, amount: int = 1) -> None:
        """Advance progress."""
        if self.task_id is not None:
            self.progress.advance(self.task_id, amount)
            self.completed += amount

    def update_description(self, description: str) -> None:
        """Update the description."""
        if self.task_id is not None:
            self.progress.update(self.task_id, description=description)
