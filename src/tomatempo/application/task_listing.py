from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from uuid import UUID

from tomatempo.application.ports import (
    ProjectRepository,
    TagRepository,
    TaskRepository,
    TaskTagRepository,
)
from tomatempo.application.tags import ListTaskTags, unique_normalized_tag_names
from tomatempo.domain.entities import Project, Tag, Task
from tomatempo.domain.value_objects import TaskPriority, TaskStatus


class InvalidTaskListFilterError(ValueError):
    pass


@dataclass(frozen=True)
class TaskListFilters:
    project_id: UUID | None = None
    statuses: list[TaskStatus | str] | None = None
    tag_names: list[str] | None = None
    priorities: list[TaskPriority | str] | None = None
    due_on: date | None = None
    due_before: date | None = None
    due_after: date | None = None
    search: str | None = None
    include_archived: bool = False


@dataclass(frozen=True)
class TaskSort:
    key: str = "default"
    direction: str = "asc"


@dataclass(frozen=True)
class TaskListItem:
    task: Task
    project: Project
    tags: list[Tag]


@dataclass(frozen=True)
class TaskListResult:
    items: list[TaskListItem]
    total_count: int


@dataclass(frozen=True)
class NormalizedTaskListFilters:
    project_id: UUID | None = None
    statuses: list[TaskStatus] | None = None
    tag_names: list[str] | None = None
    priorities: list[TaskPriority] | None = None
    due_on: date | None = None
    due_before: date | None = None
    due_after: date | None = None
    search: str | None = None
    include_archived: bool = False


@dataclass(frozen=True)
class NormalizedTaskSort:
    key: str
    direction: str


class BuildTaskListItem:
    def __init__(
        self,
        project_repository: ProjectRepository,
        tag_repository: TagRepository,
        task_tag_repository: TaskTagRepository,
    ) -> None:
        self.project_repository = project_repository
        self.tag_repository = tag_repository
        self.task_tag_repository = task_tag_repository

    def execute(self, task: Task) -> TaskListItem:
        project = self.project_repository.get_by_id(task.project_id)
        if project is None:
            raise ValueError("Project not found.")

        tags = ListTaskTags(self.tag_repository, self.task_tag_repository).execute(
            task.id
        )
        return TaskListItem(task=task, project=project, tags=tags)


class ListTasks:
    def __init__(
        self,
        task_repository: TaskRepository,
        project_repository: ProjectRepository,
        tag_repository: TagRepository,
        task_tag_repository: TaskTagRepository,
    ) -> None:
        self.task_repository = task_repository
        self.project_repository = project_repository
        self.tag_repository = tag_repository
        self.task_tag_repository = task_tag_repository

    def execute(
        self,
        filters: TaskListFilters | None = None,
        sort: TaskSort | None = None,
    ) -> TaskListResult:
        normalized_filters = normalize_task_list_filters(filters or TaskListFilters())
        normalized_sort = normalize_task_sort(sort or TaskSort())

        tasks = [
            task
            for task in self.task_repository.list()
            if self._matches_filters(task, normalized_filters)
        ]
        sorted_tasks = sort_tasks(tasks, normalized_sort)
        item_builder = BuildTaskListItem(
            self.project_repository,
            self.tag_repository,
            self.task_tag_repository,
        )
        items = [item_builder.execute(task) for task in sorted_tasks]
        return TaskListResult(items=items, total_count=len(items))

    def _matches_filters(
        self,
        task: Task,
        filters: NormalizedTaskListFilters,
    ) -> bool:
        if not filters.include_archived and filters.statuses is None:
            if task.status == TaskStatus.ARCHIVED:
                return False

        if filters.statuses is not None and task.status not in filters.statuses:
            return False

        if filters.project_id is not None and task.project_id != filters.project_id:
            return False

        if filters.priorities is not None and task.priority not in filters.priorities:
            return False

        if not _matches_due_date(task, filters):
            return False

        if not _matches_search(task, filters.search):
            return False

        return self._matches_tags(task, filters.tag_names)

    def _matches_tags(self, task: Task, tag_names: list[str] | None) -> bool:
        if tag_names is None:
            return True

        requested_tag_ids = {
            tag.id
            for name in tag_names
            if (tag := self.tag_repository.get_by_name(name))
        }
        if len(requested_tag_ids) != len(tag_names):
            return False

        task_tag_ids = self.task_tag_repository.list_tag_ids_for_task(task.id)
        return requested_tag_ids.issubset(task_tag_ids)


