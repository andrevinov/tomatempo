from collections.abc import Iterable
from dataclasses import replace
from datetime import date
from typing import Protocol
from uuid import UUID

from tomatempo.domain.entities import Project, Task, utc_now
from tomatempo.domain.exceptions import (
    DuplicateProjectNameError,
    DuplicateTaskTitleError,
    InvalidProjectNameError,
    InvalidTaskPriorityError,
    InvalidTaskTitleError,
)
from tomatempo.domain.value_objects import TaskPriority, TaskStatus

DEFAULT_PROJECT_NAME = "Inbox"


class ProjectRepository(Protocol):
    def save(self, project: Project) -> Project: ...

    def get_by_id(self, project_id: UUID) -> Project | None: ...

    def get_by_name(self, name: str) -> Project | None: ...

    def list(self) -> Iterable[Project]: ...


class TaskRepository(Protocol):
    def save(self, task: Task) -> Task: ...

    def get_by_id(self, task_id: UUID) -> Task | None: ...

    def get_by_project_and_title(self, project_id: UUID, title: str) -> Task | None: ...

    def list(self) -> Iterable[Task]: ...


def normalize_required_project_name(name: str) -> str:
    normalized_name = name.strip()
    if not normalized_name:
        raise InvalidProjectNameError
    return normalized_name


def normalize_required_task_title(title: str) -> str:
    normalized_title = title.strip()
    if not normalized_title:
        raise InvalidTaskTitleError
    return normalized_title


def normalize_priority(priority: TaskPriority | str) -> TaskPriority:
    try:
        if isinstance(priority, TaskPriority):
            return priority
        return TaskPriority(priority)
    except ValueError as exc:
        raise InvalidTaskPriorityError from exc


class CreateProject:
    def __init__(self, project_repository: ProjectRepository) -> None:
        self.project_repository = project_repository

    def execute(self, name: str) -> Project:
        normalized_name = normalize_required_project_name(name)
        if self.project_repository.get_by_name(normalized_name) is not None:
            raise DuplicateProjectNameError

        return self.project_repository.save(Project(name=normalized_name))


class GetOrCreateProjectByName:
    def __init__(self, project_repository: ProjectRepository) -> None:
        self.project_repository = project_repository

    def execute(self, name: str) -> Project:
        normalized_name = normalize_required_project_name(name)
        existing_project = self.project_repository.get_by_name(normalized_name)
        if existing_project is not None:
            return existing_project

        return self.project_repository.save(Project(name=normalized_name))


class CreateTask:
    def __init__(
        self,
        task_repository: TaskRepository,
        project_repository: ProjectRepository,
    ) -> None:
        self.task_repository = task_repository
        self.project_repository = project_repository

    def execute(self, title: str, project_id: UUID | None = None) -> Task:
        normalized_title = normalize_required_task_title(title)
        project = self._resolve_project(project_id)

        if (
            self.task_repository.get_by_project_and_title(project.id, normalized_title)
            is not None
        ):
            raise DuplicateTaskTitleError

        return self.task_repository.save(
            Task(title=normalized_title, project_id=project.id)
        )

    def _resolve_project(self, project_id: UUID | None) -> Project:
        if project_id is None:
            return GetOrCreateProjectByName(self.project_repository).execute(
                DEFAULT_PROJECT_NAME
            )

        project = self.project_repository.get_by_id(project_id)
        if project is None:
            raise ValueError("Project not found.")
        return project


class CompleteTask:
    def __init__(self, task_repository: TaskRepository) -> None:
        self.task_repository = task_repository

    def execute(self, task_id: UUID) -> Task:
        task = self._get_task(task_id)
        now = utc_now()
        return self.task_repository.save(
            replace(
                task,
                status=TaskStatus.DONE,
                completed_at=now,
                updated_at=now,
            )
        )

    def _get_task(self, task_id: UUID) -> Task:
        task = self.task_repository.get_by_id(task_id)
        if task is None:
            raise ValueError("Task not found.")
        return task


class ReopenTask:
    def __init__(self, task_repository: TaskRepository) -> None:
        self.task_repository = task_repository

    def execute(self, task_id: UUID) -> Task:
        task = self._get_task(task_id)
        return self.task_repository.save(
            replace(
                task,
                status=TaskStatus.TODO,
                completed_at=None,
                updated_at=utc_now(),
            )
        )

    def _get_task(self, task_id: UUID) -> Task:
        task = self.task_repository.get_by_id(task_id)
        if task is None:
            raise ValueError("Task not found.")
        return task


class ArchiveTask:
    def __init__(self, task_repository: TaskRepository) -> None:
        self.task_repository = task_repository

    def execute(self, task_id: UUID) -> Task:
        task = self._get_task(task_id)
        now = utc_now()
        return self.task_repository.save(
            replace(
                task,
                status=TaskStatus.ARCHIVED,
                archived_at=now,
                updated_at=now,
            )
        )

    def _get_task(self, task_id: UUID) -> Task:
        task = self.task_repository.get_by_id(task_id)
        if task is None:
            raise ValueError("Task not found.")
        return task


class UpdateTask:
    def __init__(
        self,
        task_repository: TaskRepository,
        project_repository: ProjectRepository,
    ) -> None:
        self.task_repository = task_repository
        self.project_repository = project_repository

    def execute(
        self,
        task_id: UUID,
        title: str | None = None,
        description: str | None = None,
        project_id: UUID | None = None,
        priority: TaskPriority | str | None = None,
        due_date: date | None = None,
    ) -> Task:
        task = self._get_task(task_id)

        updated_title = task.title
        updated_description = task.description
        updated_project_id = task.project_id
        updated_priority = task.priority
        updated_due_date = task.due_date

        if title is not None:
            updated_title = normalize_required_task_title(title)
        if description is not None:
            updated_description = description
        if project_id is not None:
            if self.project_repository.get_by_id(project_id) is None:
                raise ValueError("Project not found.")
            updated_project_id = project_id
        if priority is not None:
            updated_priority = normalize_priority(priority)
        if due_date is not None:
            updated_due_date = due_date

        return self.task_repository.save(
            replace(
                task,
                title=updated_title,
                description=updated_description,
                project_id=updated_project_id,
                priority=updated_priority,
                due_date=updated_due_date,
                updated_at=utc_now(),
            )
        )

    def _get_task(self, task_id: UUID) -> Task:
        task = self.task_repository.get_by_id(task_id)
        if task is None:
            raise ValueError("Task not found.")
        return task
