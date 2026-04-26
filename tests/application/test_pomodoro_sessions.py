from __future__ import annotations

from collections.abc import Iterable
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import pytest

from tomatempo.application.use_cases import (
    CompletePomodoroSession,
    GetActivePomodoroSession,
    InterruptPomodoroSession,
    InvalidPomodoroSessionError,
    PausePomodoroSession,
    ResumePomodoroSession,
    StartPomodoroSession,
)
from tomatempo.domain.entities import PomodoroSession, Task
from tomatempo.domain.value_objects import (
    PomodoroSessionStatus,
    PomodoroSessionType,
    TaskStatus,
)

from .conftest import InMemoryTaskRepository, create_project, create_task

START_TIME = datetime(2026, 5, 1, 9, 0, tzinfo=UTC)


class InMemoryPomodoroSessionRepository:
    def __init__(self) -> None:
        self.sessions: dict[UUID, PomodoroSession] = {}

    def save(self, session: PomodoroSession) -> PomodoroSession:
        self.sessions[session.id] = session
        return session

    def get_by_id(self, session_id: UUID) -> PomodoroSession | None:
        return self.sessions.get(session_id)

    def get_active(self) -> PomodoroSession | None:
        return next(
            (
                session
                for session in self.sessions.values()
                if session.status
                in {PomodoroSessionStatus.RUNNING, PomodoroSessionStatus.PAUSED}
            ),
            None,
        )

    def list(self) -> Iterable[PomodoroSession]:
        return self.sessions.values()


@pytest.fixture
def pomodoro_session_repository() -> InMemoryPomodoroSessionRepository:
    return InMemoryPomodoroSessionRepository()


def start_session(
    pomodoro_session_repository: InMemoryPomodoroSessionRepository,
    task_repository: InMemoryTaskRepository,
    session_type: PomodoroSessionType | str = PomodoroSessionType.FOCUS,
    started_at: datetime = START_TIME,
    task_id: UUID | None = None,
    planned_duration_minutes: int | None = None,
) -> PomodoroSession:
    return StartPomodoroSession(
        pomodoro_session_repository,
        task_repository,
    ).execute(
        session_type=session_type,
        started_at=started_at,
        task_id=task_id,
        planned_duration_minutes=planned_duration_minutes,
    )


def complete_session(
    pomodoro_session_repository: InMemoryPomodoroSessionRepository,
    session_id: UUID,
    ended_at: datetime,
) -> PomodoroSession:
    return CompletePomodoroSession(pomodoro_session_repository).execute(
        session_id,
        ended_at=ended_at,
    )


def pause_session(
    pomodoro_session_repository: InMemoryPomodoroSessionRepository,
    session_id: UUID,
    paused_at: datetime,
) -> PomodoroSession:
    return PausePomodoroSession(pomodoro_session_repository).execute(
        session_id,
        paused_at=paused_at,
    )


def resume_session(
    pomodoro_session_repository: InMemoryPomodoroSessionRepository,
    session_id: UUID,
    resumed_at: datetime,
) -> PomodoroSession:
    return ResumePomodoroSession(pomodoro_session_repository).execute(
        session_id,
        resumed_at=resumed_at,
    )


def interrupt_session(
    pomodoro_session_repository: InMemoryPomodoroSessionRepository,
    session_id: UUID,
    ended_at: datetime,
    reason: str | None = None,
) -> PomodoroSession:
    return InterruptPomodoroSession(pomodoro_session_repository).execute(
        session_id,
        ended_at=ended_at,
        reason=reason,
    )


def get_task(task_repository: InMemoryTaskRepository, task_id: UUID) -> Task:
    task = task_repository.get_by_id(task_id)
    assert task is not None
    return task


def create_task_with_status(
    task_repository: InMemoryTaskRepository,
    status: TaskStatus,
) -> Task:
    from .conftest import InMemoryProjectRepository

    project_repository = InMemoryProjectRepository()
    project = create_project(project_repository)
    task = create_task(task_repository, project_repository, project_id=project.id)
    return task_repository.save(replace(task, status=status, updated_at=START_TIME))

