"""Calendar commands for gwark CLI."""

import sys
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional, Callable, TypeVar, List, Dict, Any

import typer
from rich.console import Console

# Add project root for imports
project_root = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(project_root))

from gwark.core.config import load_config, get_profile
from gwark.core.constants import EXIT_ERROR
from gwark.core.output import (
    OutputFormatter,
    print_success,
    print_info,
    print_error,
    print_warning,
    print_header,
)
from gwark.core.async_utils import AsyncFetcher, run_async

console = Console()
app = typer.Typer(no_args_is_help=True)

T = TypeVar("T")


def _retry_api_call(
    func: Callable[[], T],
    max_retries: int = 3,
    base_delay: float = 1.0,
    operation: str = "API call",
) -> T:
    """Retry API call with exponential backoff for transient errors."""
    from googleapiclient.errors import HttpError

    last_error = None
    for attempt in range(max_retries):
        try:
            return func()
        except HttpError as e:
            last_error = e
            status = e.resp.status if hasattr(e, 'resp') else 0

            # Retry on 5xx (server errors) and 429 (rate limit)
            if status in (429, 500, 502, 503, 504):
                delay = base_delay * (2 ** attempt)
                if attempt < max_retries - 1:
                    print_warning(f"{operation} failed ({status}), retrying in {delay:.1f}s...")
                    time.sleep(delay)
                    continue
            # Non-retryable error
            raise
        except Exception as e:
            # Non-HTTP errors, don't retry
            raise

    # All retries exhausted
    raise last_error


def _fetch_calendar_events_paginated(
    service,
    cal_id: str,
    time_min: str,
    time_max: str,
    max_results: int = 500,
) -> List[Dict[str, Any]]:
    """Fetch all events from a calendar with pagination.

    Args:
        service: Google Calendar service
        cal_id: Calendar ID
        time_min: Start time (ISO format)
        time_max: End time (ISO format)
        max_results: Maximum total events to fetch

    Returns:
        List of event dictionaries
    """
    all_events = []
    page_token = None

    while len(all_events) < max_results:
        # Fetch page (max 250 per request is optimal)
        result = _retry_api_call(
            lambda: service.events().list(
                calendarId=cal_id,
                timeMin=time_min,
                timeMax=time_max,
                maxResults=min(250, max_results - len(all_events)),
                singleEvents=True,
                orderBy="startTime",
                pageToken=page_token,
            ).execute(),
            operation=f"Fetch events from {cal_id}"
        )

        events = result.get("items", [])
        # Tag each event with source calendar
        for event in events:
            event["_calendar_id"] = cal_id
        all_events.extend(events)

        page_token = result.get("nextPageToken")
        if not page_token:
            break

    return all_events[:max_results]


async def _fetch_all_calendars_async(
    service,
    calendar_ids: List[str],
    time_min: str,
    time_max: str,
    max_results: int,
    calendar_meta: Dict[str, Dict],
) -> List[Dict[str, Any]]:
    """Fetch events from all calendars in parallel.

    Args:
        service: Google Calendar service
        calendar_ids: List of calendar IDs to fetch
        time_min: Start time (ISO format)
        time_max: End time (ISO format)
        max_results: Max events per calendar
        calendar_meta: Calendar metadata for naming

    Returns:
        Combined list of events from all calendars
    """
    fetcher = AsyncFetcher(max_concurrent=10, rate_per_second=50)

    def fetch_calendar(cal_id: str) -> List[Dict[str, Any]]:
        """Fetch events from a single calendar (sync)."""
        return _fetch_calendar_events_paginated(
            service, cal_id, time_min, time_max, max_results
        )

    # Fetch all calendars in parallel
    results = await fetcher.fetch_all(calendar_ids, fetch_calendar)

    # Flatten and filter errors
    all_events = []
    for i, result in enumerate(results):
        cal_id = calendar_ids[i]
        cal_name = calendar_meta.get(cal_id, {}).get('name', cal_id)

        if isinstance(result, Exception):
            print_error(f"  Failed to fetch {cal_name}: {result}")
        else:
            print_info(f"  {cal_name}: {len(result)} events")
            all_events.extend(result)

    return all_events


