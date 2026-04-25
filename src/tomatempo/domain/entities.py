from dataclasses import dataclass, field
from datetime import UTC, date, datetime
from uuid import UUID, uuid4

from tomatempo.domain.value_objects import TaskPriority, TaskStatus


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