@pytest.mark.revised
def test_starting_focus_session_creates_running_session(
    pomodoro_session_repository: InMemoryPomodoroSessionRepository,
    task_repository: InMemoryTaskRepository,
) -> None:
    session = start_session(pomodoro_session_repository, task_repository)

    assert session.status == PomodoroSessionStatus.RUNNING
    assert session.type == PomodoroSessionType.FOCUS


@pytest.mark.revised
def test_starting_focus_session_sets_started_at(
    pomodoro_session_repository: InMemoryPomodoroSessionRepository,
    task_repository: InMemoryTaskRepository,
) -> None:
    session = start_session(pomodoro_session_repository, task_repository)

    assert session.started_at == START_TIME


@pytest.mark.revised
def test_starting_focus_session_uses_default_focus_duration(
    pomodoro_session_repository: InMemoryPomodoroSessionRepository,
    task_repository: InMemoryTaskRepository,
) -> None:
    session = start_session(pomodoro_session_repository, task_repository)

    assert session.planned_duration_minutes == 25


@pytest.mark.revised
def test_starting_short_break_uses_default_short_break_duration(
    pomodoro_session_repository: InMemoryPomodoroSessionRepository,
    task_repository: InMemoryTaskRepository,
) -> None:
    session = start_session(
        pomodoro_session_repository,
        task_repository,
        session_type=PomodoroSessionType.SHORT_BREAK,
    )

    assert session.planned_duration_minutes == 5


@pytest.mark.revised
def test_starting_long_break_uses_default_long_break_duration(
    pomodoro_session_repository: InMemoryPomodoroSessionRepository,
    task_repository: InMemoryTaskRepository,
) -> None:
    session = start_session(
        pomodoro_session_repository,
        task_repository,
        session_type=PomodoroSessionType.LONG_BREAK,
    )

    assert session.planned_duration_minutes == 15


@pytest.mark.revised
def test_starting_session_accepts_custom_planned_duration(
    pomodoro_session_repository: InMemoryPomodoroSessionRepository,
    task_repository: InMemoryTaskRepository,
) -> None:
    session = start_session(
        pomodoro_session_repository,
        task_repository,
        planned_duration_minutes=10,
    )

    assert session.planned_duration_minutes == 10


@pytest.mark.revised
def test_starting_session_rejects_invalid_session_type(
    pomodoro_session_repository: InMemoryPomodoroSessionRepository,
    task_repository: InMemoryTaskRepository,
) -> None:
    with pytest.raises(InvalidPomodoroSessionError):
        start_session(
            pomodoro_session_repository,
            task_repository,
            session_type="nap",
        )


@pytest.mark.revised
@pytest.mark.parametrize("duration", [0, -1])
def test_starting_session_rejects_zero_or_negative_planned_duration(
    pomodoro_session_repository: InMemoryPomodoroSessionRepository,
    task_repository: InMemoryTaskRepository,
    duration: int,
) -> None:
    with pytest.raises(InvalidPomodoroSessionError):
        start_session(
            pomodoro_session_repository,
            task_repository,
            planned_duration_minutes=duration,
        )


@pytest.mark.revised
def test_starting_session_rejects_naive_started_at(
    pomodoro_session_repository: InMemoryPomodoroSessionRepository,
    task_repository: InMemoryTaskRepository,
) -> None:
    with pytest.raises(InvalidPomodoroSessionError):
        start_session(
            pomodoro_session_repository,
            task_repository,
            started_at=datetime(2026, 5, 1, 9, 0),
        )


@pytest.mark.revised
def test_starting_focus_session_can_associate_task(
    pomodoro_session_repository: InMemoryPomodoroSessionRepository,
    task_repository: InMemoryTaskRepository,
) -> None:
    task = create_task_with_status(task_repository, TaskStatus.TODO)

    session = start_session(
        pomodoro_session_repository,
        task_repository,
        task_id=task.id,
    )

    assert session.task_id == task.id


