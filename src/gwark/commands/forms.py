"""Forms commands for gwark CLI."""

import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional

import typer
from rich.console import Console

# Add project root for imports
project_root = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(project_root))

from gwark.core.config import load_config
from gwark.core.constants import EXIT_ERROR, EXIT_VALIDATION
from gwark.core.output import (
    OutputFormatter,
    print_success,
    print_info,
    print_error,
    print_header,
)
from gwark.core.async_utils import retry_execute

console = Console()
app = typer.Typer(no_args_is_help=True)


# Question type mapping for add-question command
QUESTION_TYPE_MAP = {
    "text": "Short answer text",
    "paragraph": "Long answer text",
    "choice": "Multiple choice (radio)",
    "checkbox": "Checkboxes",
    "dropdown": "Dropdown menu",
    "scale": "Linear scale",
    "date": "Date picker",
    "time": "Time picker",
}


def _extract_form_id(form_id_or_url: str) -> str:
    """Extract form ID from URL or return as-is.

    Handles:
    - https://docs.google.com/forms/d/{FORM_ID}/edit
    - https://docs.google.com/forms/d/{FORM_ID}/viewform
    - Raw form ID
    """
    match = re.search(r'/forms/d/([a-zA-Z0-9_-]+)', form_id_or_url)
    return match.group(1) if match else form_id_or_url


@app.command("list")
def list_forms(
    max_results: int = typer.Option(50, "--max-results", "-n", help="Maximum results"),
    owned_only: bool = typer.Option(False, "--owned-only", help="Only forms you own"),
    output_format: str = typer.Option("markdown", "--format", "-f", help="Output format: json, markdown"),
    output: Optional[Path] = typer.Option(None, "--output", "-o", help="Output file path"),
) -> None:
    """List Google Forms (via Drive API)."""
    config = load_config()

    print_header("gwark forms list")
    print_info("Fetching forms from Drive...")

    try:
        from gmail_mcp.auth import get_drive_service

        drive = get_drive_service()

        # Build query for forms
        query = "mimeType='application/vnd.google-apps.form' and trashed=false"
        if owned_only:
            query += " and 'me' in owners"

        results = retry_execute(
            drive.files().list(
                q=query,
                fields="files(id, name, createdTime, modifiedTime, owners, webViewLink)",
                pageSize=max_results,
                orderBy="modifiedTime desc",
            ),
            operation="List forms",
        )

        forms = results.get('files', [])
        print_info(f"Found {len(forms)} forms")

        # Process forms
        processed_forms = []
        for f in forms:
            owners = f.get("owners", [])
            owner_email = owners[0].get("emailAddress", "Unknown") if owners else "Unknown"

            processed_forms.append({
                "id": f.get("id"),
                "title": f.get("name", "Untitled"),
                "createdTime": f.get("createdTime", ""),
                "modifiedTime": f.get("modifiedTime", ""),
                "owner": owner_email,
                "link": f.get("webViewLink", ""),
            })

        # Format output
        formatter = OutputFormatter(output_dir=config.defaults.output_directory)

        if output_format == "json":
            content = formatter.to_json(processed_forms)
            ext = "json"
        else:
            content = _format_forms_markdown(processed_forms)
            ext = "md"

        prefix = "forms_list"
        output_path = formatter.save(content, prefix, ext, output)
        print_success(f"Saved to: {output_path}")

    except ImportError as e:
        print_error(f"Missing dependency: {e}")
        print_info("Run: pip install -e . and ensure OAuth is configured")
        raise typer.Exit(EXIT_ERROR)
    except Exception as e:
        print_error(f"Failed: {e}")
        raise typer.Exit(EXIT_ERROR)


@app.command("get")
def get_form(
    form_id: str = typer.Argument(..., help="Form ID or URL"),
    output_format: str = typer.Option("markdown", "--format", "-f", help="Output format: json, markdown"),
    output: Optional[Path] = typer.Option(None, "--output", "-o", help="Output file path"),
) -> None:
    """Get form structure and questions."""
    config = load_config()

    form_id = _extract_form_id(form_id)
    print_header("gwark forms get")
    print_info(f"Fetching form: {form_id}")

    try:
        from gmail_mcp.auth import get_forms_service

        service = get_forms_service()
        form = retry_execute(
            service.forms().get(formId=form_id),
            operation="Get form",
        )

        print_success(f"Retrieved form: {form.get('info', {}).get('title', 'Untitled')}")

        # Format output
        formatter = OutputFormatter(output_dir=config.defaults.output_directory)

        if output_format == "json":
            content = formatter.to_json(form)
            ext = "json"
        else:
            content = _format_form_markdown(form)
            ext = "md"

        prefix = f"form_{form_id[:8]}"
        output_path = formatter.save(content, prefix, ext, output)
        print_success(f"Saved to: {output_path}")

    except ImportError as e:
        print_error(f"Missing dependency: {e}")
        print_info("Run: pip install -e . and ensure OAuth is configured")
        raise typer.Exit(EXIT_ERROR)
    except Exception as e:
        print_error(f"Failed: {e}")
        raise typer.Exit(EXIT_ERROR)


