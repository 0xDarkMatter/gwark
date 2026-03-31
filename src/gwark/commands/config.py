"""Configuration commands for gwark CLI."""

import sys
from pathlib import Path
from typing import Optional

import typer
from rich.console import Console
from rich.syntax import Syntax
import yaml

# Add project root for imports
project_root = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(project_root))

from gwark.core.config import (
    load_config,
    save_config,
    get_profile,
    save_profile,
    init_config_dir,
    find_config_dir,
    CONFIG_DIR,
    PROFILES_DIR,
)
from gwark.core.constants import (
    EXIT_ERROR,
    EXIT_AUTH_REQUIRED,
    EXIT_NOT_FOUND,
    EXIT_VALIDATION,
)
from gwark.core.output import (
    print_success,
    print_info,
    print_error,
    print_header,
    print_warning,
)
from gwark.schemas.config import ProfileConfig

console = Console()
app = typer.Typer(no_args_is_help=True)

# Auth subcommands
auth_app = typer.Typer(help="Authentication management")
app.add_typer(auth_app, name="auth")

# Profile subcommands
profile_app = typer.Typer(help="Profile management")
app.add_typer(profile_app, name="profile")


@app.command()
def init(
    force: bool = typer.Option(False, "--force", "-f", help="Overwrite existing config"),
) -> None:
    """Initialize a new .gwark configuration directory."""
    print_header("gwark config init")

    try:
        config_dir = init_config_dir(force=force)
        print_success(f"Created configuration directory: {config_dir}")
        print_info("Created files:")
        print_info(f"  - {config_dir / 'config.yaml'}")
        print_info(f"  - {config_dir / PROFILES_DIR / 'default.yaml'}")
        print_info("")
        print_info("Next steps:")
        print_info("  1. Edit .gwark/config.yaml to customize defaults")
        print_info("  2. Run 'gwark config auth setup' to configure OAuth")
        print_info("  3. Create profiles in .gwark/profiles/ for different use cases")
    except FileExistsError as e:
        print_warning(str(e))
        print_info("Use --force to overwrite existing configuration")
        raise typer.Exit(EXIT_ERROR)
    except Exception as e:
        print_error(f"Failed to initialize: {e}")
        raise typer.Exit(EXIT_ERROR)


@app.command()
def show(
    profile_name: Optional[str] = typer.Option(None, "--profile", "-p", help="Show specific profile"),
) -> None:
    """Display current configuration."""
    print_header("gwark config show")

    config_dir = find_config_dir()
    if not config_dir:
        print_warning("No .gwark directory found. Run 'gwark config init' first.")
        raise typer.Exit(EXIT_ERROR)

    print_info(f"Config directory: {config_dir}")

    if profile_name:
        # Show specific profile
        profile = get_profile(profile_name)
        console.print(f"\n[bold]Profile: {profile_name}[/bold]\n")
        yaml_content = yaml.dump(profile.model_dump(), default_flow_style=False)
        syntax = Syntax(yaml_content, "yaml", theme="monokai", line_numbers=True)
        console.print(syntax)
    else:
        # Show main config
        config = load_config()
        console.print("\n[bold]Main Configuration[/bold]\n")
        yaml_content = yaml.dump(config.model_dump(), default_flow_style=False)
        syntax = Syntax(yaml_content, "yaml", theme="monokai", line_numbers=True)
        console.print(syntax)

        # List available profiles
        profiles_dir = config_dir / PROFILES_DIR
        if profiles_dir.exists():
            profiles = list(profiles_dir.glob("*.yaml"))
            if profiles:
                console.print("\n[bold]Available Profiles[/bold]")
                for p in profiles:
                    name = p.stem
                    active = " (active)" if name == config.active_profile else ""
                    console.print(f"  - {name}{active}")