@pytest.mark.revised
def test_starting_focus_session_can_run_without_task(
    pomodoro_session_repository: InMemoryPomodoroSessionRepository,
    task_repository: InMemoryTaskRepository,
) -> None:
    session = start_session(pomodoro_session_repository, task_repository)

    assert session.task_id is None


@pytest.mark.revised
def test_starting_focus_session_rejects_missing_task(
    pomodoro_session_repository: InMemoryPomodoroSessionRepository,
    task_repository: InMemoryTaskRepository,
) -> None:
    with pytest.raises(InvalidPomodoroSessionError):
        start_session(
            pomodoro_session_repository,
            task_repository,
            task_id=uuid4(),
        )


@pytest.mark.revised
def test_starting_focus_session_rejects_archived_task(
    pomodoro_session_repository: InMemoryPomodoroSessionRepository,
    task_repository: InMemoryTaskRepository,
) -> None:
    task = create_task_with_status(task_repository, TaskStatus.ARCHIVED)

    with pytest.raises(InvalidPomodoroSessionError):
        start_session(
            pomodoro_session_repository,
            task_repository,
            task_id=task.id,
        )


@pytest.mark.revised
@pytest.mark.parametrize(
    "session_type",
    [PomodoroSessionType.SHORT_BREAK, PomodoroSessionType.LONG_BREAK],
)
def test_starting_break_session_rejects_task_association(
    pomodoro_session_repository: InMemoryPomodoroSessionRepository,
    task_repository: InMemoryTaskRepository,
    session_type: PomodoroSessionType,
) -> None:
    task = create_task_with_status(task_repository, TaskStatus.TODO)

    with pytest.raises(InvalidPomodoroSessionError):
        start_session(
            pomodoro_session_repository,
            task_repository,
            session_type=session_type,
            task_id=task.id,
        )


@pytest.mark.revised
def test_starting_focus_session_for_todo_task_changes_task_status_to_doing(
    pomodoro_session_repository: InMemoryPomodoroSessionRepository,
    task_repository: InMemoryTaskRepository,
) -> None:
    task = create_task_with_status(task_repository, TaskStatus.TODO)

    start_session(pomodoro_session_repository, task_repository, task_id=task.id)

    assert get_task(task_repository, task.id).status == TaskStatus.DOING


@pytest.mark.revised
def test_starting_focus_session_for_todo_task_updates_task_updated_at(
    pomodoro_session_repository: InMemoryPomodoroSessionRepository,
    task_repository: InMemoryTaskRepository,
) -> None:
    task = create_task_with_status(task_repository, TaskStatus.TODO)

    start_session(pomodoro_session_repository, task_repository, task_id=task.id)

    assert get_task(task_repository, task.id).updated_at > START_TIME


@pytest.mark.revised
@pytest.mark.parametrize("status", [TaskStatus.DOING, TaskStatus.DONE])
def test_starting_focus_session_for_non_todo_task_leaves_task_unchanged(
    pomodoro_session_repository: InMemoryPomodoroSessionRepository,
    task_repository: InMemoryTaskRepository,
    status: TaskStatus,
) -> None:
    task = create_task_with_status(task_repository, status)

    start_session(pomodoro_session_repository, task_repository, task_id=task.id)

    assert get_task(task_repository, task.id).status == status
    assert get_task(task_repository, task.id).updated_at == START_TIME


@pytest.mark.revised
def test_starting_session_fails_when_another_session_is_running(
    pomodoro_session_repository: InMemoryPomodoroSessionRepository,
    task_repository: InMemoryTaskRepository,
) -> None:
    start_session(pomodoro_session_repository, task_repository)

    with pytest.raises(InvalidPomodoroSessionError):
        start_session(
            pomodoro_session_repository,
            task_repository,
            started_at=START_TIME + timedelta(minutes=1),
        )