@app.command()
def responses(
    form_id: str = typer.Argument(..., help="Form ID or URL"),
    max_results: int = typer.Option(500, "--max-results", "-n", help="Maximum responses"),
    output_format: str = typer.Option("markdown", "--format", "-f", help="Output format: json, csv, markdown"),
    output: Optional[Path] = typer.Option(None, "--output", "-o", help="Output file path"),
) -> None:
    """Get form responses."""
    config = load_config()

    form_id = _extract_form_id(form_id)
    print_header("gwark forms responses")
    print_info(f"Fetching responses for form: {form_id}")

    try:
        from gmail_mcp.auth import get_forms_service

        service = get_forms_service()

        # First get form structure for question titles
        form = retry_execute(
            service.forms().get(formId=form_id),
            operation="Get form structure",
        )
        form_title = form.get("info", {}).get("title", "Untitled")

        # Build question ID -> title mapping
        question_map = {}
        for item in form.get("items", []):
            item_id = item.get("itemId")
            title = item.get("title", "Untitled")
            question_map[item_id] = title

        # Fetch responses with pagination
        all_responses = []
        page_token = None

        while len(all_responses) < max_results:
            result = retry_execute(
                service.forms().responses().list(
                    formId=form_id,
                    pageToken=page_token,
                    pageSize=min(100, max_results - len(all_responses)),
                ),
                operation="List form responses",
            )

            responses_batch = result.get('responses', [])
            all_responses.extend(responses_batch)

            page_token = result.get('nextPageToken')
            if not page_token:
                break

        print_info(f"Found {len(all_responses)} responses")

        # Process responses
        processed_responses = []
        for resp in all_responses:
            answers = {}
            for q_id, answer_data in resp.get("answers", {}).items():
                question_title = question_map.get(q_id, q_id)
                text_answers = answer_data.get("textAnswers", {}).get("answers", [])
                answer_values = [a.get("value", "") for a in text_answers]
                answers[question_title] = ", ".join(answer_values) if answer_values else ""

            processed_responses.append({
                "responseId": resp.get("responseId"),
                "respondentEmail": resp.get("respondentEmail", "Anonymous"),
                "createTime": resp.get("createTime", ""),
                "lastSubmittedTime": resp.get("lastSubmittedTime", ""),
                "answers": answers,
            })

        print_success(f"Processed {len(processed_responses)} responses")

        # Format output
        formatter = OutputFormatter(output_dir=config.defaults.output_directory)

        if output_format == "json":
            content = formatter.to_json({
                "formId": form_id,
                "formTitle": form_title,
                "totalResponses": len(processed_responses),
                "responses": processed_responses,
            })
            ext = "json"
        elif output_format == "csv":
            # Flatten for CSV
            flat_responses = []
            for resp in processed_responses:
                flat = {
                    "responseId": resp["responseId"],
                    "respondentEmail": resp["respondentEmail"],
                    "submittedTime": resp["lastSubmittedTime"],
                }
                flat.update(resp["answers"])
                flat_responses.append(flat)
            content = formatter.to_csv(flat_responses)
            ext = "csv"
        else:
            content = _format_responses_markdown(form_title, processed_responses, question_map)
            ext = "md"

        prefix = f"form_responses_{form_id[:8]}"
        output_path = formatter.save(content, prefix, ext, output)
        print_success(f"Saved to: {output_path}")

    except ImportError as e:
        print_error(f"Missing dependency: {e}")
        print_info("Run: pip install -e . and ensure OAuth is configured")
        raise typer.Exit(EXIT_ERROR)
    except Exception as e:
        print_error(f"Failed: {e}")
        raise typer.Exit(EXIT_ERROR)