def _extract_meet_link(conference_data: dict | None) -> str:
    """Extract Google Meet/video link from conferenceData."""
    if not conference_data:
        return ""
    for entry in conference_data.get("entryPoints", []):
        if entry.get("entryPointType") == "video":
            return entry.get("uri", "")
    return ""


@app.command("list")
def list_calendars() -> None:
    """List all available calendars with their IDs."""
    from rich.table import Table

    print_header("gwark calendar list")

    try:
        from gmail_mcp.auth import get_calendar_service
        service = get_calendar_service()

        print_info("Fetching calendars...")
        calendar_list = _retry_api_call(
            lambda: service.calendarList().list(
                fields="items(id,summary,backgroundColor,primary,accessRole)"
            ).execute(),
            operation="Fetch calendar list"
        )

        calendars = calendar_list.get("items", [])
        print_success(f"Found {len(calendars)} calendars\n")

        table = Table(title="Available Calendars", show_lines=False, expand=True)
        table.add_column("", width=2)  # Color dot
        table.add_column("Name", style="bold", no_wrap=True)
        table.add_column("ID (use with -C flag)", overflow="fold")

        for cal in calendars:
            color = cal.get("backgroundColor", "#4285f4")
            name = cal.get("summary", "Unnamed")
            cal_id = cal.get("id", "")
            primary = " (primary)" if cal.get("primary") else ""

            table.add_row(
                f"[{color}]●[/]",
                f"{name}{primary}",
                cal_id,
            )

        console.print(table)
        console.print("\n[dim]Use: gwark calendar meetings -C \"primary,<calendar-id>\" -i[/]")
        console.print("[dim]Or add to .gwark/config.yaml under calendar.calendars[/]")

    except Exception as e:
        print_error(f"Failed: {e}")
        raise typer.Exit(EXIT_ERROR)