@pytest.mark.revised
def test_starting_session_fails_when_another_session_is_paused(
    pomodoro_session_repository: InMemoryPomodoroSessionRepository,
    task_repository: InMemoryTaskRepository,
) -> None:
    session = start_session(pomodoro_session_repository, task_repository)
    pause_session(
        pomodoro_session_repository,
        session.id,
        paused_at=START_TIME + timedelta(minutes=5),
    )

    with pytest.raises(InvalidPomodoroSessionError):
        start_session(
            pomodoro_session_repository,
            task_repository,
            started_at=START_TIME + timedelta(minutes=6),
        )


@pytest.mark.revised
@pytest.mark.parametrize("finalizer", ["complete", "interrupt"])
def test_finished_sessions_do_not_block_starting_new_session(
    pomodoro_session_repository: InMemoryPomodoroSessionRepository,
    task_repository: InMemoryTaskRepository,
    finalizer: str,
) -> None:
    session = start_session(pomodoro_session_repository, task_repository)
    if finalizer == "complete":
        complete_session(
            pomodoro_session_repository,
            session.id,
            ended_at=START_TIME + timedelta(minutes=25),
        )
    else:
        interrupt_session(
            pomodoro_session_repository,
            session.id,
            ended_at=START_TIME + timedelta(minutes=10),
        )

    next_session = start_session(
        pomodoro_session_repository,
        task_repository,
        started_at=START_TIME + timedelta(minutes=30),
    )

    assert next_session.status == PomodoroSessionStatus.RUNNING


@pytest.mark.revised
def test_getting_active_session_returns_running_session(
    pomodoro_session_repository: InMemoryPomodoroSessionRepository,
    task_repository: InMemoryTaskRepository,
) -> None:
    session = start_session(pomodoro_session_repository, task_repository)

    active_session = GetActivePomodoroSession(pomodoro_session_repository).execute()

    assert active_session == session


@pytest.mark.revised
def test_getting_active_session_returns_paused_session(
    pomodoro_session_repository: InMemoryPomodoroSessionRepository,
    task_repository: InMemoryTaskRepository,
) -> None:
    session = start_session(pomodoro_session_repository, task_repository)
    paused_session = pause_session(
        pomodoro_session_repository,
        session.id,
        paused_at=START_TIME + timedelta(minutes=5),
    )

    active_session = GetActivePomodoroSession(pomodoro_session_repository).execute()

    assert active_session == paused_session


@pytest.mark.revised
def test_getting_active_session_returns_none_when_no_active_session(
    pomodoro_session_repository: InMemoryPomodoroSessionRepository,
) -> None:
    active_session = GetActivePomodoroSession(pomodoro_session_repository).execute()

    assert active_session is None


@pytest.mark.revised
def test_pausing_running_session_marks_it_as_paused(
    pomodoro_session_repository: InMemoryPomodoroSessionRepository,
    task_repository: InMemoryTaskRepository,
) -> None:
    session = start_session(pomodoro_session_repository, task_repository)

    paused_session = pause_session(
        pomodoro_session_repository,
        session.id,
        paused_at=START_TIME + timedelta(minutes=5),
    )

    assert paused_session.status == PomodoroSessionStatus.PAUSED
    assert paused_session.paused_at == START_TIME + timedelta(minutes=5)
    assert paused_session.updated_at > session.updated_at


@pytest.mark.revised
def test_pausing_missing_session_fails(
    pomodoro_session_repository: InMemoryPomodoroSessionRepository,
) -> None:
    with pytest.raises(InvalidPomodoroSessionError):
        pause_session(
            pomodoro_session_repository,
            uuid4(),
            paused_at=START_TIME + timedelta(minutes=5),
        )


@pytest.mark.revised
def test_pausing_non_running_session_fails(
    pomodoro_session_repository: InMemoryPomodoroSessionRepository,
    task_repository: InMemoryTaskRepository,
) -> None:
    session = start_session(pomodoro_session_repository, task_repository)
    complete_session(
        pomodoro_session_repository,
        session.id,
        ended_at=START_TIME + timedelta(minutes=25),
    )

    with pytest.raises(InvalidPomodoroSessionError):
        pause_session(
            pomodoro_session_repository,
            session.id,
            paused_at=START_TIME + timedelta(minutes=26),
        )


