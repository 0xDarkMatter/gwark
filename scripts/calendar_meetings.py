#!/usr/bin/env python
"""Extract meetings from Google Calendar for a specified time period."""

import os
import sys
import json
import argparse
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Dict, Optional

# Shared OAuth authentication
from gmail_mcp.auth import get_calendar_service


def extract_meetings(
    days_back: int = 30,
    calendar_id: str = 'primary',
    max_results: int = 500,
    output_format: str = 'json',
    include_declined: bool = False,
    work_only: bool = False
) -> None:
    """Extract meetings from Google Calendar.

    Args:
        days_back: Number of days to look back (default: 30)
        calendar_id: Calendar ID to search (default: 'primary')
        max_results: Maximum number of events to retrieve
        output_format: Output format (json, csv, markdown)
        include_declined: Include declined meetings
        work_only: Filter to work-related meetings only
    """
    print("=" * 80)
    print("  Google Calendar Meetings Extractor")
    print("=" * 80)
    print()

    # Calculate date range
    end_time = datetime.now(datetime.UTC if hasattr(datetime, 'UTC') else None).replace(tzinfo=None)
    start_time = end_time - timedelta(days=days_back)

    print(f"[INFO] Calendar: {calendar_id}")
    print(f"[INFO] Date Range: {start_time.strftime('%Y-%m-%d')} to {end_time.strftime('%Y-%m-%d')}")
    print(f"[INFO] Days Back: {days_back}")
    print(f"[INFO] Max Results: {max_results}")
    print()

    # Get calendar service
    print("[INFO] Connecting to Google Calendar API...")
    service = get_calendar_service()
    print("[OK] Connected")

    # Fetch events
    print("[INFO] Fetching calendar events...")
    events_result = service.events().list(
        calendarId=calendar_id,
        timeMin=start_time.isoformat() + 'Z',
        timeMax=end_time.isoformat() + 'Z',
        maxResults=max_results,
        singleEvents=True,
        orderBy='startTime'
    ).execute()

    events = events_result.get('items', [])
    print(f"[OK] Found {len(events)} total events")

    # Filter for meetings (events with attendees)
    meetings = []
    for event in events:
        # Skip if no attendees (not a meeting)
        if 'attendees' not in event:
            continue

        # Extract meeting info
        meeting = {
            'id': event.get('id'),
            'summary': event.get('summary', 'No Title'),
            'description': event.get('description', ''),
            'location': event.get('location', ''),
            'start': event.get('start', {}).get('dateTime') or event.get('start', {}).get('date'),
            'end': event.get('end', {}).get('dateTime') or event.get('end', {}).get('date'),
            'organizer': event.get('organizer', {}).get('email', 'Unknown'),
            'attendees': [],
            'status': event.get('status', 'confirmed'),
            'htmlLink': event.get('htmlLink', ''),
            'created': event.get('created'),
            'updated': event.get('updated'),
        }

        # Extract attendees
        for attendee in event.get('attendees', []):
            attendee_info = {
                'email': attendee.get('email'),
                'name': attendee.get('displayName', attendee.get('email')),
                'responseStatus': attendee.get('responseStatus', 'needsAction'),
                'organizer': attendee.get('organizer', False),
                'self': attendee.get('self', False)
            }
            meeting['attendees'].append(attendee_info)

            # Track our response status
            if attendee.get('self', False):
                meeting['myResponseStatus'] = attendee.get('responseStatus')

        # Filter by response status if needed
        if not include_declined:
            if meeting.get('myResponseStatus') == 'declined':
                continue

        # Filter for work-only meetings if requested
        if work_only:
            # Keywords to exclude (personal events and internal meetings)
            personal_keywords = [
                'amelia', 'jasper', 'bin night', 'school',
                'mack & fi', 'auburn hotel', 'tennis', 'vjbl',
                'tryouts', 'magic rep', 'family lunch',
                'roam', 'kamila', 'team lunch'
            ]

            # Check if title contains personal keywords
            summary_lower = meeting['summary'].lower()
            if any(keyword in summary_lower for keyword in personal_keywords):
                continue

            # Check if it's a work meeting by looking at attendee domains
            # Work meetings typically have evolution7.com.au or client domains
            has_work_attendee = False
            for attendee in meeting['attendees']:
                email = attendee.get('email', '').lower()
                # Check for work domains or non-gmail/personal domains
                if ('evolution7.com.au' in email or
                    'grandprix.com.au' in email or
                    'agpc.com.au' in email or
                    'saxton' in email.lower() or
                    ('.' in email and
                     not email.endswith('@gmail.com') and
                     not email.endswith('@icloud.com') and
                     '@' in email)):
                    has_work_attendee = True
                    break

            # Skip if no work attendees found (likely personal event)
            if not has_work_attendee:
                continue

        meetings.append(meeting)

    print(f"[OK] Found {len(meetings)} meetings")
    if not include_declined:
        print("[INFO] Excluded declined meetings")
    if work_only:
        print("[INFO] Filtered to work-related meetings only")

    # Export results
    project_root = Path(__file__).parent.parent
    reports_dir = project_root / 'reports'
    reports_dir.mkdir(exist_ok=True)

    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')

    if output_format == 'json':
        output_file = reports_dir / f'calendar_meetings_{timestamp}.json'
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump({
                'calendar_id': calendar_id,
                'date_range': {
                    'start': start_time.isoformat(),
                    'end': end_time.isoformat(),
                    'days_back': days_back
                },
                'total_meetings': len(meetings),
                'meetings': meetings
            }, f, indent=2, default=str)

    elif output_format == 'csv':
        import csv
        output_file = reports_dir / f'calendar_meetings_{timestamp}.csv'
        with open(output_file, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=[
                'summary', 'start', 'end', 'organizer', 'attendee_count',
                'myResponseStatus', 'location', 'htmlLink'
            ])
            writer.writeheader()
            for meeting in meetings:
                writer.writerow({
                    'summary': meeting['summary'],
                    'start': meeting['start'],
                    'end': meeting['end'],
                    'organizer': meeting['organizer'],
                    'attendee_count': len(meeting['attendees']),
                    'myResponseStatus': meeting.get('myResponseStatus', 'unknown'),
                    'location': meeting['location'],
                    'htmlLink': meeting['htmlLink']
                })

    elif output_format == 'markdown':
        output_file = reports_dir / f'calendar_meetings_{timestamp}.md'
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write(f"# Calendar Meetings Report\n\n")
            f.write(f"**Calendar:** {calendar_id}  \n")
            f.write(f"**Date Range:** {start_time.strftime('%Y-%m-%d')} to {end_time.strftime('%Y-%m-%d')}  \n")
            f.write(f"**Total Meetings:** {len(meetings)}  \n\n")
            f.write("---\n\n")

            for meeting in meetings:
                # Parse start and end times
                start_dt = datetime.fromisoformat(meeting['start'].replace('Z', '+00:00'))
                end_dt = datetime.fromisoformat(meeting['end'].replace('Z', '+00:00'))

                # Calculate duration
                duration = end_dt - start_dt
                hours, remainder = divmod(duration.total_seconds(), 3600)
                minutes = remainder // 60
                duration_str = f"{int(hours):02d}:{int(minutes):02d}"

                # Format date and time
                datetime_str = start_dt.strftime('%d/%m/%Y %H:%M')

                # Escape special characters
                summary = meeting['summary']

                f.write(f"{datetime_str} | {summary} | {duration_str}\n")

    print()
    print("=" * 80)
    print("  Export Complete")
    print("=" * 80)
    print(f"[OK] Results saved to: {output_file}")
    print(f"[INFO] Total meetings exported: {len(meetings)}")
    print(f"[INFO] Format: {output_format.upper()}")


