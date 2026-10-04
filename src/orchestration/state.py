"""
src/orchestration/state.py: State Machine & Execution Models

Defines standard task execution states and structured audit result models.
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any


class TaskStatus(str, Enum):
    """Execution lifecycle status of an individual task."""
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    SUCCESS = "SUCCESS"
    FAILED = "FAILED"
    SKIPPED = "SKIPPED"
    RETRYING = "RETRYING"


@dataclass
class TaskResult:
    """Execution output contract recording duration, metrics, and errors."""
    task_id: str
    status: TaskStatus
    start_time: datetime
    end_time: datetime | None = None
    duration_ms: float = 0.0
    retry_count: int = 0
    records_processed: int = 0
    error_message: str | None = None
    output_artifacts: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    def mark_completed(self, status: TaskStatus, error: str | None = None) -> None:
        self.end_time = datetime.now()
        self.status = status
        self.duration_ms = round((self.end_time - self.start_time).total_seconds() * 1000, 2)
        self.error_message = error

    def to_dict(self) -> dict[str, Any]:
        return {
            "task_id": self.task_id,
            "status": self.status.value,
            "start_time": self.start_time.isoformat(),
            "end_time": self.end_time.isoformat() if self.end_time else None,
            "duration_ms": self.duration_ms,
            "retry_count": self.retry_count,
            "records_processed": self.records_processed,
            "error_message": self.error_message,
            "output_artifacts": self.output_artifacts,
            "metadata": self.metadata,
        }