@app.command()
def create(
    title: str = typer.Argument(..., help="Form title"),
    description: Optional[str] = typer.Option(None, "--description", "-d", help="Form description"),
    quiz: bool = typer.Option(False, "--quiz", help="Enable quiz mode"),
) -> None:
    """Create a new Google Form."""
    print_header("gwark forms create")
    print_info(f"Creating form: {title}")

    try:
        from gmail_mcp.auth import get_forms_service

        service = get_forms_service()

        # Step 1: Create form with title
        form = retry_execute(
            service.forms().create(body={"info": {"title": title}}),
            operation="Create form",
        )
        form_id = form["formId"]
        print_info(f"Created form ID: {form_id}")

        # Step 2: Add description/settings via batchUpdate
        requests = []
        if description:
            requests.append({
                "updateFormInfo": {
                    "info": {"description": description},
                    "updateMask": "description"
                }
            })
        if quiz:
            requests.append({
                "updateSettings": {
                    "settings": {"quizSettings": {"isQuiz": True}},
                    "updateMask": "quizSettings.isQuiz"
                }
            })

        if requests:
            retry_execute(
                service.forms().batchUpdate(formId=form_id, body={"requests": requests}),
                operation="Update form settings",
            )
            print_info("Applied settings")

        edit_url = f"https://docs.google.com/forms/d/{form_id}/edit"
        view_url = f"https://docs.google.com/forms/d/{form_id}/viewform"

        print_success(f"Form created successfully!")
        console.print(f"\n[bold]Form ID:[/bold] {form_id}")
        console.print(f"[bold]Edit URL:[/bold] {edit_url}")
        console.print(f"[bold]View URL:[/bold] {view_url}")

    except ImportError as e:
        print_error(f"Missing dependency: {e}")
        print_info("Run: pip install -e . and ensure OAuth is configured")
        raise typer.Exit(EXIT_ERROR)
    except Exception as e:
        print_error(f"Failed: {e}")
        raise typer.Exit(EXIT_ERROR)


@app.command("add-question")
def add_question(
    form_id: str = typer.Argument(..., help="Form ID or URL"),
    title: str = typer.Option(..., "--title", "-t", help="Question text"),
    qtype: str = typer.Option("text", "--type", help="Question type: text, paragraph, choice, checkbox, dropdown, scale"),
    required: bool = typer.Option(False, "--required", "-r", help="Make question required"),
    choices: Optional[str] = typer.Option(None, "--choices", "-c", help="Comma-separated choices (for choice/checkbox/dropdown)"),
    low: int = typer.Option(1, "--low", help="Low value for scale (default 1)"),
    high: int = typer.Option(5, "--high", help="High value for scale (default 5)"),
) -> None:
    """Add a question to an existing form."""
    form_id = _extract_form_id(form_id)
    print_header("gwark forms add-question")
    print_info(f"Adding question to form: {form_id}")

    # Validate question type
    valid_types = ["text", "paragraph", "choice", "checkbox", "dropdown", "scale", "date", "time"]
    if qtype not in valid_types:
        print_error(f"Invalid question type: {qtype}")
        print_info(f"Valid types: {', '.join(valid_types)}")
        raise typer.Exit(EXIT_VALIDATION)

    # Validate choices for choice-based types
    if qtype in ("choice", "checkbox", "dropdown") and not choices:
        print_error(f"Question type '{qtype}' requires --choices option")
        print_info("Example: --choices 'Option A, Option B, Option C'")
        raise typer.Exit(EXIT_VALIDATION)

    try:
        from gmail_mcp.auth import get_forms_service

        service = get_forms_service()

        # Build question based on type
        question = {"required": required}

        if qtype == "text":
            question["textQuestion"] = {"paragraph": False}
        elif qtype == "paragraph":
            question["textQuestion"] = {"paragraph": True}
        elif qtype in ("choice", "checkbox", "dropdown"):
            type_map = {"choice": "RADIO", "checkbox": "CHECKBOX", "dropdown": "DROP_DOWN"}
            options = [{"value": c.strip()} for c in choices.split(",") if c.strip()]
            question["choiceQuestion"] = {"type": type_map[qtype], "options": options}
        elif qtype == "scale":
            question["scaleQuestion"] = {"low": low, "high": high}
        elif qtype == "date":
            question["dateQuestion"] = {}
        elif qtype == "time":
            question["timeQuestion"] = {}

        # Create item request
        request = {
            "createItem": {
                "item": {
                    "title": title,
                    "questionItem": {"question": question}
                },
                "location": {"index": 0}  # Will be appended at end
            }
        }

        # Get current form to determine next index
        form = retry_execute(
            service.forms().get(formId=form_id),
            operation="Get form",
        )
        items = form.get("items", [])
        request["createItem"]["location"]["index"] = len(items)

        # Execute batch update
        retry_execute(
            service.forms().batchUpdate(formId=form_id, body={"requests": [request]}),
            operation="Add question",
        )

        print_success(f"Added question: {title}")
        print_info(f"Type: {QUESTION_TYPE_MAP.get(qtype, qtype)}")
        if required:
            print_info("Required: Yes")

    except ImportError as e:
        print_error(f"Missing dependency: {e}")
        print_info("Run: pip install -e . and ensure OAuth is configured")
        raise typer.Exit(EXIT_ERROR)
    except Exception as e:
        print_error(f"Failed: {e}")
        raise typer.Exit(EXIT_ERROR)