def normalize_task_list_filters(
    filters: TaskListFilters,
) -> NormalizedTaskListFilters:
    return NormalizedTaskListFilters(
        project_id=filters.project_id,
        statuses=normalize_statuses(filters.statuses),
        tag_names=normalize_tag_names(filters.tag_names),
        priorities=normalize_priorities(filters.priorities),
        due_on=filters.due_on,
        due_before=filters.due_before,
        due_after=filters.due_after,
        search=normalize_search(filters.search),
        include_archived=filters.include_archived,
    )


def normalize_statuses(
    statuses: list[TaskStatus | str] | None,
) -> list[TaskStatus] | None:
    if statuses is None:
        return None

    try:
        return [
            status if isinstance(status, TaskStatus) else TaskStatus(status)
            for status in statuses
        ]
    except ValueError as exc:
        raise InvalidTaskListFilterError from exc


def normalize_priorities(
    priorities: list[TaskPriority | str] | None,
) -> list[TaskPriority] | None:
    if priorities is None:
        return None

    try:
        return [
            priority if isinstance(priority, TaskPriority) else TaskPriority(priority)
            for priority in priorities
        ]
    except ValueError as exc:
        raise InvalidTaskListFilterError from exc


def normalize_tag_names(tag_names: list[str] | None) -> list[str] | None:
    if tag_names is None:
        return None
    return unique_normalized_tag_names(tag_names)


def normalize_search(search: str | None) -> str | None:
    if search is None:
        return None

    normalized_search = search.strip().casefold()
    return normalized_search or None


def normalize_task_sort(sort: TaskSort) -> NormalizedTaskSort:
    allowed_keys = {
        "default",
        "title",
        "created_at",
        "updated_at",
        "due_date",
        "priority",
    }
    allowed_directions = {"asc", "desc"}

    if sort.key not in allowed_keys or sort.direction not in allowed_directions:
        raise InvalidTaskListFilterError

    return NormalizedTaskSort(key=sort.key, direction=sort.direction)


def _matches_due_date(task: Task, filters: NormalizedTaskListFilters) -> bool:
    has_due_filter = (
        filters.due_on is not None
        or filters.due_before is not None
        or filters.due_after is not None
    )
    if not has_due_filter:
        return True

    if task.due_date is None:
        return False

    if filters.due_on is not None and task.due_date != filters.due_on:
        return False
    if filters.due_before is not None and task.due_date >= filters.due_before:
        return False
    return not (filters.due_after is not None and task.due_date <= filters.due_after)


def _matches_search(task: Task, search: str | None) -> bool:
    if search is None:
        return True

    return search in task.title.casefold() or search in (
        task.description or ""
    ).casefold()


def sort_tasks(tasks: list[Task], sort: NormalizedTaskSort) -> list[Task]:
    if sort.key == "default":
        return sorted(tasks, key=default_sort_key, reverse=sort.direction == "desc")

    return sorted(
        tasks,
        key=lambda task: sort_key_for_task(task, sort.key),
        reverse=sort.direction == "desc",
    )


def default_sort_key(task: Task) -> tuple[bool, int, datetime, str]:
    return (
        task.sort_order is None,
        task.sort_order or 0,
        task.created_at,
        str(task.id),
    )


def sort_key_for_task(
    task: Task,
    key: str,
) -> tuple[object, ...]:
    if key == "title":
        return (task.title.casefold(), str(task.id))
    if key == "created_at":
        return (task.created_at, str(task.id))
    if key == "updated_at":
        return (task.updated_at, str(task.id))
    if key == "due_date":
        return (task.due_date is None, task.due_date or date.max, str(task.id))
    if key == "priority":
        return (priority_rank(task.priority), str(task.id))

    raise InvalidTaskListFilterError


def priority_rank(priority: TaskPriority) -> int:
    return {
        TaskPriority.NONE: 0,
        TaskPriority.LOW: 1,
        TaskPriority.MEDIUM: 2,
        TaskPriority.HIGH: 3,
    }[priority]
