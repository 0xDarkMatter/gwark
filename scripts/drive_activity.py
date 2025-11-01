#!/usr/bin/env python
"""Extract Google Drive file activity for a specified time period."""

import os
import sys
import argparse
from datetime import datetime
from pathlib import Path
from typing import List, Dict

# Shared OAuth authentication
from gmail_mcp.auth import get_drive_service


def get_file_type(mime_type: str) -> str:
    """Convert MIME type to readable file type."""
    mime_map = {
        'application/vnd.google-apps.document': 'Google Doc',
        'application/vnd.google-apps.spreadsheet': 'Google Sheet',
        'application/vnd.google-apps.presentation': 'Google Slides',
        'application/vnd.google-apps.form': 'Google Form',
        'application/vnd.google-apps.drawing': 'Google Drawing',
        'application/vnd.google-apps.folder': 'Folder',
        'application/pdf': 'PDF',
        'application/vnd.openxmlformats-officedocument.wordprocessingml.document': 'Word Doc',
        'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet': 'Excel',
        'application/vnd.openxmlformats-officedocument.presentationml.presentation': 'PowerPoint',
        'text/plain': 'Text File',
        'image/jpeg': 'JPEG Image',
        'image/png': 'PNG Image',
    }
    return mime_map.get(mime_type, mime_type.split('/')[-1].upper())


def extract_drive_activity(
    year: int = 2025,
    month: int = 10,
    output_format: str = 'markdown',
    include_shared_drives: bool = True,
    only_owned_by_me: bool = True
) -> None:
    """Extract Google Drive file activity.

    Args:
        year: Year to search
        month: Month to search
        output_format: Output format (markdown, json)
        include_shared_drives: Include shared drives
    """
    import calendar

    month_name = calendar.month_name[month]
    last_day = calendar.monthrange(year, month)[1]

    print("=" * 80)
    print(f"  Google Drive Activity - {month_name} {year}")
    print("=" * 80)
    print()

    # Calculate date range
    start_date = f"{year}-{month:02d}-01T00:00:00"
    end_date = f"{year}-{month:02d}-{last_day}T23:59:59"

    print(f"[INFO] Date Range: {month_name} 1-{last_day}, {year}")
    print(f"[INFO] Include Shared Drives: {include_shared_drives}")
    print()

    # Get Drive service
    print("[INFO] Connecting to Google Drive API...")
    service = get_drive_service()
    print("[OK] Connected")

    # Build query for files modified in the date range
    query = f"modifiedTime >= '{start_date}' and modifiedTime <= '{end_date}' and trashed = false"

    all_files = []

    # Search My Drive
    print("[INFO] Searching My Drive...")
    page_token = None
    my_drive_count = 0

    while True:
        try:
            results = service.files().list(
                q=query,
                spaces='drive',
                fields='nextPageToken, files(id, name, mimeType, modifiedTime, createdTime, owners, webViewLink, parents, driveId, lastModifyingUser)',
                pageToken=page_token,
                pageSize=1000,
                supportsAllDrives=True,
                includeItemsFromAllDrives=False
            ).execute()

            files = results.get('files', [])
            my_drive_count += len(files)

            for file in files:
                file['drive_location'] = 'My Drive'
                all_files.append(file)

            page_token = results.get('nextPageToken')
            if not page_token:
                break

        except Exception as e:
            print(f"[ERROR] Failed to fetch My Drive files: {e}")
            break

    print(f"[OK] Found {my_drive_count} files in My Drive")

    # Search Shared Drives
    if include_shared_drives:
        print("[INFO] Searching Shared Drives...")

        # First, get list of shared drives
        try:
            shared_drives_result = service.drives().list(
                pageSize=100,
                fields='drives(id, name)'
            ).execute()

            shared_drives = shared_drives_result.get('drives', [])
            print(f"[INFO] Found {len(shared_drives)} Shared Drives")

            shared_drive_count = 0
            for drive in shared_drives:
                drive_name = drive['name']
                drive_id = drive['id']

                page_token = None
                while True:
                    try:
                        results = service.files().list(
                            q=query,
                            spaces='drive',
                            corpora='drive',
                            driveId=drive_id,
                            fields='nextPageToken, files(id, name, mimeType, modifiedTime, createdTime, owners, webViewLink, parents, driveId, lastModifyingUser)',
                            pageToken=page_token,
                            pageSize=1000,
                            supportsAllDrives=True,
                            includeItemsFromAllDrives=True
                        ).execute()

                        files = results.get('files', [])

                        for file in files:
                            file['drive_location'] = f"Shared: {drive_name}"
                            all_files.append(file)

                        shared_drive_count += len(files)

                        page_token = results.get('nextPageToken')
                        if not page_token:
                            break

                    except Exception as e:
                        print(f"[ERROR] Failed to fetch from {drive_name}: {e}")
                        break

            print(f"[OK] Found {shared_drive_count} files in Shared Drives")

        except Exception as e:
            print(f"[ERROR] Failed to list Shared Drives: {e}")

    print(f"[OK] Total files found: {len(all_files)}")

    # Sort by modified time (most recent first)
    all_files.sort(key=lambda x: x.get('modifiedTime', ''), reverse=True)

    # Separate files into owned and contributed (for all formats)
    owned_files = []
    contributed_files = []

    for file in all_files:
        owners = file.get('owners', [])
        user_is_owner = any(owner.get('me', False) for owner in owners)
        last_modifier = file.get('lastModifyingUser', {})
        user_is_last_modifier = last_modifier.get('me', False)

        if user_is_owner:
            owned_files.append(file)
        elif user_is_last_modifier:
            contributed_files.append(file)

    # Export results
    project_root = Path(__file__).parent.parent
    reports_dir = project_root / 'reports'
    reports_dir.mkdir(exist_ok=True)

    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')

    if output_format == 'markdown':
        output_file = reports_dir / f'drive_activity_{year}{month:02d}_{timestamp}.md'

        with open(output_file, 'w', encoding='utf-8') as f:
            f.write(f"# Google Drive Activity - {month_name} {year}\n\n")
            f.write(f"**Files You Own:** {len(owned_files)}\n")
            f.write(f"**Files You Contributed To:** {len(contributed_files)}\n\n")

            # Section 1: Files you own
            if owned_files:
                f.write("## Files You Created or Own\n\n")
                f.write("---\n\n")

                for file in owned_files:
                    name = file.get('name', 'Unknown')
                    mime_type = file.get('mimeType', '')
                    file_type = get_file_type(mime_type)
                    modified = file.get('modifiedTime', '')
                    created = file.get('createdTime', '')
                    location = file.get('drive_location', 'Unknown')
                    link = file.get('webViewLink', '')

                    # Parse modified time
                    try:
                        mod_dt = datetime.fromisoformat(modified.replace('Z', '+00:00'))
                        mod_str = mod_dt.strftime('%d/%m/%Y %H:%M')
                    except:
                        mod_str = modified

                    # Determine action
                    if created and modified and created[:10] == modified[:10]:
                        action = "Created"
                    else:
                        action = "Edited"

                    f.write(f"{mod_str} | {action} | {file_type} | {name} | {location}")
                    if link:
                        f.write(f" | [View]({link})")
                    f.write("\n")

            # Section 2: Files you contributed to
            if contributed_files:
                f.write("\n## Files You Contributed To (Owned by Others)\n\n")
                f.write("---\n\n")

                for file in contributed_files:
                    name = file.get('name', 'Unknown')
                    mime_type = file.get('mimeType', '')
                    file_type = get_file_type(mime_type)
                    modified = file.get('modifiedTime', '')
                    location = file.get('drive_location', 'Unknown')
                    link = file.get('webViewLink', '')
                    owners = file.get('owners', [])
                    owner_name = owners[0].get('displayName', 'Unknown') if owners else 'Unknown'

                    # Parse modified time
                    try:
                        mod_dt = datetime.fromisoformat(modified.replace('Z', '+00:00'))
                        mod_str = mod_dt.strftime('%d/%m/%Y %H:%M')
                    except:
                        mod_str = modified

                    f.write(f"{mod_str} | Edited | {file_type} | {name} | Owner: {owner_name} | {location}")
                    if link:
                        f.write(f" | [View]({link})")
                    f.write("\n")

            files_written = len(owned_files) + len(contributed_files)

    elif output_format == 'json':
        import json
        output_file = reports_dir / f'drive_activity_{year}{month:02d}_{timestamp}.json'
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump({
                'month': month_name,
                'year': year,
                'total_files': len(all_files),
                'files': all_files
            }, f, indent=2, default=str)

    print()
    print("=" * 80)
    print("  Export Complete")
    print("=" * 80)
    print(f"[OK] Results saved to: {output_file}")
    if only_owned_by_me:
        print(f"[INFO] Total files found: {len(all_files)}")
        print(f"[INFO] Files you own: {len(owned_files)}")
        print(f"[INFO] Files you contributed to: {len(contributed_files)}")
    else:
        print(f"[INFO] Total files: {len(all_files)}")
    print(f"[INFO] Format: {output_format.upper()}")


