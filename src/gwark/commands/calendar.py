"""Calendar commands for gwark CLI."""

import asyncio
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

import typer
from rich.console import Console

# Add project root for imports
project_root = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(project_root))

from gwark.core.config import load_config, get_profile
from gwark.core.output import (
    OutputFormatter,
    print_success,
    print_info,
    print_error,
    print_header,
)

console = Console()
app = typer.Typer(no_args_is_help=True)


@app.command()
def meetings(
    days: int = typer.Option(30, "--days", "-n", help="Days to look back"),
    calendar_id: str = typer.Option("primary", "--calendar-id", "-c", help="Calendar ID"),
    work_only: bool = typer.Option(False, "--work-only", "-w", help="Filter to work meetings only"),
    include_declined: bool = typer.Option(False, "--include-declined", help="Include declined meetings"),
    max_results: int = typer.Option(500, "--max-results", "-m", help="Maximum results"),
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

    print_header("gwark calendar meetings")
    print_info(f"Days back: {days}, Calendar: {calendar_id}, Work only: {work_only}")

    try:
        from gmail_mcp.auth import get_calendar_service

        service = get_calendar_service()

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

        # Fetch events
        events_result = service.events().list(
            calendarId=calendar_id,
            timeMin=time_min,
            timeMax=time_max,
            maxResults=max_results,
            singleEvents=True,
            orderBy="startTime",
        ).execute()

        events = events_result.get("items", [])
        print_info(f"Found {len(events)} events")

        # Process events
        meetings_data = []
        for event in events:
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

            meeting = {
                "id": event.get("id"),
                "summary": event.get("summary", "No Title"),
                "start": start.get("dateTime", start.get("date", "")),
                "end": end.get("dateTime", end.get("date", "")),
                "location": event.get("location", ""),
                "description": event.get("description", "")[:200] if event.get("description") else "",
                "organizer": event.get("organizer", {}).get("email", ""),
                "attendees": [a.get("email") for a in event.get("attendees", [])],
                "status": event.get("status"),
                "link": event.get("htmlLink", ""),
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

        prefix = f"calendar_meetings_{calendar_id}"
        output_path = formatter.save(content, prefix, ext, output)
        print_success(f"Saved to: {output_path}")

        # Launch interactive viewer
        if interactive and meetings_data:
            from gwark.ui.viewer import view_meetings
            view_meetings(meetings_data, title=f"Calendar: {calendar_id}")

    except ImportError as e:
        print_error(f"Missing dependency: {e}")
        print_info("Run: pip install -e . and ensure OAuth is configured")
        raise typer.Exit(1)
    except Exception as e:
        print_error(f"Failed: {e}")
        raise typer.Exit(1)


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
