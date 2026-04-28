from dataclasses import dataclass, field
from datetime import UTC, date, datetime
from uuid import UUID, uuid4

from tomatempo.domain.value_objects import (
    PomodoroSessionStatus,
    PomodoroSessionType,
    TaskPriority,
    TaskStatus,
)


def utc_now() -> datetime:
    return datetime.now(UTC)


@dataclass(frozen=True)
class Project:
    name: str
    id: UUID = field(default_factory=uuid4)
    created_at: datetime = field(default_factory=utc_now)
    updated_at: datetime = field(default_factory=utc_now)
    description: str | None = None
    is_archived: bool = False


@dataclass(frozen=True)
class Tag:
    name: str
    id: UUID = field(default_factory=uuid4)
    created_at: datetime = field(default_factory=utc_now)
    updated_at: datetime = field(default_factory=utc_now)
    description: str | None = None
    is_archived: bool = False


@dataclass(frozen=True)
class Task:
    project_id: UUID
    title: str
    id: UUID = field(default_factory=uuid4)
    status: TaskStatus = TaskStatus.TODO
    created_at: datetime = field(default_factory=utc_now)
    updated_at: datetime = field(default_factory=utc_now)
    description: str | None = None
    priority: TaskPriority = TaskPriority.NONE
    due_date: date | None = None
    completed_at: datetime | None = None
    archived_at: datetime | None = None
    sort_order: int | None = None
    estimated_pomodoros: int | None = None


@dataclass(frozen=True)
class PomodoroSession:
    type: PomodoroSessionType
    status: PomodoroSessionStatus
    planned_duration_minutes: int
    started_at: datetime
    id: UUID = field(default_factory=uuid4)
    created_at: datetime = field(default_factory=utc_now)
    updated_at: datetime = field(default_factory=utc_now)
    actual_duration_minutes: int | None = None
    task_id: UUID | None = None
    paused_at: datetime | None = None
    accumulated_pause_seconds: int = 0
    ended_at: datetime | None = None
    interruption_reason: str | None = None