@pytest.mark.revised
def test_pausing_session_rejects_naive_paused_at(
    pomodoro_session_repository: InMemoryPomodoroSessionRepository,
    task_repository: InMemoryTaskRepository,
) -> None:
    session = start_session(pomodoro_session_repository, task_repository)

    with pytest.raises(InvalidPomodoroSessionError):
        pause_session(
            pomodoro_session_repository,
            session.id,
            paused_at=datetime(2026, 5, 1, 9, 5),
        )


@pytest.mark.revised
def test_resuming_paused_session_marks_it_as_running(
    pomodoro_session_repository: InMemoryPomodoroSessionRepository,
    task_repository: InMemoryTaskRepository,
) -> None:
    session = start_session(pomodoro_session_repository, task_repository)
    pause_session(
        pomodoro_session_repository,
        session.id,
        paused_at=START_TIME + timedelta(minutes=5),
    )

    resumed_session = resume_session(
        pomodoro_session_repository,
        session.id,
        resumed_at=START_TIME + timedelta(minutes=8),
    )

    assert resumed_session.status == PomodoroSessionStatus.RUNNING
    assert resumed_session.paused_at is None
    assert resumed_session.accumulated_pause_seconds == 180


@pytest.mark.revised
def test_resuming_paused_session_updates_updated_at(
    pomodoro_session_repository: InMemoryPomodoroSessionRepository,
    task_repository: InMemoryTaskRepository,
) -> None:
    session = start_session(pomodoro_session_repository, task_repository)
    paused_session = pause_session(
        pomodoro_session_repository,
        session.id,
        paused_at=START_TIME + timedelta(minutes=5),
    )

    resumed_session = resume_session(
        pomodoro_session_repository,
        session.id,
        resumed_at=START_TIME + timedelta(minutes=8),
    )

    assert resumed_session.updated_at > paused_session.updated_at


def test_resuming_missing_session_fails(
    pomodoro_session_repository: InMemoryPomodoroSessionRepository,
) -> None:
    with pytest.raises(InvalidPomodoroSessionError):
        resume_session(
            pomodoro_session_repository,
            uuid4(),
            resumed_at=START_TIME + timedelta(minutes=8),
        )


def test_resuming_non_paused_session_fails(
    pomodoro_session_repository: InMemoryPomodoroSessionRepository,
    task_repository: InMemoryTaskRepository,
) -> None:
    session = start_session(pomodoro_session_repository, task_repository)

    with pytest.raises(InvalidPomodoroSessionError):
        resume_session(
            pomodoro_session_repository,
            session.id,
            resumed_at=START_TIME + timedelta(minutes=8),
        )


@pytest.mark.revised
def test_resuming_session_rejects_naive_resume_time(
    pomodoro_session_repository: InMemoryPomodoroSessionRepository,
    task_repository: InMemoryTaskRepository,
) -> None:
    session = start_session(pomodoro_session_repository, task_repository)
    pause_session(
        pomodoro_session_repository,
        session.id,
        paused_at=START_TIME + timedelta(minutes=5),
    )

    with pytest.raises(InvalidPomodoroSessionError):
        resume_session(
            pomodoro_session_repository,
            session.id,
            resumed_at=datetime(2026, 5, 1, 9, 8),
        )


@pytest.mark.revised
def test_resuming_session_rejects_resume_time_before_or_equal_to_paused_at(
    pomodoro_session_repository: InMemoryPomodoroSessionRepository,
    task_repository: InMemoryTaskRepository,
) -> None:
    session = start_session(pomodoro_session_repository, task_repository)
    pause_session(
        pomodoro_session_repository,
        session.id,
        paused_at=START_TIME + timedelta(minutes=5),
    )

    with pytest.raises(InvalidPomodoroSessionError):
        resume_session(
            pomodoro_session_repository,
            session.id,
            resumed_at=START_TIME + timedelta(minutes=5),
        )