def _format_forms_markdown(forms: list) -> str:
    """Format forms list as markdown table."""
    lines = []
    lines.append("# Google Forms\n")
    lines.append(f"*Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}*\n")
    lines.append(f"*Total: {len(forms)} forms*\n")

    lines.append("| Modified | Title | Owner | Link |")
    lines.append("|----------|-------|-------|------|")

    for f in forms:
        try:
            mod_time = datetime.fromisoformat(f["modifiedTime"].replace("Z", "+00:00"))
            date_str = mod_time.strftime("%Y-%m-%d")
        except Exception:
            date_str = f.get("modifiedTime", "")[:10]

        title = f.get("title", "Untitled").replace("|", "\\|")[:40]
        owner = f.get("owner", "").split("@")[0]
        link = f.get("link", "")

        lines.append(f"| {date_str} | {title} | {owner} | [Open]({link}) |")

    return "\n".join(lines)


def _format_form_markdown(form: dict) -> str:
    """Format form structure as markdown."""
    lines = []
    info = form.get("info", {})
    title = info.get("title", "Untitled")
    description = info.get("description", "")

    lines.append(f"# {title}\n")
    if description:
        lines.append(f"*{description}*\n")

    lines.append(f"**Form ID:** `{form.get('formId')}`\n")
    lines.append(f"**Response URL:** {form.get('responderUri', 'N/A')}\n")

    # Settings
    settings = form.get("settings", {})
    quiz_settings = settings.get("quizSettings", {})
    if quiz_settings.get("isQuiz"):
        lines.append("**Mode:** Quiz\n")

    # Questions
    items = form.get("items", [])
    if items:
        lines.append("## Questions\n")
        for i, item in enumerate(items, 1):
            item_title = item.get("title", "Untitled")
            item_desc = item.get("description", "")
            question_item = item.get("questionItem", {})
            question = question_item.get("question", {})
            required = question.get("required", False)

            # Determine question type
            q_type = "Unknown"
            if "textQuestion" in question:
                q_type = "Paragraph" if question["textQuestion"].get("paragraph") else "Short answer"
            elif "choiceQuestion" in question:
                choice_type = question["choiceQuestion"].get("type", "")
                type_names = {"RADIO": "Multiple choice", "CHECKBOX": "Checkboxes", "DROP_DOWN": "Dropdown"}
                q_type = type_names.get(choice_type, "Choice")
            elif "scaleQuestion" in question:
                scale = question["scaleQuestion"]
                q_type = f"Scale ({scale.get('low', 1)}-{scale.get('high', 5)})"
            elif "dateQuestion" in question:
                q_type = "Date"
            elif "timeQuestion" in question:
                q_type = "Time"

            req_marker = " *" if required else ""
            lines.append(f"{i}. **{item_title}**{req_marker}")
            lines.append(f"   - Type: {q_type}")
            if item_desc:
                lines.append(f"   - Description: {item_desc}")

            # Show choices if applicable
            if "choiceQuestion" in question:
                options = question["choiceQuestion"].get("options", [])
                if options:
                    lines.append("   - Options:")
                    for opt in options:
                        lines.append(f"     - {opt.get('value', '')}")

            lines.append("")

        lines.append("\n*Questions marked with * are required*")

    return "\n".join(lines)


def _format_responses_markdown(form_title: str, responses: list, question_map: dict) -> str:
    """Format form responses as markdown."""
    lines = []
    lines.append(f"# Responses: {form_title}\n")
    lines.append(f"*Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}*\n")
    lines.append(f"*Total: {len(responses)} responses*\n")

    if not responses:
        lines.append("No responses yet.")
        return "\n".join(lines)

    # Summary
    lines.append("## Summary\n")
    lines.append(f"- Total responses: {len(responses)}")
    lines.append("")

    # Response details
    lines.append("## Responses\n")
    for i, resp in enumerate(responses, 1):
        email = resp.get("respondentEmail", "Anonymous")
        time_str = resp.get("lastSubmittedTime", "")[:16].replace("T", " ")

        lines.append(f"### Response {i}")
        lines.append(f"- **Submitted:** {time_str}")
        lines.append(f"- **Email:** {email}")
        lines.append("")

        for question, answer in resp.get("answers", {}).items():
            q_display = question.replace("|", "\\|")[:50]
            a_display = str(answer).replace("|", "\\|")[:100] if answer else "(no answer)"
            lines.append(f"**{q_display}:** {a_display}")

        lines.append("\n---\n")

    return "\n".join(lines)
