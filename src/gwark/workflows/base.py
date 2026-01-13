"""Base workflow classes for gwark."""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional


class WorkflowStage(str, Enum):
    """Workflow execution stages."""

    FETCH = "fetch"
    FILTER = "filter"
    ANALYZE = "analyze"
    CLASSIFY = "classify"
    REPORT = "report"


@dataclass
class WorkflowResult:
    """Result of a workflow execution."""

    success: bool
    workflow_name: str
    started_at: datetime
    completed_at: Optional[datetime] = None
    stages_completed: List[str] = field(default_factory=list)
    stats: Dict[str, Any] = field(default_factory=dict)
    output_path: Optional[Path] = None
    error: Optional[str] = None

    @property
    def duration_seconds(self) -> float:
        """Get execution duration in seconds."""
        if self.completed_at and self.started_at:
            return (self.completed_at - self.started_at).total_seconds()
        return 0.0


class Workflow(ABC):
    """Base class for all workflows."""

    name: str = "base"
    description: str = "Base workflow"
    stages: List[WorkflowStage] = []

    def __init__(self):
        """Initialize workflow."""
        self._result: Optional[WorkflowResult] = None
        self._current_stage: Optional[WorkflowStage] = None

    @abstractmethod
    def run(self, **kwargs) -> WorkflowResult:
        """Execute the workflow.

        Args:
            **kwargs: Workflow-specific parameters

        Returns:
            WorkflowResult with execution details
        """
        pass

    def _start(self) -> WorkflowResult:
        """Initialize workflow result."""
        self._result = WorkflowResult(
            success=False,
            workflow_name=self.name,
            started_at=datetime.now(),
        )
        return self._result

    def _complete_stage(self, stage: WorkflowStage) -> None:
        """Mark a stage as completed."""
        if self._result:
            self._result.stages_completed.append(stage.value)

    def _finish(self, success: bool = True, error: Optional[str] = None) -> WorkflowResult:
        """Finalize workflow result."""
        if self._result:
            self._result.success = success
            self._result.completed_at = datetime.now()
            if error:
                self._result.error = error
        return self._result or WorkflowResult(
            success=False,
            workflow_name=self.name,
            started_at=datetime.now(),
            error=error or "Unknown error",
        )

    def _update_stats(self, key: str, value: Any) -> None:
        """Update workflow statistics."""
        if self._result:
            self._result.stats[key] = value


# Registry for available workflows
_workflows: Dict[str, type] = {}


def register_workflow(workflow_class: type) -> type:
    """Decorator to register a workflow class."""
    _workflows[workflow_class.name] = workflow_class
    return workflow_class


def get_workflow(name: str) -> Optional[type]:
    """Get a registered workflow class by name."""
    return _workflows.get(name)


def list_workflows() -> List[Dict[str, str]]:
    """List all registered workflows."""
    return [
        {"name": cls.name, "description": cls.description}
        for cls in _workflows.values()
    ]