@app.command()
def meetings(
    days: int = typer.Option(30, "--days", "-n", help="Days to look back"),
    calendar_id: str = typer.Option("primary", "--calendar-id", "-c", help="Calendar ID (deprecated, use --calendars)"),
    calendars: Optional[str] = typer.Option(None, "--calendars", "-C", help="Comma-separated calendar IDs (default: from config or 'primary')"),
    work_only: bool = typer.Option(False, "--work-only", "-w", help="Filter to work meetings only"),
    include_declined: bool = typer.Option(False, "--include-declined", help="Include declined meetings"),
    max_results: int = typer.Option(500, "--max-results", "-m", help="Maximum results per calendar"),
    output_format: str = typer.Option("markdown", "--format", "-f", help="Output format: json, csv, markdown"),
    interactive: bool = typer.Option(False, "--interactive", "-i", help="Launch interactive viewer"),
    profile: Optional[str] = typer.Option(None, "--profile", "-p", help="Use named profile"),
    output: Optional[Path] = typer.Option(None, "--output", "-o", help="Output file path"),
) -> None:
    """Extract calendar meetings for analysis."""
    # Load config and profile
    config = load_config()
    exclude_keywords = []

    if profile:
        prof = get_profile(profile)
        work_only = prof.filters.get("calendar", {}).get("work_only", work_only)
        exclude_keywords = prof.filters.get("calendar", {}).get("exclude_keywords", [])

    # Determine which calendars to fetch
    # Priority: --calendars flag > config > --calendar-id (deprecated) > "primary"
    if calendars:
        calendar_ids = [c.strip() for c in calendars.split(",")]
    elif hasattr(config, 'calendar') and config.calendar.calendars:
        calendar_ids = config.calendar.calendars
    elif calendar_id != "primary":
        calendar_ids = [calendar_id]  # Use deprecated flag if explicitly set
    else:
        calendar_ids = ["primary"]

    print_header("gwark calendar meetings")
    cal_display = ", ".join(calendar_ids) if len(calendar_ids) <= 3 else f"{len(calendar_ids)} calendars"
    print_info(f"Days back: {days}, Calendars: {cal_display}, Work only: {work_only}")

    try:
        from gmail_mcp.auth import get_calendar_service

        service = get_calendar_service()

        # Fetch calendar metadata (names, colors) for all accessible calendars
        print_info("Fetching calendar metadata...")
        calendar_list = _retry_api_call(
            lambda: service.calendarList().list(
                fields="items(id,summary,backgroundColor,foregroundColor,primary)"
            ).execute(),
            operation="Fetch calendar list"
        )

        # Build color map: {calendar_id: {"name": "Personal", "bg": "#9fe1e7", ...}}
        calendar_meta = {}
        for cal in calendar_list.get("items", []):
            calendar_meta[cal["id"]] = {
                "name": cal.get("summary", cal["id"]),
                "bg": cal.get("backgroundColor", "#4285f4"),
                "fg": cal.get("foregroundColor", "#ffffff"),
                "primary": cal.get("primary", False),
            }

        # Calculate time range
        # For interactive mode, load extra buffer (month before and after)
        now = datetime.utcnow()
        if interactive:
            # Load 30 days before and 30 days after for smooth navigation
            time_min = (now - timedelta(days=max(days, 30))).isoformat() + "Z"
            time_max = (now + timedelta(days=30)).isoformat() + "Z"
            print_info(f"Interactive mode: loading extended range for smooth navigation")
        else:
            time_min = (now - timedelta(days=days)).isoformat() + "Z"
            time_max = now.isoformat() + "Z"

        print_info(f"Fetching events from {time_min[:10]} to {time_max[:10]}...")

        # Fetch events from all calendars in parallel with pagination
        if len(calendar_ids) == 1:
            # Single calendar - no need for async overhead
            all_events = _fetch_calendar_events_paginated(
                service, calendar_ids[0], time_min, time_max, max_results
            )
            cal_name = calendar_meta.get(calendar_ids[0], {}).get('name', calendar_ids[0])
            print_info(f"  {cal_name}: {len(all_events)} events")
        else:
            # Multiple calendars - fetch in parallel
            print_info(f"Fetching from {len(calendar_ids)} calendars in parallel...")
            all_events = run_async(_fetch_all_calendars_async(
                service, calendar_ids, time_min, time_max, max_results, calendar_meta
            ))

        print_info(f"Found {len(all_events)} total events")

        # Process events
        meetings_data = []
        for event in all_events:
            # Skip declined if not included
            if not include_declined:
                attendees = event.get("attendees", [])
                user_response = next(
                    (a.get("responseStatus") for a in attendees if a.get("self")),
                    "accepted"
                )
                if user_response == "declined":
                    continue

            # Extract meeting details
            start = event.get("start", {})
            end = event.get("end", {})
            cal_id = event.get("_calendar_id", "primary")
            cal_info = calendar_meta.get(cal_id, {"name": "Primary", "bg": "#4285f4", "fg": "#ffffff"})

            meeting = {
                "id": event.get("id"),
                "summary": event.get("summary", "No Title"),
                "start": start.get("dateTime", start.get("date", "")),
                "end": end.get("dateTime", end.get("date", "")),
                "location": event.get("location", ""),
                # Full description (not truncated)
                "description": event.get("description", ""),
                "organizer": event.get("organizer", {}).get("email", ""),
                # Attendees with displayName
                "attendees": [
                    {
                        "email": a.get("email", ""),
                        "name": a.get("displayName") or a.get("email", "").split("@")[0].replace(".", " ").title(),
                        "status": a.get("responseStatus", "needsAction"),
                    }
                    for a in event.get("attendees", [])
                ],
                "status": event.get("status"),
                "link": event.get("htmlLink", ""),
                # Calendar source
                "calendar_id": cal_id,
                "calendar_name": cal_info.get("name", "Primary"),
                "calendar_color": cal_info.get("bg", "#4285f4"),
                # Google Meet link
                "meet_link": _extract_meet_link(event.get("conferenceData")),
            }

            # Calculate duration
            try:
                start_dt = datetime.fromisoformat(meeting["start"].replace("Z", "+00:00"))
                end_dt = datetime.fromisoformat(meeting["end"].replace("Z", "+00:00"))
                meeting["duration_minutes"] = int((end_dt - start_dt).total_seconds() / 60)
            except Exception:
                meeting["duration_minutes"] = 0

            # Work-only filtering
            if work_only:
                summary_lower = meeting["summary"].lower()
                if any(kw.lower() in summary_lower for kw in exclude_keywords):
                    continue

            meetings_data.append(meeting)

        # Sort by start time (important when merging from multiple calendars)
        meetings_data.sort(key=lambda m: m.get("start", ""))

        print_success(f"Processed {len(meetings_data)} meetings")

        # Format output
        formatter = OutputFormatter(output_dir=config.defaults.output_directory)

        if output_format == "json":
            content = formatter.to_json(meetings_data)
            ext = "json"
        elif output_format == "csv":
            content = formatter.to_csv(meetings_data)
            ext = "csv"
        else:
            content = _format_meetings_markdown(meetings_data)
            ext = "md"

        # Use calendar names in filename if multiple
        if len(calendar_ids) > 1:
            prefix = f"calendar_meetings_multi"
        else:
            cal_name = calendar_meta.get(calendar_ids[0], {}).get("name", calendar_ids[0])
            prefix = f"calendar_meetings_{cal_name.replace(' ', '_')}"
        output_path = formatter.save(content, prefix, ext, output)
        print_success(f"Saved to: {output_path}")

        # Launch interactive viewer
        if interactive and meetings_data:
            from gwark.ui.viewer import view_meetings
            # Pass calendar info to viewer
            title = "Calendar" if len(calendar_ids) == 1 else f"Calendars ({len(calendar_ids)})"
            view_meetings(meetings_data, title=title)

    except ImportError as e:
        print_error(f"Missing dependency: {e}")
        print_info("Run: pip install -e . and ensure OAuth is configured")
        raise typer.Exit(EXIT_ERROR)
    except Exception as e:
        print_error(f"Failed: {e}")
        raise typer.Exit(EXIT_ERROR)


