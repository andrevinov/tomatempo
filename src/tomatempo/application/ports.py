from __future__ import annotations

from collections.abc import Iterable
from typing import TYPE_CHECKING, Protocol
from uuid import UUID

from tomatempo.domain.entities import Project, Tag, Task

if TYPE_CHECKING:
    from tomatempo.domain.entities import PomodoroSession


class ProjectRepository(Protocol):
    """Persistence port for project entities.

    Implementations store and retrieve domain Project objects. Business
    validation, timestamp decisions, and state transitions belong to use cases,
    not to repository implementations.
    """

    def save(self, project: Project) -> Project:
        """Persist a project by its id and return the persisted project."""
        ...

    def get_by_id(self, project_id: UUID) -> Project | None:
        """Return the project with this id, or None when it is not stored."""
        ...

    def get_by_name(self, name: str) -> Project | None:
        """Return the project matching this normalized name, if any.

        Matching is case-insensitive and ignores leading or trailing whitespace.
        Use cases pass already stripped names, but repositories must still
        preserve this lookup behavior for duplicate detection.
        """
        ...

    def list(self) -> Iterable[Project]:
        """Return all stored projects without applying business filters."""
        ...


class TaskRepository(Protocol):
    """Persistence port for task entities.

    Implementations store and retrieve domain Task objects. They must not apply
    task lifecycle rules; use cases decide when a task changes status,
    timestamps, project, priority, due date, estimate, or other fields.
    """

    def save(self, task: Task) -> Task:
        """Persist a task by its id and return the persisted task."""
        ...

    def get_by_id(self, task_id: UUID) -> Task | None:
        """Return the task with this id, or None when it is not stored."""
        ...

    def get_by_project_and_title(self, project_id: UUID, title: str) -> Task | None:
        """Return a task in a project matching this normalized title, if any.

        Matching is scoped to the project, case-insensitive, and ignores leading
        or trailing whitespace. This lookup is used to enforce per-project title
        uniqueness before saving a task or moving it between projects.
        """
        ...

    def list(self) -> Iterable[Task]:
        """Return all stored tasks without applying business filters or sorting."""
        ...


class TagRepository(Protocol):
    """Persistence port for tag entities.

    Implementations store and retrieve domain Tag objects. Tag name
    normalization is defined by application use cases, and repository lookups
    must honor that normalized identity.
    """

    def save(self, tag: Tag) -> Tag:
        """Persist a tag by its id and return the persisted tag."""
        ...

    def get_by_id(self, tag_id: UUID) -> Tag | None:
        """Return the tag with this id, or None when it is not stored."""
        ...

    def get_by_name(self, name: str) -> Tag | None:
        """Return the tag matching this normalized name, if any.

        Matching ignores a leading hash, folds case, trims surrounding
        whitespace, and treats internal whitespace as hyphen-separated words.
        """
        ...

    def list(self) -> Iterable[Tag]:
        """Return all stored tags without applying business filters."""
        ...


class TaskTagRepository(Protocol):
    """Persistence port for task-to-tag relationships."""

    def attach(self, task_id: UUID, tag_id: UUID) -> bool:
        """Attach a tag to a task.

        Return True when a new relationship was created. Return False when the
        relationship already existed.
        """
        ...

    def remove(self, task_id: UUID, tag_id: UUID) -> bool:
        """Remove a tag from a task.

        Return True when an existing relationship was removed. Return False
        when the relationship did not exist.
        """
        ...

    def replace_for_task(self, task_id: UUID, tag_ids: set[UUID]) -> bool:
        """Replace all tag relationships for one task.

        The operation must affect only the selected task. Return True when the
        resulting tag set differs from the previous one, otherwise False.
        """
        ...

    def list_tag_ids_for_task(self, task_id: UUID) -> set[UUID]:
        """Return the ids of tags currently attached to this task."""
        ...


class PomodoroSessionRepository(Protocol):
    """Persistence port for Pomodoro session entities."""

    def save(self, session: PomodoroSession) -> PomodoroSession:
        """Persist a session by its id and return the persisted session."""
        ...

    def get_by_id(self, session_id: UUID) -> PomodoroSession | None:
        """Return the session with this id, or None when it is not stored."""
        ...

    def get_active(self) -> PomodoroSession | None:
        """Return the running or paused session, if one exists.

        The application currently allows at most one active session at a time.
        Completed, interrupted, and planned sessions are not active.
        """
        ...

    def list(self) -> Iterable[PomodoroSession]:
        """Return all stored sessions without applying business filters."""
        ...
