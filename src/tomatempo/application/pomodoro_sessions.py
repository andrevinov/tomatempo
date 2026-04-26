from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timedelta
from uuid import UUID

from tomatempo.application.ports import PomodoroSessionRepository, TaskRepository
from tomatempo.domain.entities import PomodoroSession, Task, utc_now
from tomatempo.domain.value_objects import (
    PomodoroSessionStatus,
    PomodoroSessionType,
    TaskStatus,
)

DEFAULT_SESSION_DURATIONS = {
    PomodoroSessionType.FOCUS: 25,
    PomodoroSessionType.SHORT_BREAK: 5,
    PomodoroSessionType.LONG_BREAK: 15,
}


class InvalidPomodoroSessionError(ValueError):
    pass


class StartPomodoroSession:
    def __init__(
        self,
        pomodoro_session_repository: PomodoroSessionRepository,
        task_repository: TaskRepository,
    ) -> None:
        self.pomodoro_session_repository = pomodoro_session_repository
        self.task_repository = task_repository

    def execute(
        self,
        session_type: PomodoroSessionType | str,
        started_at: datetime,
        task_id: UUID | None = None,
        planned_duration_minutes: int | None = None,
    ) -> PomodoroSession:
        validate_aware_datetime(started_at)
        normalized_type = normalize_session_type(session_type)
        duration = normalize_planned_duration(
            normalized_type,
            planned_duration_minutes,
        )

        if self.pomodoro_session_repository.get_active() is not None:
            raise InvalidPomodoroSessionError

        if normalized_type != PomodoroSessionType.FOCUS and task_id is not None:
            raise InvalidPomodoroSessionError

        if task_id is not None:
            task = self.task_repository.get_by_id(task_id)
            if task is None or task.status == TaskStatus.ARCHIVED:
                raise InvalidPomodoroSessionError
            self._move_todo_task_to_doing(task, started_at)

        return self.pomodoro_session_repository.save(
            PomodoroSession(
                type=normalized_type,
                status=PomodoroSessionStatus.RUNNING,
                planned_duration_minutes=duration,
                task_id=task_id,
                started_at=started_at,
                created_at=started_at,
                updated_at=started_at,
            )
        )

    def _move_todo_task_to_doing(self, task: Task, started_at: datetime) -> None:
        if task.status != TaskStatus.TODO:
            return

        self.task_repository.save(
            replace(
                task,
                status=TaskStatus.DOING,
                updated_at=next_time_after(task.updated_at, started_at),
            )
        )


class GetActivePomodoroSession:
    def __init__(
        self,
        pomodoro_session_repository: PomodoroSessionRepository,
    ) -> None:
        self.pomodoro_session_repository = pomodoro_session_repository

    def execute(self) -> PomodoroSession | None:
        return self.pomodoro_session_repository.get_active()


class PausePomodoroSession:
    def __init__(
        self,
        pomodoro_session_repository: PomodoroSessionRepository,
    ) -> None:
        self.pomodoro_session_repository = pomodoro_session_repository

    def execute(self, session_id: UUID, paused_at: datetime) -> PomodoroSession:
        validate_aware_datetime(paused_at)
        session = get_session_or_raise(self.pomodoro_session_repository, session_id)
        if session.status != PomodoroSessionStatus.RUNNING:
            raise InvalidPomodoroSessionError

        return self.pomodoro_session_repository.save(
            replace(
                session,
                status=PomodoroSessionStatus.PAUSED,
                paused_at=paused_at,
                updated_at=next_time_after(session.updated_at, paused_at),
            )
        )


class ResumePomodoroSession:
    def __init__(
        self,
        pomodoro_session_repository: PomodoroSessionRepository,
    ) -> None:
        self.pomodoro_session_repository = pomodoro_session_repository

    def execute(self, session_id: UUID, resumed_at: datetime) -> PomodoroSession:
        validate_aware_datetime(resumed_at)
        session = get_session_or_raise(self.pomodoro_session_repository, session_id)
        if (
            session.status != PomodoroSessionStatus.PAUSED
            or session.paused_at is None
            or resumed_at <= session.paused_at
        ):
            raise InvalidPomodoroSessionError

        pause_seconds = int((resumed_at - session.paused_at).total_seconds())
        return self.pomodoro_session_repository.save(
            replace(
                session,
                status=PomodoroSessionStatus.RUNNING,
                paused_at=None,
                accumulated_pause_seconds=(
                    session.accumulated_pause_seconds + pause_seconds
                ),
                updated_at=next_time_after(session.updated_at, resumed_at),
            )
        )