@pytest.mark.revised
def test_completing_running_session_marks_it_as_completed(
    pomodoro_session_repository: InMemoryPomodoroSessionRepository,
    task_repository: InMemoryTaskRepository,
) -> None:
    session = start_session(pomodoro_session_repository, task_repository)

    completed_session = complete_session(
        pomodoro_session_repository,
        session.id,
        ended_at=START_TIME + timedelta(minutes=25),
    )

    assert completed_session.status == PomodoroSessionStatus.COMPLETED
    assert completed_session.ended_at == START_TIME + timedelta(minutes=25)
    assert completed_session.actual_duration_minutes == 25
    assert completed_session.updated_at > session.updated_at


@pytest.mark.revised
def test_completing_paused_session_excludes_paused_time_from_actual_duration(
    pomodoro_session_repository: InMemoryPomodoroSessionRepository,
    task_repository: InMemoryTaskRepository,
) -> None:
    session = start_session(pomodoro_session_repository, task_repository)
    pause_session(
        pomodoro_session_repository,
        session.id,
        paused_at=START_TIME + timedelta(minutes=10),
    )

    completed_session = complete_session(
        pomodoro_session_repository,
        session.id,
        ended_at=START_TIME + timedelta(minutes=15),
    )

    assert completed_session.status == PomodoroSessionStatus.COMPLETED
    assert completed_session.actual_duration_minutes == 10


@pytest.mark.revised
def test_completing_session_rounds_actual_duration_down_to_whole_minutes(
    pomodoro_session_repository: InMemoryPomodoroSessionRepository,
    task_repository: InMemoryTaskRepository,
) -> None:
    session = start_session(pomodoro_session_repository, task_repository)

    completed_session = complete_session(
        pomodoro_session_repository,
        session.id,
        ended_at=START_TIME + timedelta(minutes=25, seconds=59),
    )

    assert completed_session.actual_duration_minutes == 25


@pytest.mark.revised
def test_completing_missing_session_fails(
    pomodoro_session_repository: InMemoryPomodoroSessionRepository,
) -> None:
    with pytest.raises(InvalidPomodoroSessionError):
        complete_session(
            pomodoro_session_repository,
            uuid4(),
            ended_at=START_TIME + timedelta(minutes=25),
        )


@pytest.mark.revised
def test_completing_non_active_session_fails(
    pomodoro_session_repository: InMemoryPomodoroSessionRepository,
    task_repository: InMemoryTaskRepository,
) -> None:
    session = start_session(pomodoro_session_repository, task_repository)
    complete_session(
        pomodoro_session_repository,
        session.id,
        ended_at=START_TIME + timedelta(minutes=25),
    )

    with pytest.raises(InvalidPomodoroSessionError):
        complete_session(
            pomodoro_session_repository,
            session.id,
            ended_at=START_TIME + timedelta(minutes=30),
        )


@pytest.mark.revised
def test_completing_session_rejects_naive_ended_at(
    pomodoro_session_repository: InMemoryPomodoroSessionRepository,
    task_repository: InMemoryTaskRepository,
) -> None:
    session = start_session(pomodoro_session_repository, task_repository)

    with pytest.raises(InvalidPomodoroSessionError):
        complete_session(
            pomodoro_session_repository,
            session.id,
            ended_at=datetime(2026, 5, 1, 9, 25),
        )


@pytest.mark.revised
def test_completing_session_rejects_end_times_before_or_equal_to_start_time(
    pomodoro_session_repository: InMemoryPomodoroSessionRepository,
    task_repository: InMemoryTaskRepository,
) -> None:
    session = start_session(pomodoro_session_repository, task_repository)

    with pytest.raises(InvalidPomodoroSessionError):
        complete_session(
            pomodoro_session_repository,
            session.id,
            ended_at=START_TIME,
        )


