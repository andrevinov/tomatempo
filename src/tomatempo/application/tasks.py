from dataclasses import replace
from datetime import date
from uuid import UUID

from tomatempo.application.ports import ProjectRepository, TaskRepository
from tomatempo.application.projects import (
    DEFAULT_PROJECT_NAME,
    GetOrCreateProjectByName,
)
from tomatempo.domain.entities import Project, Task, utc_now
from tomatempo.domain.exceptions import (
    DuplicateTaskTitleError,
    InvalidTaskPriorityError,
    InvalidTaskTitleError,
)
from tomatempo.domain.value_objects import TaskPriority, TaskStatus


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
        task = get_task_or_raise(self.task_repository, task_id)
        now = utc_now()
        return self.task_repository.save(
            replace(
                task,
                status=TaskStatus.DONE,
                completed_at=now,
                updated_at=now,
            )
        )


class ReopenTask:
    def __init__(self, task_repository: TaskRepository) -> None:
        self.task_repository = task_repository

    def execute(self, task_id: UUID) -> Task:
        task = get_task_or_raise(self.task_repository, task_id)
        return self.task_repository.save(
            replace(
                task,
                status=TaskStatus.TODO,
                completed_at=None,
                updated_at=utc_now(),
            )
        )


class ArchiveTask:
    def __init__(self, task_repository: TaskRepository) -> None:
        self.task_repository = task_repository

    def execute(self, task_id: UUID) -> Task:
        task = get_task_or_raise(self.task_repository, task_id)
        now = utc_now()
        return self.task_repository.save(
            replace(
                task,
                status=TaskStatus.ARCHIVED,
                archived_at=now,
                updated_at=now,
            )
        )


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
        task = get_task_or_raise(self.task_repository, task_id)

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


def get_task_or_raise(task_repository: TaskRepository, task_id: UUID) -> Task:
    task = task_repository.get_by_id(task_id)
    if task is None:
        raise ValueError("Task not found.")
    return task


def save_task_with_updated_timestamp(
    task_repository: TaskRepository,
    task: Task,
) -> Task:
    return task_repository.save(replace(task, updated_at=utc_now()))