def main() -> int:
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Extract meetings from Google Calendar",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Extract meetings from last 30 days (default)
  python scripts/calendar_meetings.py

  # Last 7 days in markdown format
  python scripts/calendar_meetings.py --days-back 7 --format markdown

  # Last 60 days including declined meetings
  python scripts/calendar_meetings.py --days-back 60 --include-declined

  # Export to CSV
  python scripts/calendar_meetings.py --format csv --days-back 30
"""
    )

    parser.add_argument(
        '--days-back',
        type=int,
        default=30,
        help='Number of days to look back (default: 30)'
    )

    parser.add_argument(
        '--calendar-id',
        type=str,
        default='primary',
        help='Calendar ID to search (default: primary)'
    )

    parser.add_argument(
        '--max-results',
        type=int,
        default=500,
        help='Maximum number of events to retrieve (default: 500)'
    )

    parser.add_argument(
        '--format',
        type=str,
        choices=['json', 'csv', 'markdown'],
        default='json',
        help='Output format (default: json)'
    )

    parser.add_argument(
        '--include-declined',
        action='store_true',
        help='Include meetings you declined'
    )

    parser.add_argument(
        '--work-only',
        action='store_true',
        help='Filter to work-related meetings only (exclude personal events)'
    )

    args = parser.parse_args()

    try:
        extract_meetings(
            days_back=args.days_back,
            calendar_id=args.calendar_id,
            max_results=args.max_results,
            output_format=args.format,
            include_declined=args.include_declined,
            work_only=args.work_only
        )
        return 0

    except KeyboardInterrupt:
        print("\n\nExtraction cancelled by user")
        return 1
    except Exception as e:
        print(f"\n✗ Error: {e}", file=sys.stderr)
        print("\nMake sure you've set up OAuth2 credentials:")
        print("  1. Enable Calendar API in Google Cloud Console")
        print("  2. Download OAuth2 credentials")
        print("  3. Save as config/oauth2_credentials.json")
        return 1


if __name__ == "__main__":
    sys.exit(main())