@profile_app.command("list")
def profile_list() -> None:
    """List all available profiles."""
    print_header("gwark config profile list")

    config_dir = find_config_dir()
    if not config_dir:
        print_warning("No .gwark directory found. Run 'gwark config init' first.")
        raise typer.Exit(EXIT_ERROR)

    config = load_config()
    profiles_dir = config_dir / PROFILES_DIR

    if not profiles_dir.exists():
        print_info("No profiles directory found.")
        return

    profiles = list(profiles_dir.glob("*.yaml"))
    if not profiles:
        print_info("No profiles found.")
        return

    console.print("\n[bold]Available Profiles[/bold]\n")
    for p in profiles:
        name = p.stem
        active = " [green](active)[/green]" if name == config.active_profile else ""
        profile = get_profile(name)
        desc = profile.description or "No description"
        console.print(f"  [cyan]{name}[/cyan]{active}")
        console.print(f"    {desc}")


@profile_app.command("create")
def profile_create(
    name: str = typer.Argument(..., help="Profile name"),
    description: str = typer.Option("", "--description", "-d", help="Profile description"),
) -> None:
    """Create a new profile."""
    print_header(f"gwark config profile create {name}")

    config_dir = find_config_dir()
    if not config_dir:
        print_warning("No .gwark directory found. Run 'gwark config init' first.")
        raise typer.Exit(EXIT_ERROR)

    profile_path = config_dir / PROFILES_DIR / f"{name}.yaml"
    if profile_path.exists():
        print_warning(f"Profile '{name}' already exists.")
        raise typer.Exit(EXIT_ERROR)

    profile = ProfileConfig(name=name, description=description)
    save_profile(profile, config_dir)

    print_success(f"Created profile: {profile_path}")
    print_info("Edit the file to customize filters and settings.")


@profile_app.command("delete")
def profile_delete(
    name: str = typer.Argument(..., help="Profile name to delete"),
    force: bool = typer.Option(False, "--force", "-f", help="Skip confirmation"),
) -> None:
    """Delete a profile."""
    config_dir = find_config_dir()
    if not config_dir:
        print_warning("No .gwark directory found.")
        raise typer.Exit(EXIT_ERROR)

    profile_path = config_dir / PROFILES_DIR / f"{name}.yaml"
    if not profile_path.exists():
        print_warning(f"Profile '{name}' not found.")
        raise typer.Exit(EXIT_ERROR)

    if name == "default":
        print_warning("Cannot delete the default profile.")
        raise typer.Exit(EXIT_ERROR)

    if not force:
        confirm = typer.confirm(f"Delete profile '{name}'?")
        if not confirm:
            raise typer.Abort()

    profile_path.unlink()
    print_success(f"Deleted profile: {name}")


