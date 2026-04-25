from collections.abc import Iterable
from dataclasses import replace
from datetime import date
from typing import Protocol
from uuid import UUID

from tomatempo.domain.entities import Project, Tag, Task, utc_now
from tomatempo.domain.exceptions import (
    DuplicateProjectNameError,
    DuplicateTagNameError,
    DuplicateTaskTitleError,
    InvalidProjectNameError,
    InvalidTagNameError,
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


class TagRepository(Protocol):
    def save(self, tag: Tag) -> Tag: ...

    def get_by_id(self, tag_id: UUID) -> Tag | None: ...

    def get_by_name(self, name: str) -> Tag | None: ...

    def list(self) -> Iterable[Tag]: ...


class TaskTagRepository(Protocol):
    def attach(self, task_id: UUID, tag_id: UUID) -> bool: ...

    def remove(self, task_id: UUID, tag_id: UUID) -> bool: ...

    def replace_for_task(self, task_id: UUID, tag_ids: set[UUID]) -> bool: ...

    def list_tag_ids_for_task(self, task_id: UUID) -> set[UUID]: ...


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


def normalize_required_tag_name(name: str) -> str:
    without_hash = name.strip().removeprefix("#").strip()
    if not without_hash:
        raise InvalidTagNameError
    return "-".join(without_hash.split()).casefold()


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


class CreateTag:
    def __init__(self, tag_repository: TagRepository) -> None:
        self.tag_repository = tag_repository

    def execute(self, name: str) -> Tag:
        normalized_name = normalize_required_tag_name(name)
        if self.tag_repository.get_by_name(normalized_name) is not None:
            raise DuplicateTagNameError

        return self.tag_repository.save(Tag(name=normalized_name))


class GetOrCreateTagByName:
    def __init__(self, tag_repository: TagRepository) -> None:
        self.tag_repository = tag_repository

    def execute(self, name: str) -> Tag:
        normalized_name = normalize_required_tag_name(name)
        existing_tag = self.tag_repository.get_by_name(normalized_name)
        if existing_tag is not None:
            return existing_tag

        return self.tag_repository.save(Tag(name=normalized_name))


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


class AttachTagToTask:
    def __init__(
        self,
        task_repository: TaskRepository,
        tag_repository: TagRepository,
        task_tag_repository: TaskTagRepository,
    ) -> None:
        self.task_repository = task_repository
        self.tag_repository = tag_repository
        self.task_tag_repository = task_tag_repository

    def execute(self, task_id: UUID, tag_name: str) -> Task:
        task = get_task_or_raise(self.task_repository, task_id)
        tag = GetOrCreateTagByName(self.tag_repository).execute(tag_name)
        attached = self.task_tag_repository.attach(task.id, tag.id)
        if not attached:
            return task

        return save_task_with_updated_timestamp(self.task_repository, task)


class AttachTagsToTask:
    def __init__(
        self,
        task_repository: TaskRepository,
        tag_repository: TagRepository,
        task_tag_repository: TaskTagRepository,
    ) -> None:
        self.task_repository = task_repository
        self.tag_repository = tag_repository
        self.task_tag_repository = task_tag_repository

    def execute(self, task_id: UUID, tag_names: Iterable[str]) -> Task:
        task = get_task_or_raise(self.task_repository, task_id)
        changed = False
        for tag_name in unique_normalized_tag_names(tag_names):
            tag = GetOrCreateTagByName(self.tag_repository).execute(tag_name)
            changed = self.task_tag_repository.attach(task.id, tag.id) or changed

        if not changed:
            return task

        return save_task_with_updated_timestamp(self.task_repository, task)


class RemoveTagFromTask:
    def __init__(
        self,
        task_repository: TaskRepository,
        tag_repository: TagRepository,
        task_tag_repository: TaskTagRepository,
    ) -> None:
        self.task_repository = task_repository
        self.tag_repository = tag_repository
        self.task_tag_repository = task_tag_repository

    def execute(self, task_id: UUID, tag_name: str) -> Task:
        task = get_task_or_raise(self.task_repository, task_id)
        tag = self.tag_repository.get_by_name(normalize_required_tag_name(tag_name))
        if tag is None:
            return task

        removed = self.task_tag_repository.remove(task.id, tag.id)
        if not removed:
            return task

        return save_task_with_updated_timestamp(self.task_repository, task)


class ReplaceTaskTags:
    def __init__(
        self,
        task_repository: TaskRepository,
        tag_repository: TagRepository,
        task_tag_repository: TaskTagRepository,
    ) -> None:
        self.task_repository = task_repository
        self.tag_repository = tag_repository
        self.task_tag_repository = task_tag_repository

    def execute(self, task_id: UUID, tag_names: Iterable[str]) -> Task:
        task = get_task_or_raise(self.task_repository, task_id)
        tags = [
            GetOrCreateTagByName(self.tag_repository).execute(tag_name)
            for tag_name in unique_normalized_tag_names(tag_names)
        ]
        changed = self.task_tag_repository.replace_for_task(
            task.id,
            {tag.id for tag in tags},
        )
        if not changed:
            return task

        return save_task_with_updated_timestamp(self.task_repository, task)


class ListTaskTags:
    def __init__(
        self,
        tag_repository: TagRepository,
        task_tag_repository: TaskTagRepository,
    ) -> None:
        self.tag_repository = tag_repository
        self.task_tag_repository = task_tag_repository

    def execute(self, task_id: UUID) -> list[Tag]:
        tags = [
            tag
            for tag_id in self.task_tag_repository.list_tag_ids_for_task(task_id)
            if (tag := self.tag_repository.get_by_id(tag_id)) is not None
        ]
        return sorted(tags, key=lambda tag: tag.name)


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
        return get_task_or_raise(self.task_repository, task_id)


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
        return get_task_or_raise(self.task_repository, task_id)


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
        return get_task_or_raise(self.task_repository, task_id)


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
        return get_task_or_raise(self.task_repository, task_id)


def unique_normalized_tag_names(tag_names: Iterable[str]) -> list[str]:
    names: list[str] = []
    seen: set[str] = set()
    for tag_name in tag_names:
        normalized_name = normalize_required_tag_name(tag_name)
        if normalized_name not in seen:
            names.append(normalized_name)
            seen.add(normalized_name)
    return names


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