def main() -> int:
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Extract Google Drive file activity",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Extract October 2025 activity (default)
  python scripts/drive_activity.py

  # Extract September 2025 activity
  python scripts/drive_activity.py --year 2025 --month 9

  # Export to JSON
  python scripts/drive_activity.py --format json

  # Exclude shared drives
  python scripts/drive_activity.py --no-shared-drives
"""
    )

    parser.add_argument(
        '--year',
        type=int,
        default=2025,
        help='Year to search (default: 2025)'
    )

    parser.add_argument(
        '--month',
        type=int,
        default=10,
        help='Month to search (default: 10)'
    )

    parser.add_argument(
        '--format',
        type=str,
        choices=['markdown', 'json'],
        default='markdown',
        help='Output format (default: markdown)'
    )

    parser.add_argument(
        '--no-shared-drives',
        action='store_true',
        help='Exclude shared drives from search'
    )

    parser.add_argument(
        '--include-others',
        action='store_true',
        help='Include files created by others (default: only show files you own)'
    )

    args = parser.parse_args()

    try:
        extract_drive_activity(
            year=args.year,
            month=args.month,
            output_format=args.format,
            include_shared_drives=not args.no_shared_drives,
            only_owned_by_me=not args.include_others
        )
        return 0

    except KeyboardInterrupt:
        print("\n\nExtraction cancelled by user")
        return 1
    except Exception as e:
        print(f"\n✗ Error: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        print("\nMake sure you've set up OAuth2 credentials:")
        print("  1. Enable Drive API in Google Cloud Console")
        print("  2. Download OAuth2 credentials")
        print("  3. Save as config/oauth2_credentials.json")
        return 1


if __name__ == "__main__":
    sys.exit(main())