@auth_app.command("setup")
def auth_setup(
    service: str = typer.Option(
        "all", "--service", "-s",
        help="Google service to authenticate (gmail, calendar, drive, sheets, docs, forms, slides, people, all)",
    ),
    manual: bool = typer.Option(False, "--manual", help="Use manual authorization code flow"),
    port: int = typer.Option(8080, "--port", "-p", help="Port for OAuth callback"),
) -> None:
    """Set up OAuth2 authentication.

    Authenticates with Google APIs and stores tokens in OS keyring
    (Fabric-compliant: fabric-gwark service).
    """
    print_header("gwark config auth setup")

    try:
        from gmail_mcp.auth import OAuth2Manager, get_credential_store
        from pathlib import Path

        config = load_config()
        credentials_path = config.auth.credentials_path

        if not credentials_path.exists():
            print_error(f"Credentials file not found: {credentials_path}")
            print_info("Download OAuth2 credentials from Google Cloud Console")
            print_info(f"Save as: {credentials_path}")
            raise typer.Exit(EXIT_ERROR)

        print_info(f"Using credentials: {credentials_path}")
        print_info(f"Token storage: OS keyring (fabric-gwark)")

        # Determine which services to authenticate
        service_scopes = {
            "gmail": ["https://www.googleapis.com/auth/gmail.readonly"],
            "calendar": ["https://www.googleapis.com/auth/calendar.readonly"],
            "drive": ["https://www.googleapis.com/auth/drive"],
            "sheets": [
                "https://www.googleapis.com/auth/spreadsheets",
                "https://www.googleapis.com/auth/drive.file",
                "https://www.googleapis.com/auth/drive.metadata.readonly",
            ],
            "docs": ["https://www.googleapis.com/auth/documents"],
            "forms": [
                "https://www.googleapis.com/auth/forms.body",
                "https://www.googleapis.com/auth/forms.responses.readonly",
            ],
            "slides": ["https://www.googleapis.com/auth/presentations"],
            "people": [
                "https://www.googleapis.com/auth/contacts.readonly",
                "https://www.googleapis.com/auth/contacts.other.readonly",
            ],
        }

        if service == "all":
            # Combined scopes for a single auth flow
            all_scopes = []
            for scopes in service_scopes.values():
                all_scopes.extend(scopes)
            targets = [("all", list(set(all_scopes)))]
        elif service in service_scopes:
            targets = [(service, service_scopes[service])]
        else:
            print_error(f"Unknown service: {service}")
            print_info(f"Valid services: {', '.join(service_scopes.keys())}, all")
            raise typer.Exit(EXIT_VALIDATION)

        store = get_credential_store()

        for svc_name, scopes in targets:
            print_info(f"\nAuthenticating: {svc_name}")

            manager = OAuth2Manager(
                credentials_path=Path(credentials_path),
                scopes=scopes,
            )

            if manual:
                print_info("Starting manual OAuth2 flow...")
                auth_url, state = manager.get_authorization_url()
                print_info(f"\nOpen this URL in your browser:\n")
                print(auth_url)
                print()
                auth_code = typer.prompt("Enter the authorization code")
                credentials = manager.exchange_code_for_token(auth_code)
            else:
                print_info("A browser window will open for authentication.")
                credentials = manager.run_local_server_flow(port=port)

            if credentials and (credentials.token or credentials.refresh_token):
                if svc_name == "all":
                    # Save under each service name so per-service lookup works
                    for name in service_scopes:
                        store.save_google_credentials(credentials, name)
                    store.save_google_credentials(credentials, "default")
                else:
                    store.save_google_credentials(credentials, svc_name)

                print_success(f"Authentication successful for: {svc_name}")
                print_info(f"Stored in: OS keyring (fabric-gwark)")
            else:
                print_error(f"Authentication failed for: {svc_name}")
                raise typer.Exit(EXIT_ERROR)

    except ImportError as e:
        print_error(f"Missing dependency: {e}")
        raise typer.Exit(EXIT_ERROR)
    except Exception as e:
        print_error(f"Setup failed: {e}")
        raise typer.Exit(EXIT_ERROR)


@auth_app.command("test")
def auth_test(
    all_apis: bool = typer.Option(False, "--all", "-a", help="Test all Google APIs (not just Gmail)"),
) -> None:
    """Test OAuth2 connection and API availability.

    By default, tests Gmail only. Use --all to check every API gwark uses.

    Examples:
        gwark config auth test          # Quick Gmail check
        gwark config auth test --all    # Full preflight check
    """
    print_header("gwark config auth test")

    try:
        from gmail_mcp.auth import get_gmail_service

        print_info("Testing Gmail API connection...")

        service = get_gmail_service()
        profile = service.users().getProfile(userId="me").execute()

        print_success("Gmail API connected")
        print_info(f"Email: {profile.get('emailAddress')}")
        print_info(f"Messages: {profile.get('messagesTotal')}")

    except Exception as e:
        print_error(f"Gmail connection failed: {e}")
        print_info("Run: gwark config auth setup")
        raise typer.Exit(EXIT_ERROR)

    if not all_apis:
        print_info("Use --all to test all Google APIs")
        return

    # Full preflight check
    _preflight_check_all()


# Google Cloud Console enable URLs for each API
_API_ENABLE_URLS = {
    "Gmail": "https://console.cloud.google.com/apis/library/gmail.googleapis.com",
    "Calendar": "https://console.cloud.google.com/apis/library/calendar-json.googleapis.com",
    "Drive": "https://console.cloud.google.com/apis/library/drive.googleapis.com",
    "Docs": "https://console.cloud.google.com/apis/library/docs.googleapis.com",
    "Sheets": "https://console.cloud.google.com/apis/library/sheets.googleapis.com",
    "Slides": "https://console.cloud.google.com/apis/library/slides.googleapis.com",
    "Forms": "https://console.cloud.google.com/apis/library/forms.googleapis.com",
    "People": "https://console.cloud.google.com/apis/library/people.googleapis.com",
}


