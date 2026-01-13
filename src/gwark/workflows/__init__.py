"""Workflow engine for gwark."""

from gwark.workflows.base import Workflow, WorkflowResult, WorkflowStage

# Import triage workflow to register it
from gwark.workflows import triage  # noqa: F401

__all__ = ["Workflow", "WorkflowResult", "WorkflowStage"]
