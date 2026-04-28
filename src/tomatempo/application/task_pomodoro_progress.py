from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, replace
from datetime import datetime
from uuid import UUID

from tomatempo.application.ports import PomodoroSessionRepository, TaskRepository
from tomatempo.domain.entities import PomodoroSession, Task
from tomatempo.domain.value_objects import PomodoroSessionStatus, PomodoroSessionType

FOCUS_POMODORO_MINUTES = 25
COUNTED_FOCUS_STATUSES = {
    PomodoroSessionStatus.COMPLETED,
    PomodoroSessionStatus.INTERRUPTED,
}


class InvalidTaskPomodoroProgressError(ValueError):
    pass


@dataclass(frozen=True)
class TaskPomodoroProgressSummary:
    task: Task
    estimated_pomodoros: int | None
    estimated_minutes: int | None
    actual_focus_minutes: int
    actual_pomodoro_equivalents: float
    remaining_estimated_minutes: int | None
    estimate_exceeded: bool


class UpdateTaskPomodoroEstimate:
    def __init__(self, task_repository: TaskRepository) -> None:
        self.task_repository = task_repository

    def execute(
        self,
        task_id: UUID,
        estimated_pomodoros: int | None,
        updated_at: datetime,
    ) -> Task:
        task = get_task_or_raise(self.task_repository, task_id)
        if estimated_pomodoros is not None and estimated_pomodoros <= 0:
            raise InvalidTaskPomodoroProgressError

        if task.estimated_pomodoros == estimated_pomodoros:
            return task

        return self.task_repository.save(
            replace(
                task,
                estimated_pomodoros=estimated_pomodoros,
                updated_at=updated_at,
            )
        )


class GetTaskPomodoroProgress:
    def __init__(
        self,
        task_repository: TaskRepository,
        pomodoro_session_repository: PomodoroSessionRepository,
    ) -> None:
        self.task_repository = task_repository
        self.pomodoro_session_repository = pomodoro_session_repository

    def execute(self, task_id: UUID) -> TaskPomodoroProgressSummary:
        task = get_task_or_raise(self.task_repository, task_id)
        return build_progress_summary(task, self.pomodoro_session_repository.list())


class ListTaskPomodoroProgress:
    def __init__(
        self,
        task_repository: TaskRepository,
        pomodoro_session_repository: PomodoroSessionRepository,
    ) -> None:
        self.task_repository = task_repository
        self.pomodoro_session_repository = pomodoro_session_repository

    def execute(self, task_ids: list[UUID]) -> list[TaskPomodoroProgressSummary]:
        unique_task_ids = first_seen_unique_ids(task_ids)
        if not unique_task_ids:
            raise InvalidTaskPomodoroProgressError

        sessions = list(self.pomodoro_session_repository.list())
        return [
            build_progress_summary(
                get_task_or_raise(self.task_repository, task_id),
                sessions,
            )
            for task_id in unique_task_ids
        ]


def build_progress_summary(
    task: Task,
    sessions: Iterable[PomodoroSession],
) -> TaskPomodoroProgressSummary:
    actual_focus_minutes = sum(
        session.actual_duration_minutes or 0
        for session in sessions
        if session_counts_toward_task_progress(session, task.id)
    )
    estimated_minutes = estimate_minutes(task.estimated_pomodoros)
    remaining_estimated_minutes = remaining_minutes(
        estimated_minutes,
        actual_focus_minutes,
    )

    return TaskPomodoroProgressSummary(
        task=task,
        estimated_pomodoros=task.estimated_pomodoros,
        estimated_minutes=estimated_minutes,
        actual_focus_minutes=actual_focus_minutes,
        actual_pomodoro_equivalents=actual_focus_minutes / FOCUS_POMODORO_MINUTES,
        remaining_estimated_minutes=remaining_estimated_minutes,
        estimate_exceeded=(
            estimated_minutes is not None and actual_focus_minutes > estimated_minutes
        ),
    )


def get_task_or_raise(task_repository: TaskRepository, task_id: UUID) -> Task:
    task = task_repository.get_by_id(task_id)
    if task is None:
        raise InvalidTaskPomodoroProgressError
    return task


def first_seen_unique_ids(task_ids: list[UUID]) -> list[UUID]:
    seen: set[UUID] = set()
    unique_task_ids: list[UUID] = []
    for task_id in task_ids:
        if task_id in seen:
            continue
        seen.add(task_id)
        unique_task_ids.append(task_id)
    return unique_task_ids


def estimate_minutes(estimated_pomodoros: int | None) -> int | None:
    if estimated_pomodoros is None:
        return None
    return estimated_pomodoros * FOCUS_POMODORO_MINUTES


def remaining_minutes(
    estimated_minutes: int | None,
    actual_focus_minutes: int,
) -> int | None:
    if estimated_minutes is None:
        return None
    return max(0, estimated_minutes - actual_focus_minutes)


def session_counts_toward_task_progress(
    session: PomodoroSession,
    task_id: UUID,
) -> bool:
    return (
        session.task_id == task_id
        and session.type == PomodoroSessionType.FOCUS
        and session.status in COUNTED_FOCUS_STATUSES
        and session.actual_duration_minutes is not None
    )