def _preflight_check_all() -> None:
    """Test all Google APIs used by gwark."""
    from rich.table import Table

    console_out = Console(stderr=True)

    # Define checks: (name, get_service_func, test_call, required)
    checks = [
        ("Calendar", "_check_calendar", True),
        ("Drive", "_check_drive", True),
        ("Docs", "_check_docs", False),
        ("Sheets", "_check_sheets", False),
        ("Slides", "_check_slides", False),
        ("Forms", "_check_forms", False),
        ("People", "_check_people", False),
    ]

    results = []
    for api_name, check_func, required in checks:
        status, detail = globals()[check_func]()
        results.append((api_name, status, detail, required))

    # Display results table
    table = Table(title="API Preflight Check", show_header=True, header_style="bold")
    table.add_column("API", style="cyan")
    table.add_column("Status", justify="center")
    table.add_column("Detail")
    table.add_column("Action")

    passed = 0
    failed = 0
    skipped = 0

    for api_name, status, detail, required in results:
        if status == "ok":
            status_str = "[green]OK[/green]"
            action = ""
            passed += 1
        elif status == "disabled":
            status_str = "[red]DISABLED[/red]" if required else "[yellow]DISABLED[/yellow]"
            action = f"[link={_API_ENABLE_URLS.get(api_name, '')}]Enable API[/link]"
            failed += 1
        elif status == "no_token":
            status_str = "[dim]NO TOKEN[/dim]"
            action = f"Run: gwark {api_name.lower()} ... (auto-authenticates)"
            skipped += 1
        else:
            status_str = "[red]ERROR[/red]"
            action = detail
            failed += 1

        table.add_row(api_name, status_str, detail[:60], action)

    console_out.print()
    console_out.print(table)
    console_out.print()

    # Summary
    total = passed + failed + skipped
    if failed == 0:
        print_success(f"All APIs ready ({passed} ok, {skipped} not yet authenticated)")
    else:
        print_warning(f"{failed} API(s) need attention ({passed} ok, {skipped} not yet authenticated)")
        console_out.print()
        console_out.print("[bold]To enable a disabled API:[/bold]")
        console_out.print("  1. Click the 'Enable API' link above (or copy the URL)")
        console_out.print("  2. Click 'Enable' in Google Cloud Console")
        console_out.print("  3. Wait 1-2 minutes, then re-run: gwark config auth test --all")


def _check_api(svc_key, get_service_fn, test_fn):
    """Generic API check: get service, run test call, return (status, detail)."""
    from gmail_mcp.auth.oauth import has_credentials
    from googleapiclient.errors import HttpError

    # Check if token exists before triggering OAuth browser flow
    if not has_credentials(svc_key):
        return "no_token", "Not authenticated yet"

    try:
        service = get_service_fn()
    except SystemExit:
        return "no_token", "Not authenticated yet"
    except Exception as e:
        return "error", str(e)[:80]

    try:
        test_fn(service)
        return "ok", "Connected"
    except HttpError as e:
        msg = str(e)
        if "not been used in project" in msg or "is disabled" in msg:
            return "disabled", "API not enabled in Google Cloud project"
        if "REQUEST_DENIED" in msg:
            return "disabled", "API access denied"
        return "error", e.reason[:80] if hasattr(e, 'reason') else str(e)[:80]
    except Exception as e:
        return "error", str(e)[:80]


def _check_calendar():
    from gmail_mcp.auth import get_calendar_service
    return _check_api(
        "calendar", get_calendar_service,
        lambda svc: svc.calendarList().list(maxResults=1).execute(),
    )


def _check_drive():
    from gmail_mcp.auth import get_drive_service
    return _check_api(
        "drive", get_drive_service,
        lambda svc: svc.files().list(pageSize=1, fields="files(id)").execute(),
    )


def _check_docs():
    from gmail_mcp.auth import get_docs_service
    return _check_api(
        "docs", get_docs_service,
        lambda svc: _check_docs_api(svc),
    )


def _check_docs_api(docs_service):
    """Check if Docs API is enabled by attempting to get a non-existent doc."""
    from googleapiclient.errors import HttpError
    try:
        docs_service.documents().get(documentId="test_nonexistent").execute()
    except HttpError as e:
        if e.resp.status == 404:
            return  # 404 means API is enabled, doc just doesn't exist
        raise  # Re-raise 403 (disabled) or other errors