def _format_meetings_markdown(meetings: list) -> str:
    """Format meetings as markdown."""
    lines = []
    lines.append("# Calendar Meetings\n")
    lines.append(f"*Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}*\n")
    lines.append(f"*Total: {len(meetings)} meetings*\n")

    # Calculate total time
    total_minutes = sum(m.get("duration_minutes", 0) for m in meetings)
    total_hours = total_minutes / 60
    lines.append(f"*Total time: {total_hours:.1f} hours*\n")

    lines.append("| Date | Time | Duration | Meeting | Organizer |")
    lines.append("|------|------|----------|---------|-----------|")

    for meeting in meetings:
        try:
            start_dt = datetime.fromisoformat(meeting["start"].replace("Z", "+00:00"))
            date_str = start_dt.strftime("%d/%m/%Y")
            time_str = start_dt.strftime("%H:%M")
        except Exception:
            date_str = meeting["start"][:10]
            time_str = ""

        duration = meeting.get("duration_minutes", 0)
        duration_str = f"{duration}min" if duration < 60 else f"{duration // 60}h{duration % 60}m"
        summary = meeting.get("summary", "No Title").replace("|", "\\|")[:40]
        organizer = meeting.get("organizer", "").split("@")[0]

        lines.append(f"| {date_str} | {time_str} | {duration_str} | {summary} | {organizer} |")

    return "\n".join(lines)
