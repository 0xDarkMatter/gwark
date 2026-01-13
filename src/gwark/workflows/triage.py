"""Email triage workflow for gwark."""

from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from gwark.core.config import load_config, get_profile
from gwark.core.dates import date_to_gmail_query
from gwark.core.email_utils import (
    apply_email_filters,
    detect_response_status,
    extract_email_details,
)
from gwark.core.output import print_info, print_success, print_error
from gwark.schemas.config import EmailFilters
from gwark.workflows.base import (
    Workflow,
    WorkflowResult,
    WorkflowStage,
    register_workflow,
)


@register_workflow
class TriageWorkflow(Workflow):
    """Email triage workflow - inbox review, audits, catchup."""

    name = "triage"
    description = "Email triage and priority analysis"
    stages = [
        WorkflowStage.FETCH,
        WorkflowStage.FILTER,
        WorkflowStage.ANALYZE,
        WorkflowStage.CLASSIFY,
        WorkflowStage.REPORT,
    ]

    def run(
        self,
        account: str,
        since: datetime,
        profile: str = "work",
        output: Optional[Path] = None,
        dry_run: bool = False,
        skip_ai: bool = False,
        max_results: int = 500,
        export_data: Optional[Path] = None,
    ) -> WorkflowResult:
        """Execute the triage workflow.

        Args:
            account: Email account to analyze (e.g., user@company.com)
            since: Start date for email search
            profile: Filter profile to use
            output: Optional output file path
            dry_run: If True, skip AI classification
            skip_ai: If True, skip AI classification step

        Returns:
            WorkflowResult with execution details
        """
        result = self._start()

        try:
            # Load profile
            profile_config = get_profile(profile)
            email_filters = EmailFilters(**profile_config.filters.get("email", {}))

            # Stage 1: Fetch emails
            print_info(f"Stage 1: Fetching emails for {account} since {since.date()} (max {max_results})")
            emails = self._fetch_emails(account, since, max_results)
            self._complete_stage(WorkflowStage.FETCH)
            self._update_stats("total_fetched", len(emails))

            if not emails:
                print_info("No emails found for the specified criteria.")
                return self._finish(success=True)

            print_success(f"Fetched {len(emails)} emails")

            # Stage 2: Apply rule-based filters
            print_info("Stage 2: Applying filter rules...")
            kept, filtered = apply_email_filters(emails, email_filters)
            self._complete_stage(WorkflowStage.FILTER)
            self._update_stats("kept_after_filter", len(kept))
            self._update_stats("filtered_out", len(filtered))

            print_success(f"Kept {len(kept)} emails, filtered {len(filtered)} (rules)")

            # Stage 3: Detect response status
            print_info("Stage 3: Analyzing response status...")
            from gmail_mcp.auth import get_gmail_service
            service = get_gmail_service()

            kept = detect_response_status(kept, service, account)
            self._complete_stage(WorkflowStage.ANALYZE)

            # Count by status
            status_counts = self._count_by_status(kept)
            self._update_stats("needs_response", status_counts.get("needs_response", 0))
            self._update_stats("awaiting_reply", status_counts.get("awaiting_reply", 0))
            self._update_stats("replied", status_counts.get("replied", 0))

            print_success(f"Needs response: {status_counts.get('needs_response', 0)}")

            # Stage 4: AI classification (optional)
            if export_data:
                # Export data for Claude Code classification
                print_info("Stage 4: Exporting data for Claude Code classification...")
                needs_triage = [e for e in kept if e.get("response_status") == "needs_response"]

                # Enrich with sender signals before export
                print_info("Enriching with sender signals...")
                from gmail_mcp.ai.sender_signals import enrich_with_sender_signals
                try:
                    from gmail_mcp.auth import get_people_service
                    people_service = get_people_service()
                except Exception as e:
                    print_info(f"Contacts API not available: {e}")
                    people_service = None

                enrich_with_sender_signals(needs_triage, people_service)

                import json
                export_content = {
                    "account": account,
                    "since": since.isoformat(),
                    "generated": datetime.now().isoformat(),
                    "needs_classification": [
                        {
                            "id": e.get("id"),
                            "from": e.get("from"),
                            "to": e.get("to"),
                            "subject": e.get("subject"),
                            "date": e.get("date"),
                            "snippet": e.get("snippet", "")[:200],
                            "sender_quality": e.get("sender_quality", "unknown"),
                        }
                        for e in needs_triage
                    ],
                    "stats": dict(result.stats),
                }

                export_data.parent.mkdir(parents=True, exist_ok=True)
                export_data.write_text(json.dumps(export_content, indent=2), encoding="utf-8")
                print_success(f"Exported {len(needs_triage)} emails to: {export_data}")
                print_info("Ask Claude Code to classify these emails, then re-run with --import-classifications")
                self._complete_stage(WorkflowStage.CLASSIFY)

            elif not dry_run and not skip_ai:
                print_info("Stage 4: AI classification...")
                needs_triage = [e for e in kept if e.get("response_status") == "needs_response"]

                if needs_triage:
                    # Enrich with sender quality signals (contacts + other contacts)
                    print_info("Enriching with sender signals...")
                    from gmail_mcp.ai.sender_signals import enrich_with_sender_signals
                    try:
                        from gmail_mcp.auth import get_people_service
                        people_service = get_people_service()
                    except Exception as e:
                        print_info(f"Contacts API not available: {e}")
                        people_service = None

                    enrich_with_sender_signals(needs_triage, people_service)

                    # Classify with AI
                    from gmail_mcp.ai import classify_emails
                    classify_emails(needs_triage)
                    self._complete_stage(WorkflowStage.CLASSIFY)

                    # Count by priority (5-tier system)
                    priority_counts = self._count_by_priority(needs_triage)
                    self._update_stats("urgent", priority_counts.get("urgent", 0))
                    self._update_stats("important", priority_counts.get("important", 0))
                    self._update_stats("respond", priority_counts.get("respond", 0))
                    self._update_stats("noise", priority_counts.get("noise", 0))
                    self._update_stats("sales", priority_counts.get("sales", 0))

                    print_success(f"Classified: {len(needs_triage)} emails")
                else:
                    print_info("No emails need classification")
                    self._complete_stage(WorkflowStage.CLASSIFY)
            else:
                print_info("Stage 4: Skipped (dry-run or skip-ai)")
                self._complete_stage(WorkflowStage.CLASSIFY)

            # Stage 5: Generate report
            print_info("Stage 5: Generating report...")
            from gwark.workflows.report import generate_triage_report

            config = load_config()
            output_dir = Path(config.defaults.output_directory)
            output_dir.mkdir(parents=True, exist_ok=True)

            if output is None:
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                output = output_dir / f"triage_{account.split('@')[0]}_{timestamp}.md"

            report_content = generate_triage_report(
                account=account,
                since=since,
                kept=kept,
                filtered=filtered,
                stats=result.stats,
            )

            output.write_text(report_content, encoding="utf-8")
            result.output_path = output
            self._complete_stage(WorkflowStage.REPORT)

            print_success(f"Report saved to: {output}")

            return self._finish(success=True)

        except Exception as e:
            print_error(f"Workflow error: {e}")
            return self._finish(success=False, error=str(e))

    def _fetch_emails(self, account: str, since: datetime, max_results: int = 500) -> List[Dict[str, Any]]:
        """Fetch emails for the given account since the specified date."""
        from gmail_mcp.auth import get_gmail_service

        # Build query: emails TO this account, since the date
        after_date = date_to_gmail_query(since)
        query = f"to:{account} after:{after_date}"

        print_info(f"Query: {query}")

        # Get Gmail service
        service = get_gmail_service()

        # Search for messages
        print_info("Searching emails...")
        results = service.users().messages().list(
            userId="me",
            q=query,
            maxResults=min(500, max_results),
        ).execute()

        messages = results.get("messages", [])

        # Handle pagination up to max_results
        while "nextPageToken" in results and len(messages) < max_results:
            remaining = max_results - len(messages)
            results = service.users().messages().list(
                userId="me",
                q=query,
                maxResults=min(500, remaining),
                pageToken=results["nextPageToken"],
            ).execute()
            messages.extend(results.get("messages", []))

        # Trim to max_results
        messages = messages[:max_results]

        if not messages:
            return []

        print_info(f"Found {len(messages)} messages, fetching details...")

        # Fetch email details in parallel
        def fetch_one(msg_id: str) -> Optional[Dict[str, Any]]:
            try:
                email_data = service.users().messages().get(
                    userId="me",
                    id=msg_id,
                    format="full",
                ).execute()
                return extract_email_details(email_data, detail_level="full")
            except Exception:
                return None

        emails = []
        total = len(messages)

        # Sequential fetch for stability (parallel was causing crashes)
        for i, msg in enumerate(messages):
            result = fetch_one(msg["id"])
            if result:
                emails.append(result)
            if (i + 1) % 20 == 0:
                print_info(f"Fetched {i + 1}/{total} emails...")

        # Sort by date (newest first)
        emails.sort(key=lambda x: x.get("date_timestamp", 0), reverse=True)

        return emails

    def _count_by_status(self, emails: List[Dict[str, Any]]) -> Dict[str, int]:
        """Count emails by response status."""
        counts: Dict[str, int] = {}
        for email in emails:
            status = email.get("response_status", "unknown")
            counts[status] = counts.get(status, 0) + 1
        return counts

    def _count_by_priority(self, emails: List[Dict[str, Any]]) -> Dict[str, int]:
        """Count emails by AI priority."""
        counts: Dict[str, int] = {}
        for email in emails:
            priority = email.get("ai_priority", "informational")
            counts[priority] = counts.get(priority, 0) + 1
        return counts