def _check_sheets():
    from gmail_mcp.auth.oauth import has_credentials
    if not has_credentials("sheets"):
        return "no_token", "Not authenticated yet"

    from gmail_mcp.auth import get_sheets_client
    try:
        client = get_sheets_client()
        client.list_spreadsheet_files()
        return "ok", "Connected"
    except SystemExit:
        return "no_token", "Not authenticated yet"
    except Exception as e:
        msg = str(e)
        if "not been used" in msg or "is disabled" in msg:
            return "disabled", "API not enabled in Google Cloud project"
        return "error", str(e)[:80]


def _check_slides():
    from gmail_mcp.auth import get_slides_service
    return _check_api(
        "slides", get_slides_service,
        lambda svc: _check_slides_api(svc),
    )


def _check_slides_api(slides_service):
    """Check if Slides API is enabled by attempting to get a non-existent presentation."""
    from googleapiclient.errors import HttpError
    try:
        slides_service.presentations().get(presentationId="test_nonexistent").execute()
    except HttpError as e:
        if e.resp.status == 404:
            return  # API enabled, presentation doesn't exist
        raise


def _check_forms():
    from gmail_mcp.auth import get_forms_service
    return _check_api(
        "forms", get_forms_service,
        lambda svc: _check_forms_api(svc),
    )


def _check_forms_api(forms_service):
    """Check if Forms API is enabled by attempting to get a non-existent form."""
    from googleapiclient.errors import HttpError
    try:
        forms_service.forms().get(formId="test_nonexistent").execute()
    except HttpError as e:
        if e.resp.status == 404:
            return  # API enabled, form doesn't exist
        raise


def _check_people():
    from gmail_mcp.auth import get_people_service
    return _check_api(
        "people", get_people_service,
        lambda svc: svc.people().connections().list(
            resourceName="people/me", pageSize=1, personFields="names"
        ).execute(),
    )


@auth_app.command("list")
def auth_list() -> None:
    """List configured accounts."""
    print_header("gwark config auth list")

    try:
        from gmail_mcp.auth import get_credential_store

        store = get_credential_store()
        status = store.status()

        if not status["authenticated"]:
            print_info("No accounts configured yet.")
            print_info("Run 'gwark config auth setup' to add an account.")
            return

        console.print("\n[bold]Configured Services[/bold]\n")
        console.print(f"  Storage: [cyan]{status['source']}[/cyan] (keyring: {'available' if status['keyring_available'] else 'not available'})")
        console.print("")

        for svc in status["services"]:
            source = store.get_credentials_source(svc)
            console.print(f"  - [cyan]{svc}[/cyan] ({source})")

    except Exception as e:
        print_error(f"Failed to list accounts: {e}")
        raise typer.Exit(EXIT_ERROR)


@auth_app.command("remove")
def auth_remove(
    service: str = typer.Argument(..., help="Service to remove (gmail, calendar, drive, etc. or 'all')"),
    force: bool = typer.Option(False, "--force", "-f", help="Skip confirmation"),
) -> None:
    """Remove stored credentials for a service."""
    try:
        from gmail_mcp.auth import get_credential_store

        store = get_credential_store()

        if service == "all":
            services = store.list_services()
            if not services:
                print_warning("No credentials found.")
                raise typer.Exit(EXIT_ERROR)

            if not force:
                confirm = typer.confirm(f"Remove credentials for all {len(services)} services?")
                if not confirm:
                    raise typer.Abort()

            for svc in services:
                store.delete_google_credentials(svc)
            print_success(f"Removed credentials for: {', '.join(services)}")
        else:
            if not store.has_google_credentials(service):
                print_warning(f"No credentials found for '{service}'.")
                raise typer.Exit(EXIT_ERROR)

            if not force:
                confirm = typer.confirm(f"Remove credentials for '{service}'?")
                if not confirm:
                    raise typer.Abort()

            store.delete_google_credentials(service)
            print_success(f"Removed credentials for: {service}")

    except Exception as e:
        print_error(f"Failed to remove: {e}")
        raise typer.Exit(EXIT_ERROR)
