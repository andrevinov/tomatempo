from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import date, datetime, timedelta
from uuid import UUID

from tomatempo.application.ports import (
    ProjectRepository,
    TagRepository,
    TaskRepository,
    TaskTagRepository,
)
from tomatempo.application.tags import GetOrCreateTagByName, unique_normalized_tag_names
from tomatempo.application.tasks import normalize_priority
from tomatempo.domain.entities import Task, utc_now
from tomatempo.domain.exceptions import InvalidTagNameError, InvalidTaskPriorityError
from tomatempo.domain.value_objects import TaskPriority, TaskStatus


class InvalidBatchTaskEditError(ValueError):
    pass


@dataclass(frozen=True)
class BatchTaskOperation:
    kind: str
    value: object = None

    @classmethod
    def update_priority(cls, priority: TaskPriority | str) -> BatchTaskOperation:
        return cls(kind="update_priority", value=priority)

    @classmethod
    def update_due_date(cls, due_date: date | None) -> BatchTaskOperation:
        return cls(kind="update_due_date", value=due_date)

    @classmethod
    def move_to_project(cls, project_id: UUID) -> BatchTaskOperation:
        return cls(kind="move_to_project", value=project_id)

    @classmethod
    def attach_tags(cls, tag_names: list[str]) -> BatchTaskOperation:
        return cls(kind="attach_tags", value=tag_names)

    @classmethod
    def remove_tags(cls, tag_names: list[str]) -> BatchTaskOperation:
        return cls(kind="remove_tags", value=tag_names)

    @classmethod
    def replace_tags(cls, tag_names: list[str]) -> BatchTaskOperation:
        return cls(kind="replace_tags", value=tag_names)

    @classmethod
    def complete(cls) -> BatchTaskOperation:
        return cls(kind="complete")

    @classmethod
    def reopen(cls) -> BatchTaskOperation:
        return cls(kind="reopen")

    @classmethod
    def archive(cls) -> BatchTaskOperation:
        return cls(kind="archive")


@dataclass(frozen=True)
class NormalizedBatchTaskOperation:
    kind: str
    value: object = None


@dataclass(frozen=True)
class BatchTaskError:
    task_id: UUID | None
    code: str
    message: str


@dataclass(frozen=True)
class BatchTaskResult:
    requested_count: int
    changed_count: int
    unchanged_count: int
    error_count: int
    changed_tasks: list[Task]
    errors: list[BatchTaskError]