@pytest.mark.revised
def test_completing_session_does_not_complete_associated_task(
    pomodoro_session_repository: InMemoryPomodoroSessionRepository,
    task_repository: InMemoryTaskRepository,
) -> None:
    task = create_task_with_status(task_repository, TaskStatus.TODO)
    session = start_session(
        pomodoro_session_repository,
        task_repository,
        task_id=task.id,
    )

    complete_session(
        pomodoro_session_repository,
        session.id,
        ended_at=START_TIME + timedelta(minutes=25),
    )

    assert get_task(task_repository, task.id).status == TaskStatus.DOING


@pytest.mark.revised
def test_interrupting_running_session_marks_it_as_interrupted(
    pomodoro_session_repository: InMemoryPomodoroSessionRepository,
    task_repository: InMemoryTaskRepository,
) -> None:
    session = start_session(pomodoro_session_repository, task_repository)

    interrupted_session = interrupt_session(
        pomodoro_session_repository,
        session.id,
        ended_at=START_TIME + timedelta(minutes=10),
        reason="meeting",
    )

    assert interrupted_session.status == PomodoroSessionStatus.INTERRUPTED
    assert interrupted_session.ended_at == START_TIME + timedelta(minutes=10)
    assert interrupted_session.actual_duration_minutes == 10
    assert interrupted_session.interruption_reason == "meeting"
    assert interrupted_session.updated_at > session.updated_at


@pytest.mark.revised
def test_interrupting_paused_session_excludes_paused_time_from_actual_duration(
    pomodoro_session_repository: InMemoryPomodoroSessionRepository,
    task_repository: InMemoryTaskRepository,
) -> None:
    session = start_session(pomodoro_session_repository, task_repository)
    pause_session(
        pomodoro_session_repository,
        session.id,
        paused_at=START_TIME + timedelta(minutes=10),
    )

    interrupted_session = interrupt_session(
        pomodoro_session_repository,
        session.id,
        ended_at=START_TIME + timedelta(minutes=15),
    )

    assert interrupted_session.actual_duration_minutes == 10


@pytest.mark.revised
def test_interrupting_session_trims_reason(
    pomodoro_session_repository: InMemoryPomodoroSessionRepository,
    task_repository: InMemoryTaskRepository,
) -> None:
    session = start_session(pomodoro_session_repository, task_repository)

    interrupted_session = interrupt_session(
        pomodoro_session_repository,
        session.id,
        ended_at=START_TIME + timedelta(minutes=10),
        reason="  meeting  ",
    )

    assert interrupted_session.interruption_reason == "meeting"


@pytest.mark.revised
def test_interrupting_session_stores_none_for_blank_reason(
    pomodoro_session_repository: InMemoryPomodoroSessionRepository,
    task_repository: InMemoryTaskRepository,
) -> None:
    session = start_session(pomodoro_session_repository, task_repository)

    interrupted_session = interrupt_session(
        pomodoro_session_repository,
        session.id,
        ended_at=START_TIME + timedelta(minutes=10),
        reason="   ",
    )

    assert interrupted_session.interruption_reason is None


@pytest.mark.revised
def test_interrupting_missing_session_fails(
    pomodoro_session_repository: InMemoryPomodoroSessionRepository,
) -> None:
    with pytest.raises(InvalidPomodoroSessionError):
        interrupt_session(
            pomodoro_session_repository,
            uuid4(),
            ended_at=START_TIME + timedelta(minutes=10),
        )


@pytest.mark.revised
def test_interrupting_non_active_session_fails(
    pomodoro_session_repository: InMemoryPomodoroSessionRepository,
    task_repository: InMemoryTaskRepository,
) -> None:
    session = start_session(pomodoro_session_repository, task_repository)
    complete_session(
        pomodoro_session_repository,
        session.id,
        ended_at=START_TIME + timedelta(minutes=25),
    )

    with pytest.raises(InvalidPomodoroSessionError):
        interrupt_session(
            pomodoro_session_repository,
            session.id,
            ended_at=START_TIME + timedelta(minutes=30),
        )