class CompletePomodoroSession:
    def __init__(
        self,
        pomodoro_session_repository: PomodoroSessionRepository,
    ) -> None:
        self.pomodoro_session_repository = pomodoro_session_repository

    def execute(self, session_id: UUID, ended_at: datetime) -> PomodoroSession:
        session = get_active_session_or_raise(
            self.pomodoro_session_repository,
            session_id,
        )
        validate_end_time(session, ended_at)
        return self.pomodoro_session_repository.save(
            replace(
                session,
                status=PomodoroSessionStatus.COMPLETED,
                ended_at=ended_at,
                actual_duration_minutes=actual_duration_minutes(session, ended_at),
                paused_at=None,
                updated_at=next_time_after(session.updated_at, ended_at),
            )
        )


class InterruptPomodoroSession:
    def __init__(
        self,
        pomodoro_session_repository: PomodoroSessionRepository,
    ) -> None:
        self.pomodoro_session_repository = pomodoro_session_repository

    def execute(
        self,
        session_id: UUID,
        ended_at: datetime,
        reason: str | None = None,
    ) -> PomodoroSession:
        session = get_active_session_or_raise(
            self.pomodoro_session_repository,
            session_id,
        )
        validate_end_time(session, ended_at)
        return self.pomodoro_session_repository.save(
            replace(
                session,
                status=PomodoroSessionStatus.INTERRUPTED,
                ended_at=ended_at,
                actual_duration_minutes=actual_duration_minutes(session, ended_at),
                paused_at=None,
                interruption_reason=normalize_interruption_reason(reason),
                updated_at=next_time_after(session.updated_at, ended_at),
            )
        )


def normalize_session_type(
    session_type: PomodoroSessionType | str,
) -> PomodoroSessionType:
    try:
        if isinstance(session_type, PomodoroSessionType):
            return session_type
        return PomodoroSessionType(session_type)
    except ValueError as exc:
        raise InvalidPomodoroSessionError from exc


def normalize_planned_duration(
    session_type: PomodoroSessionType,
    planned_duration_minutes: int | None,
) -> int:
    duration = (
        DEFAULT_SESSION_DURATIONS[session_type]
        if planned_duration_minutes is None
        else planned_duration_minutes
    )
    if duration <= 0:
        raise InvalidPomodoroSessionError
    return duration


def validate_aware_datetime(value: datetime) -> None:
    if value.tzinfo is None or value.utcoffset() is None:
        raise InvalidPomodoroSessionError


def validate_end_time(session: PomodoroSession, ended_at: datetime) -> None:
    validate_aware_datetime(ended_at)
    if ended_at <= session.started_at:
        raise InvalidPomodoroSessionError


def get_session_or_raise(
    pomodoro_session_repository: PomodoroSessionRepository,
    session_id: UUID,
) -> PomodoroSession:
    session = pomodoro_session_repository.get_by_id(session_id)
    if session is None:
        raise InvalidPomodoroSessionError
    return session


def get_active_session_or_raise(
    pomodoro_session_repository: PomodoroSessionRepository,
    session_id: UUID,
) -> PomodoroSession:
    session = get_session_or_raise(pomodoro_session_repository, session_id)
    if session.status not in {
        PomodoroSessionStatus.RUNNING,
        PomodoroSessionStatus.PAUSED,
    }:
        raise InvalidPomodoroSessionError
    return session


def actual_duration_minutes(session: PomodoroSession, ended_at: datetime) -> int:
    paused_seconds = session.accumulated_pause_seconds
    if session.status == PomodoroSessionStatus.PAUSED and session.paused_at is not None:
        paused_seconds += int((ended_at - session.paused_at).total_seconds())

    elapsed_seconds = int((ended_at - session.started_at).total_seconds())
    return max(0, (elapsed_seconds - paused_seconds) // 60)


def normalize_interruption_reason(reason: str | None) -> str | None:
    if reason is None:
        return None
    normalized_reason = reason.strip()
    return normalized_reason or None


def next_time_after(previous: datetime, candidate: datetime | None = None) -> datetime:
    return max(candidate or utc_now(), previous + timedelta(microseconds=1))