class BatchEditTasks:
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
        task_ids: list[UUID],
        operation: BatchTaskOperation,
        include_archived: bool = False,
    ) -> BatchTaskResult:
        selection = normalize_batch_task_selection(task_ids)
        normalized_operation = self._normalize_operation(operation)

        changed_tasks: list[Task] = []
        errors: list[BatchTaskError] = []
        unchanged_count = 0

        for task_id in selection:
            task = self.task_repository.get_by_id(task_id)
            if task is None:
                errors.append(
                    BatchTaskError(
                        task_id=task_id,
                        code="missing_task",
                        message="Task not found.",
                    )
                )
                continue

            if task.status == TaskStatus.ARCHIVED and not include_archived:
                errors.append(
                    BatchTaskError(
                        task_id=task.id,
                        code="archived_task",
                        message="Archived task cannot be edited.",
                    )
                )
                continue

            updated_task, error = self._apply_operation(task, normalized_operation)
            if error is not None:
                errors.append(error)
                continue
            if updated_task is None:
                unchanged_count += 1
                continue

            changed_tasks.append(updated_task)

        return BatchTaskResult(
            requested_count=len(selection),
            changed_count=len(changed_tasks),
            unchanged_count=unchanged_count,
            error_count=len(errors),
            changed_tasks=changed_tasks,
            errors=errors,
        )

    def _normalize_operation(
        self,
        operation: BatchTaskOperation,
    ) -> NormalizedBatchTaskOperation:
        if operation.kind == "update_priority":
            try:
                return NormalizedBatchTaskOperation(
                    kind=operation.kind,
                    value=normalize_priority_value(operation.value),
                )
            except InvalidTaskPriorityError as exc:
                raise InvalidBatchTaskEditError from exc

        if operation.kind == "move_to_project":
            project_id = normalize_project_id(operation.value)
            if self.project_repository.get_by_id(project_id) is None:
                raise InvalidBatchTaskEditError
            return NormalizedBatchTaskOperation(kind=operation.kind, value=project_id)

        if operation.kind in {"attach_tags", "remove_tags", "replace_tags"}:
            try:
                return NormalizedBatchTaskOperation(
                    kind=operation.kind,
                    value=normalize_tag_list(operation.value),
                )
            except InvalidTagNameError as exc:
                raise InvalidBatchTaskEditError from exc

        if operation.kind in {
            "update_due_date",
            "complete",
            "reopen",
            "archive",
        }:
            return NormalizedBatchTaskOperation(
                kind=operation.kind,
                value=operation.value,
            )

        raise InvalidBatchTaskEditError

    def _apply_operation(
        self,
        task: Task,
        operation: NormalizedBatchTaskOperation,
    ) -> tuple[Task | None, BatchTaskError | None]:
        if operation.kind == "update_priority":
            return self._update_priority(
                task,
                normalize_priority_value(operation.value),
            )
        if operation.kind == "update_due_date":
            return self._update_due_date(task, normalize_due_date(operation.value))
        if operation.kind == "move_to_project":
            return self._move_to_project(task, normalize_project_id(operation.value))
        if operation.kind == "attach_tags":
            return self._attach_tags(task, normalize_tag_list(operation.value))
        if operation.kind == "remove_tags":
            return self._remove_tags(task, normalize_tag_list(operation.value))
        if operation.kind == "replace_tags":
            return self._replace_tags(task, normalize_tag_list(operation.value))
        if operation.kind == "complete":
            return self._complete(task)
        if operation.kind == "reopen":
            return self._reopen(task)
        if operation.kind == "archive":
            return self._archive(task)

        raise InvalidBatchTaskEditError

    def _update_priority(
        self,
        task: Task,
        priority: TaskPriority,
    ) -> tuple[Task | None, None]:
        if task.priority == priority:
            return None, None

        return self._save_changed_task(replace(task, priority=priority)), None

    def _update_due_date(
        self,
        task: Task,
        due_date: date | None,
    ) -> tuple[Task | None, None]:
        if task.due_date == due_date:
            return None, None

        return self._save_changed_task(replace(task, due_date=due_date)), None

    def _move_to_project(
        self,
        task: Task,
        project_id: UUID,
    ) -> tuple[Task | None, BatchTaskError | None]:
        if task.project_id == project_id:
            return None, None

        existing_task = self.task_repository.get_by_project_and_title(
            project_id,
            task.title,
        )
        if existing_task is not None and existing_task.id != task.id:
            return None, BatchTaskError(
                task_id=task.id,
                code="duplicate_task_title",
                message="Task title already exists in the target project.",
            )

        return self._save_changed_task(replace(task, project_id=project_id)), None

    def _attach_tags(
        self,
        task: Task,
        tag_names: list[str],
    ) -> tuple[Task | None, None]:
        changed = False
        for tag_name in tag_names:
            tag = GetOrCreateTagByName(self.tag_repository).execute(tag_name)
            changed = self.task_tag_repository.attach(task.id, tag.id) or changed

        if not changed:
            return None, None

        return self._touch_task(task), None

    def _remove_tags(
        self,
        task: Task,
        tag_names: list[str],
    ) -> tuple[Task | None, None]:
        changed = False
        for tag_name in tag_names:
            tag = self.tag_repository.get_by_name(tag_name)
            if tag is None:
                continue
            changed = self.task_tag_repository.remove(task.id, tag.id) or changed

        if not changed:
            return None, None

        return self._touch_task(task), None

    def _replace_tags(
        self,
        task: Task,
        tag_names: list[str],
    ) -> tuple[Task | None, None]:
        tags = [
            GetOrCreateTagByName(self.tag_repository).execute(tag_name)
            for tag_name in tag_names
        ]
        changed = self.task_tag_repository.replace_for_task(
            task.id,
            {tag.id for tag in tags},
        )
        if not changed:
            return None, None

        return self._touch_task(task), None

    def _complete(self, task: Task) -> tuple[Task | None, None]:
        if task.status == TaskStatus.DONE:
            return None, None

        now = next_update_time(task)
        return self.task_repository.save(
            replace(
                task,
                status=TaskStatus.DONE,
                completed_at=now,
                updated_at=now,
            )
        ), None

    def _reopen(self, task: Task) -> tuple[Task | None, None]:
        if task.status == TaskStatus.TODO:
            return None, None

        return self._save_changed_task(
            replace(
                task,
                status=TaskStatus.TODO,
                completed_at=None,
            )
        ), None

    def _archive(self, task: Task) -> tuple[Task | None, None]:
        if task.status == TaskStatus.ARCHIVED:
            return None, None

        now = next_update_time(task)
        return self.task_repository.save(
            replace(
                task,
                status=TaskStatus.ARCHIVED,
                archived_at=now,
                updated_at=now,
            )
        ), None

    def _save_changed_task(self, task: Task) -> Task:
        return self.task_repository.save(
            replace(task, updated_at=next_update_time(task))
        )

    def _touch_task(self, task: Task) -> Task:
        return self.task_repository.save(
            replace(task, updated_at=next_update_time(task))
        )


def normalize_batch_task_selection(task_ids: list[UUID]) -> list[UUID]:
    if not task_ids:
        raise InvalidBatchTaskEditError

    selection: list[UUID] = []
    seen: set[UUID] = set()
    for task_id in task_ids:
        if task_id not in seen:
            selection.append(task_id)
            seen.add(task_id)
    return selection


def normalize_priority_value(value: object) -> TaskPriority:
    if not isinstance(value, TaskPriority | str):
        raise InvalidBatchTaskEditError
    return normalize_priority(value)


def normalize_project_id(value: object) -> UUID:
    if not isinstance(value, UUID):
        raise InvalidBatchTaskEditError
    return value


def normalize_due_date(value: object) -> date | None:
    if value is None or isinstance(value, date):
        return value
    raise InvalidBatchTaskEditError


def normalize_tag_list(value: object) -> list[str]:
    if not isinstance(value, list):
        raise InvalidBatchTaskEditError

    if not all(isinstance(tag_name, str) for tag_name in value):
        raise InvalidBatchTaskEditError

    return unique_normalized_tag_names(value)


def next_update_time(task: Task) -> datetime:
    return max(utc_now(), task.updated_at + timedelta(microseconds=1))