@pytest.mark.revised
def test_interrupting_session_rejects_naive_ended_at(
    pomodoro_session_repository: InMemoryPomodoroSessionRepository,
    task_repository: InMemoryTaskRepository,
) -> None:
    session = start_session(pomodoro_session_repository, task_repository)

    with pytest.raises(InvalidPomodoroSessionError):
        interrupt_session(
            pomodoro_session_repository,
            session.id,
            ended_at=datetime(2026, 5, 1, 9, 10),
        )


@pytest.mark.revised
def test_interrupting_session_rejects_end_times_before_or_equal_to_start_time(
    pomodoro_session_repository: InMemoryPomodoroSessionRepository,
    task_repository: InMemoryTaskRepository,
) -> None:
    session = start_session(pomodoro_session_repository, task_repository)

    with pytest.raises(InvalidPomodoroSessionError):
        interrupt_session(
            pomodoro_session_repository,
            session.id,
            ended_at=START_TIME,
        )


@pytest.mark.revised
def test_interrupting_session_does_not_modify_associated_task_status(
    pomodoro_session_repository: InMemoryPomodoroSessionRepository,
    task_repository: InMemoryTaskRepository,
) -> None:
    task = create_task_with_status(task_repository, TaskStatus.DONE)
    session = start_session(
        pomodoro_session_repository,
        task_repository,
        task_id=task.id,
    )

    interrupt_session(
        pomodoro_session_repository,
        session.id,
        ended_at=START_TIME + timedelta(minutes=10),
    )

    assert get_task(task_repository, task.id).status == TaskStatus.DONE


@pytest.mark.revised
def test_running_sessions_have_open_session_fields(
    pomodoro_session_repository: InMemoryPomodoroSessionRepository,
    task_repository: InMemoryTaskRepository,
) -> None:
    session = start_session(pomodoro_session_repository, task_repository)

    assert session.ended_at is None
    assert session.actual_duration_minutes is None
    assert session.interruption_reason is None
    assert session.paused_at is None
    assert session.accumulated_pause_seconds == 0


@pytest.mark.revised
def test_paused_sessions_have_pause_fields_and_no_end_fields(
    pomodoro_session_repository: InMemoryPomodoroSessionRepository,
    task_repository: InMemoryTaskRepository,
) -> None:
    session = start_session(pomodoro_session_repository, task_repository)

    paused_session = pause_session(
        pomodoro_session_repository,
        session.id,
        paused_at=START_TIME + timedelta(minutes=5),
    )

    assert paused_session.paused_at == START_TIME + timedelta(minutes=5)
    assert paused_session.ended_at is None
    assert paused_session.actual_duration_minutes is None


@pytest.mark.revised
def test_finished_sessions_preserve_planned_duration(
    pomodoro_session_repository: InMemoryPomodoroSessionRepository,
    task_repository: InMemoryTaskRepository,
) -> None:
    completed = start_session(
        pomodoro_session_repository,
        task_repository,
        planned_duration_minutes=10,
    )
    complete_session(
        pomodoro_session_repository,
        completed.id,
        ended_at=START_TIME + timedelta(minutes=10),
    )
    interrupted = start_session(
        pomodoro_session_repository,
        task_repository,
        started_at=START_TIME + timedelta(minutes=20),
        planned_duration_minutes=15,
    )

    interrupted = interrupt_session(
        pomodoro_session_repository,
        interrupted.id,
        ended_at=START_TIME + timedelta(minutes=25),
    )

    saved_completed_session = pomodoro_session_repository.get_by_id(completed.id)
    assert saved_completed_session is not None
    assert saved_completed_session.planned_duration_minutes == 10
    assert interrupted.planned_duration_minutes == 15


@pytest.mark.revised
def test_session_identity_and_timestamps_are_set(
    pomodoro_session_repository: InMemoryPomodoroSessionRepository,
    task_repository: InMemoryTaskRepository,
) -> None:
    session = start_session(pomodoro_session_repository, task_repository)

    assert session.id is not None
    assert session.created_at is not None
    assert session.updated_at is not None
