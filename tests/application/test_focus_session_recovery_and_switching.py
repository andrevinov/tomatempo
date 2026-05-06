from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime, timedelta
from typing import Protocol, cast
from uuid import UUID, uuid4

import pytest

from tomatempo.application.use_cases import (
    DiscardStalePausedPomodoroSession,
    EndFocusSessionForTaskSwitch,
    InvalidPomodoroSessionError,
    RecoverActivePomodoroSession,
    StartCarriedOverFocusSession,
    calculate_remaining_planned_minutes,
    has_meaningful_task_switch_carry_over,
)
from tomatempo.domain.entities import PomodoroSession
from tomatempo.domain.value_objects import (
    PomodoroSessionStatus,
    PomodoroSessionType,
    TaskStatus,
)

from .conftest import (
    InMemoryPomodoroSessionRepository,
    InMemoryTaskRepository,
    create_task_with_status,
    get_task,
)
from .test_pomodoro_sessions import (
    complete_session,
    interrupt_session,
    pause_session,
    start_session,
)

START_TIME = datetime(2026, 5, 1, 9, 0, tzinfo=UTC)


class TaskSwitchResult(Protocol):
    ended_session: PomodoroSession
    remaining_planned_minutes: int
    has_meaningful_remaining_minutes: bool


def recover_active_session(
    pomodoro_session_repository: InMemoryPomodoroSessionRepository,
    now: datetime,
) -> PomodoroSession | None:
    return cast(
        PomodoroSession | None,
        RecoverActivePomodoroSession(pomodoro_session_repository).execute(now=now),
    )


def discard_stale_paused_session(
    pomodoro_session_repository: InMemoryPomodoroSessionRepository,
    session_id: UUID,
    now: datetime,
) -> PomodoroSession:
    return cast(
        PomodoroSession,
        DiscardStalePausedPomodoroSession(pomodoro_session_repository).execute(
            session_id=session_id,
            now=now,
        ),
    )


def end_focus_session_for_switch(
    pomodoro_session_repository: InMemoryPomodoroSessionRepository,
    session_id: UUID,
    ended_at: datetime,
    mode: str,
) -> TaskSwitchResult:
    return cast(
        TaskSwitchResult,
        EndFocusSessionForTaskSwitch(pomodoro_session_repository).execute(
            session_id=session_id,
            ended_at=ended_at,
            mode=mode,
        ),
    )


def start_carried_over_focus_session(
    pomodoro_session_repository: InMemoryPomodoroSessionRepository,
    task_repository: InMemoryTaskRepository,
    task_id: UUID,
    started_at: datetime,
    remaining_planned_minutes: int,
) -> PomodoroSession:
    return cast(
        PomodoroSession,
        StartCarriedOverFocusSession(
            pomodoro_session_repository,
            task_repository,
        ).execute(
            task_id=task_id,
            started_at=started_at,
            remaining_planned_minutes=remaining_planned_minutes,
        ),
    )


def save_session(
    pomodoro_session_repository: InMemoryPomodoroSessionRepository,
    session: PomodoroSession,
) -> PomodoroSession:
    return pomodoro_session_repository.save(session)


def saved_session(
    pomodoro_session_repository: InMemoryPomodoroSessionRepository,
    session: PomodoroSession,
) -> PomodoroSession:
    saved = pomodoro_session_repository.get_by_id(session.id)
    assert saved is not None
    return saved


@pytest.mark.revised
def test_recovering_active_session_returns_none_when_no_active_session_exists(
    pomodoro_session_repository: InMemoryPomodoroSessionRepository,
) -> None:
    assert recover_active_session(pomodoro_session_repository, START_TIME) is None


def test_recovering_active_session_returns_running_session(
    pomodoro_session_repository: InMemoryPomodoroSessionRepository,
    task_repository: InMemoryTaskRepository,
) -> None:
    session = start_session(pomodoro_session_repository, task_repository)

    recovered = recover_active_session(
        pomodoro_session_repository,
        START_TIME + timedelta(hours=4),
    )

    assert recovered == session


@pytest.mark.revised
def test_recovering_active_session_returns_non_stale_paused_session(
    pomodoro_session_repository: InMemoryPomodoroSessionRepository,
    task_repository: InMemoryTaskRepository,
) -> None:
    session = start_session(pomodoro_session_repository, task_repository)
    paused = pause_session(
        pomodoro_session_repository,
        session.id,
        paused_at=START_TIME + timedelta(minutes=15),
    )

    recovered = recover_active_session(
        pomodoro_session_repository,
        START_TIME + timedelta(hours=1, minutes=15),
    )

    assert recovered == paused


@pytest.mark.revised
def test_recovering_active_session_rejects_naive_current_time(
    pomodoro_session_repository: InMemoryPomodoroSessionRepository,
) -> None:
    with pytest.raises(InvalidPomodoroSessionError):
        recover_active_session(
            pomodoro_session_repository,
            datetime(2026, 5, 1, 10, 0),
        )


@pytest.mark.revised
def test_recovering_active_session_discards_stale_paused_session(
    pomodoro_session_repository: InMemoryPomodoroSessionRepository,
    task_repository: InMemoryTaskRepository,
) -> None:
    session = start_session(pomodoro_session_repository, task_repository)
    pause_session(
        pomodoro_session_repository,
        session.id,
        paused_at=START_TIME + timedelta(minutes=10),
    )
    now = START_TIME + timedelta(hours=2)

    recovered = recover_active_session(pomodoro_session_repository, now)
    discarded = saved_session(pomodoro_session_repository, session)

    assert recovered is None
    assert discarded.status == PomodoroSessionStatus.INTERRUPTED
    assert discarded.interruption_reason == "stale_pause_discarded"


@pytest.mark.revised
def test_recovering_running_session_does_not_update_session(
    pomodoro_session_repository: InMemoryPomodoroSessionRepository,
    task_repository: InMemoryTaskRepository,
) -> None:
    session = start_session(pomodoro_session_repository, task_repository)

    recover_active_session(
        pomodoro_session_repository,
        START_TIME + timedelta(hours=3),
    )

    assert saved_session(pomodoro_session_repository, session) == session


@pytest.mark.revised
def test_recovering_non_stale_paused_session_does_not_update_session(
    pomodoro_session_repository: InMemoryPomodoroSessionRepository,
    task_repository: InMemoryTaskRepository,
) -> None:
    session = start_session(pomodoro_session_repository, task_repository)
    paused = pause_session(
        pomodoro_session_repository,
        session.id,
        paused_at=START_TIME + timedelta(minutes=20),
    )

    recover_active_session(
        pomodoro_session_repository,
        START_TIME + timedelta(minutes=50),
    )

    assert saved_session(pomodoro_session_repository, session) == paused


@pytest.mark.revised
@pytest.mark.parametrize(
    ("pause_age", "is_stale"),
    [
        (timedelta(hours=1, seconds=1), True),
        (timedelta(hours=1), False),
        (timedelta(minutes=59, seconds=59), False),
    ],
)
def test_paused_session_staleness_uses_one_hour_threshold(
    pomodoro_session_repository: InMemoryPomodoroSessionRepository,
    task_repository: InMemoryTaskRepository,
    pause_age: timedelta,
    is_stale: bool,
) -> None:
    session = start_session(pomodoro_session_repository, task_repository)
    pause_session(
        pomodoro_session_repository,
        session.id,
        paused_at=START_TIME + timedelta(minutes=5),
    )
    now = START_TIME + timedelta(minutes=5) + pause_age

    if is_stale:
        assert recover_active_session(pomodoro_session_repository, now) is None
    else:
        assert recover_active_session(pomodoro_session_repository, now) is not None


def test_stale_detection_uses_paused_at_not_updated_at(
    pomodoro_session_repository: InMemoryPomodoroSessionRepository,
    task_repository: InMemoryTaskRepository,
) -> None:
    session = start_session(pomodoro_session_repository, task_repository)
    paused = pause_session(
        pomodoro_session_repository,
        session.id,
        paused_at=START_TIME + timedelta(minutes=10),
    )
    save_session(
        pomodoro_session_repository,
        replace(paused, updated_at=START_TIME + timedelta(hours=2)),
    )

    recovered = recover_active_session(
        pomodoro_session_repository,
        START_TIME + timedelta(minutes=40),
    )

    assert recovered is not None
    assert recovered.status == PomodoroSessionStatus.PAUSED


def test_discarding_stale_paused_session_marks_it_as_interrupted(
    pomodoro_session_repository: InMemoryPomodoroSessionRepository,
    task_repository: InMemoryTaskRepository,
) -> None:
    session = start_session(pomodoro_session_repository, task_repository)
    pause_session(
        pomodoro_session_repository,
        session.id,
        paused_at=START_TIME + timedelta(minutes=10),
    )

    discarded = discard_stale_paused_session(
        pomodoro_session_repository,
        session.id,
        now=START_TIME + timedelta(hours=2),
    )

    assert discarded.status == PomodoroSessionStatus.INTERRUPTED


def test_discarding_stale_paused_session_sets_end_fields(
    pomodoro_session_repository: InMemoryPomodoroSessionRepository,
    task_repository: InMemoryTaskRepository,
) -> None:
    session = start_session(pomodoro_session_repository, task_repository)
    pause_session(
        pomodoro_session_repository,
        session.id,
        paused_at=START_TIME + timedelta(minutes=10),
    )
    now = START_TIME + timedelta(hours=2)

    discarded = discard_stale_paused_session(
        pomodoro_session_repository,
        session.id,
        now=now,
    )

    assert discarded.ended_at == now
    assert discarded.paused_at is None
    assert discarded.interruption_reason == "stale_pause_discarded"
    assert discarded.actual_duration_minutes == 10


def test_discarding_stale_paused_session_accumulates_discarded_pause_time(
    pomodoro_session_repository: InMemoryPomodoroSessionRepository,
    task_repository: InMemoryTaskRepository,
) -> None:
    session = start_session(pomodoro_session_repository, task_repository)
    pause_session(
        pomodoro_session_repository,
        session.id,
        paused_at=START_TIME + timedelta(minutes=10),
    )

    discarded = discard_stale_paused_session(
        pomodoro_session_repository,
        session.id,
        now=START_TIME + timedelta(hours=2),
    )

    assert discarded.accumulated_pause_seconds == 110 * 60


def test_discarded_stale_paused_session_no_longer_blocks_starting_new_session(
    pomodoro_session_repository: InMemoryPomodoroSessionRepository,
    task_repository: InMemoryTaskRepository,
) -> None:
    session = start_session(pomodoro_session_repository, task_repository)
    pause_session(
        pomodoro_session_repository,
        session.id,
        paused_at=START_TIME + timedelta(minutes=10),
    )
    discard_stale_paused_session(
        pomodoro_session_repository,
        session.id,
        now=START_TIME + timedelta(hours=2),
    )

    next_session = start_session(
        pomodoro_session_repository,
        task_repository,
        started_at=START_TIME + timedelta(hours=2, minutes=1),
    )

    assert next_session.status == PomodoroSessionStatus.RUNNING


def test_discarding_missing_session_fails(
    pomodoro_session_repository: InMemoryPomodoroSessionRepository,
) -> None:
    with pytest.raises(InvalidPomodoroSessionError):
        discard_stale_paused_session(
            pomodoro_session_repository,
            uuid4(),
            now=START_TIME + timedelta(hours=2),
        )


@pytest.mark.parametrize(
    "status",
    [
        PomodoroSessionStatus.RUNNING,
        PomodoroSessionStatus.COMPLETED,
        PomodoroSessionStatus.INTERRUPTED,
    ],
)
def test_discarding_non_paused_session_fails(
    pomodoro_session_repository: InMemoryPomodoroSessionRepository,
    status: PomodoroSessionStatus,
) -> None:
    session = save_session(
        pomodoro_session_repository,
        PomodoroSession(
            type=PomodoroSessionType.FOCUS,
            status=status,
            planned_duration_minutes=25,
            started_at=START_TIME,
            created_at=START_TIME,
            updated_at=START_TIME,
            ended_at=START_TIME + timedelta(minutes=10)
            if status != PomodoroSessionStatus.RUNNING
            else None,
        ),
    )

    with pytest.raises(InvalidPomodoroSessionError):
        discard_stale_paused_session(
            pomodoro_session_repository,
            session.id,
            now=START_TIME + timedelta(hours=2),
        )


def test_discarding_paused_session_without_paused_at_fails(
    pomodoro_session_repository: InMemoryPomodoroSessionRepository,
) -> None:
    session = save_session(
        pomodoro_session_repository,
        PomodoroSession(
            type=PomodoroSessionType.FOCUS,
            status=PomodoroSessionStatus.PAUSED,
            planned_duration_minutes=25,
            started_at=START_TIME,
            created_at=START_TIME,
            updated_at=START_TIME,
        ),
    )

    with pytest.raises(InvalidPomodoroSessionError):
        discard_stale_paused_session(
            pomodoro_session_repository,
            session.id,
            now=START_TIME + timedelta(hours=2),
        )


def test_discarding_non_stale_paused_session_fails(
    pomodoro_session_repository: InMemoryPomodoroSessionRepository,
    task_repository: InMemoryTaskRepository,
) -> None:
    session = start_session(pomodoro_session_repository, task_repository)
    pause_session(
        pomodoro_session_repository,
        session.id,
        paused_at=START_TIME + timedelta(minutes=10),
    )

    with pytest.raises(InvalidPomodoroSessionError):
        discard_stale_paused_session(
            pomodoro_session_repository,
            session.id,
            now=START_TIME + timedelta(minutes=40),
        )


def test_discarding_with_naive_current_time_fails(
    pomodoro_session_repository: InMemoryPomodoroSessionRepository,
    task_repository: InMemoryTaskRepository,
) -> None:
    session = start_session(pomodoro_session_repository, task_repository)
    pause_session(
        pomodoro_session_repository,
        session.id,
        paused_at=START_TIME + timedelta(minutes=10),
    )

    with pytest.raises(InvalidPomodoroSessionError):
        discard_stale_paused_session(
            pomodoro_session_repository,
            session.id,
            now=datetime(2026, 5, 1, 11, 0),
        )


@pytest.mark.parametrize("offset", [timedelta(minutes=-1), timedelta()])
def test_discarding_with_current_time_before_or_equal_to_paused_at_fails(
    pomodoro_session_repository: InMemoryPomodoroSessionRepository,
    task_repository: InMemoryTaskRepository,
    offset: timedelta,
) -> None:
    session = start_session(pomodoro_session_repository, task_repository)
    paused_at = START_TIME + timedelta(minutes=10)
    pause_session(pomodoro_session_repository, session.id, paused_at=paused_at)

    with pytest.raises(InvalidPomodoroSessionError):
        discard_stale_paused_session(
            pomodoro_session_repository,
            session.id,
            now=paused_at + offset,
        )


@pytest.mark.parametrize(
    ("actual_duration_minutes", "expected_remaining_minutes"),
    [(15, 10), (25, 0), (30, 0)],
)
def test_remaining_planned_minutes_never_return_negative_values(
    actual_duration_minutes: int,
    expected_remaining_minutes: int,
) -> None:
    session = PomodoroSession(
        type=PomodoroSessionType.FOCUS,
        status=PomodoroSessionStatus.COMPLETED,
        planned_duration_minutes=25,
        actual_duration_minutes=actual_duration_minutes,
        started_at=START_TIME,
    )

    remaining_minutes = calculate_remaining_planned_minutes(session)

    assert remaining_minutes == expected_remaining_minutes


def test_sessions_without_actual_duration_have_no_meaningful_carry_over(
) -> None:
    session = PomodoroSession(
        type=PomodoroSessionType.FOCUS,
        status=PomodoroSessionStatus.RUNNING,
        planned_duration_minutes=25,
        started_at=START_TIME,
    )

    assert calculate_remaining_planned_minutes(session) == 0
    assert has_meaningful_task_switch_carry_over(session) is False


@pytest.mark.parametrize(
    "session_type",
    [PomodoroSessionType.SHORT_BREAK, PomodoroSessionType.LONG_BREAK],
)
def test_break_sessions_do_not_produce_meaningful_task_switch_carry_over(
    session_type: PomodoroSessionType,
) -> None:
    session = PomodoroSession(
        type=session_type,
        status=PomodoroSessionStatus.COMPLETED,
        planned_duration_minutes=5,
        actual_duration_minutes=2,
        started_at=START_TIME,
    )

    assert has_meaningful_task_switch_carry_over(session) is False


def test_ending_running_focus_session_for_switch_completes_it_when_mode_is_complete(
    pomodoro_session_repository: InMemoryPomodoroSessionRepository,
    task_repository: InMemoryTaskRepository,
) -> None:
    session = start_session(pomodoro_session_repository, task_repository)

    result = end_focus_session_for_switch(
        pomodoro_session_repository,
        session.id,
        ended_at=START_TIME + timedelta(minutes=15),
        mode="complete",
    )

    assert result.ended_session.status == PomodoroSessionStatus.COMPLETED
    assert result.ended_session.actual_duration_minutes == 15


def test_ending_running_focus_session_for_switch_interrupts_it_when_mode_is_interrupt(
    pomodoro_session_repository: InMemoryPomodoroSessionRepository,
    task_repository: InMemoryTaskRepository,
) -> None:
    session = start_session(pomodoro_session_repository, task_repository)

    result = end_focus_session_for_switch(
        pomodoro_session_repository,
        session.id,
        ended_at=START_TIME + timedelta(minutes=15),
        mode="interrupt",
    )

    assert result.ended_session.status == PomodoroSessionStatus.INTERRUPTED
    assert result.ended_session.actual_duration_minutes == 15


def test_ending_paused_focus_session_for_switch_excludes_paused_time(
    pomodoro_session_repository: InMemoryPomodoroSessionRepository,
    task_repository: InMemoryTaskRepository,
) -> None:
    session = start_session(pomodoro_session_repository, task_repository)
    pause_session(
        pomodoro_session_repository,
        session.id,
        paused_at=START_TIME + timedelta(minutes=15),
    )

    result = end_focus_session_for_switch(
        pomodoro_session_repository,
        session.id,
        ended_at=START_TIME + timedelta(minutes=20),
        mode="complete",
    )

    assert result.ended_session.actual_duration_minutes == 15


def test_ending_focus_session_for_switch_returns_carry_over_information(
    pomodoro_session_repository: InMemoryPomodoroSessionRepository,
    task_repository: InMemoryTaskRepository,
) -> None:
    session = start_session(pomodoro_session_repository, task_repository)

    result = end_focus_session_for_switch(
        pomodoro_session_repository,
        session.id,
        ended_at=START_TIME + timedelta(minutes=15),
        mode="complete",
    )

    assert result.ended_session.id == session.id
    assert result.remaining_planned_minutes == 10
    assert result.has_meaningful_remaining_minutes is True


def test_ending_focus_session_for_switch_marks_zero_remaining_minutes_as_not_meaningful(
    pomodoro_session_repository: InMemoryPomodoroSessionRepository,
    task_repository: InMemoryTaskRepository,
) -> None:
    session = start_session(pomodoro_session_repository, task_repository)

    result = end_focus_session_for_switch(
        pomodoro_session_repository,
        session.id,
        ended_at=START_TIME + timedelta(minutes=25),
        mode="complete",
    )

    assert result.remaining_planned_minutes == 0
    assert result.has_meaningful_remaining_minutes is False


def test_ending_missing_session_for_switch_fails(
    pomodoro_session_repository: InMemoryPomodoroSessionRepository,
) -> None:
    with pytest.raises(InvalidPomodoroSessionError):
        end_focus_session_for_switch(
            pomodoro_session_repository,
            uuid4(),
            ended_at=START_TIME + timedelta(minutes=15),
            mode="complete",
        )


@pytest.mark.parametrize(
    "status",
    [PomodoroSessionStatus.COMPLETED, PomodoroSessionStatus.INTERRUPTED],
)
def test_ending_inactive_session_for_switch_fails(
    pomodoro_session_repository: InMemoryPomodoroSessionRepository,
    status: PomodoroSessionStatus,
) -> None:
    session = save_session(
        pomodoro_session_repository,
        PomodoroSession(
            type=PomodoroSessionType.FOCUS,
            status=status,
            planned_duration_minutes=25,
            started_at=START_TIME,
            created_at=START_TIME,
            updated_at=START_TIME,
            ended_at=START_TIME + timedelta(minutes=10),
            actual_duration_minutes=10,
        ),
    )

    with pytest.raises(InvalidPomodoroSessionError):
        end_focus_session_for_switch(
            pomodoro_session_repository,
            session.id,
            ended_at=START_TIME + timedelta(minutes=15),
            mode="complete",
        )


@pytest.mark.parametrize(
    "session_type",
    [PomodoroSessionType.SHORT_BREAK, PomodoroSessionType.LONG_BREAK],
)
def test_ending_break_session_for_switch_fails(
    pomodoro_session_repository: InMemoryPomodoroSessionRepository,
    session_type: PomodoroSessionType,
) -> None:
    session = save_session(
        pomodoro_session_repository,
        PomodoroSession(
            type=session_type,
            status=PomodoroSessionStatus.RUNNING,
            planned_duration_minutes=5,
            started_at=START_TIME,
            created_at=START_TIME,
            updated_at=START_TIME,
        ),
    )

    with pytest.raises(InvalidPomodoroSessionError):
        end_focus_session_for_switch(
            pomodoro_session_repository,
            session.id,
            ended_at=START_TIME + timedelta(minutes=2),
            mode="complete",
        )


def test_ending_focus_session_for_switch_rejects_invalid_mode(
    pomodoro_session_repository: InMemoryPomodoroSessionRepository,
    task_repository: InMemoryTaskRepository,
) -> None:
    session = start_session(pomodoro_session_repository, task_repository)

    with pytest.raises(InvalidPomodoroSessionError):
        end_focus_session_for_switch(
            pomodoro_session_repository,
            session.id,
            ended_at=START_TIME + timedelta(minutes=15),
            mode="skip",
        )


def test_starting_carried_over_focus_session_uses_remaining_minutes(
    pomodoro_session_repository: InMemoryPomodoroSessionRepository,
    task_repository: InMemoryTaskRepository,
) -> None:
    task = create_task_with_status(
        task_repository,
        TaskStatus.TODO,
        updated_at=START_TIME,
    )

    session = start_carried_over_focus_session(
        pomodoro_session_repository,
        task_repository,
        task_id=task.id,
        started_at=START_TIME + timedelta(minutes=15),
        remaining_planned_minutes=10,
    )

    assert session.type == PomodoroSessionType.FOCUS
    assert session.status == PomodoroSessionStatus.RUNNING
    assert session.task_id == task.id
    assert session.planned_duration_minutes == 10
    assert get_task(task_repository, task.id).status == TaskStatus.DOING


@pytest.mark.parametrize("remaining_minutes", [0, -1])
def test_starting_carried_over_focus_session_rejects_zero_or_negative_minutes(
    pomodoro_session_repository: InMemoryPomodoroSessionRepository,
    task_repository: InMemoryTaskRepository,
    remaining_minutes: int,
) -> None:
    task = create_task_with_status(
        task_repository,
        TaskStatus.TODO,
        updated_at=START_TIME,
    )

    with pytest.raises(InvalidPomodoroSessionError):
        start_carried_over_focus_session(
            pomodoro_session_repository,
            task_repository,
            task_id=task.id,
            started_at=START_TIME + timedelta(minutes=15),
            remaining_planned_minutes=remaining_minutes,
        )


def test_starting_carried_over_focus_session_rejects_missing_task(
    pomodoro_session_repository: InMemoryPomodoroSessionRepository,
    task_repository: InMemoryTaskRepository,
) -> None:
    with pytest.raises(InvalidPomodoroSessionError):
        start_carried_over_focus_session(
            pomodoro_session_repository,
            task_repository,
            task_id=uuid4(),
            started_at=START_TIME + timedelta(minutes=15),
            remaining_planned_minutes=10,
        )


def test_starting_carried_over_focus_session_rejects_archived_task(
    pomodoro_session_repository: InMemoryPomodoroSessionRepository,
    task_repository: InMemoryTaskRepository,
) -> None:
    task = create_task_with_status(
        task_repository,
        TaskStatus.ARCHIVED,
        updated_at=START_TIME,
    )

    with pytest.raises(InvalidPomodoroSessionError):
        start_carried_over_focus_session(
            pomodoro_session_repository,
            task_repository,
            task_id=task.id,
            started_at=START_TIME + timedelta(minutes=15),
            remaining_planned_minutes=10,
        )


def test_starting_carried_over_focus_session_rejects_existing_active_session(
    pomodoro_session_repository: InMemoryPomodoroSessionRepository,
    task_repository: InMemoryTaskRepository,
) -> None:
    task = create_task_with_status(
        task_repository,
        TaskStatus.TODO,
        updated_at=START_TIME,
    )
    start_session(pomodoro_session_repository, task_repository)

    with pytest.raises(InvalidPomodoroSessionError):
        start_carried_over_focus_session(
            pomodoro_session_repository,
            task_repository,
            task_id=task.id,
            started_at=START_TIME + timedelta(minutes=15),
            remaining_planned_minutes=10,
        )


def test_task_ownership_of_actual_minutes_is_preserved_when_switching(
    pomodoro_session_repository: InMemoryPomodoroSessionRepository,
    task_repository: InMemoryTaskRepository,
) -> None:
    first_task = create_task_with_status(
        task_repository,
        TaskStatus.TODO,
        updated_at=START_TIME,
    )
    second_task = create_task_with_status(
        task_repository,
        TaskStatus.TODO,
        updated_at=START_TIME,
    )
    first_session = start_session(
        pomodoro_session_repository,
        task_repository,
        task_id=first_task.id,
    )
    result = end_focus_session_for_switch(
        pomodoro_session_repository,
        first_session.id,
        ended_at=START_TIME + timedelta(minutes=15),
        mode="complete",
    )

    second_session = start_carried_over_focus_session(
        pomodoro_session_repository,
        task_repository,
        task_id=second_task.id,
        started_at=START_TIME + timedelta(minutes=15),
        remaining_planned_minutes=result.remaining_planned_minutes,
    )

    assert result.ended_session.task_id == first_task.id
    assert result.ended_session.actual_duration_minutes == 15
    assert second_session.task_id == second_task.id
    assert second_session.actual_duration_minutes is None


def test_completed_switch_segments_keep_minutes_attached_to_their_tasks(
    pomodoro_session_repository: InMemoryPomodoroSessionRepository,
    task_repository: InMemoryTaskRepository,
) -> None:
    first_task = create_task_with_status(
        task_repository,
        TaskStatus.TODO,
        updated_at=START_TIME,
    )
    second_task = create_task_with_status(
        task_repository,
        TaskStatus.TODO,
        updated_at=START_TIME,
    )
    first_session = start_session(
        pomodoro_session_repository,
        task_repository,
        task_id=first_task.id,
    )
    result = end_focus_session_for_switch(
        pomodoro_session_repository,
        first_session.id,
        ended_at=START_TIME + timedelta(minutes=15),
        mode="complete",
    )
    second_session = start_carried_over_focus_session(
        pomodoro_session_repository,
        task_repository,
        task_id=second_task.id,
        started_at=START_TIME + timedelta(minutes=15),
        remaining_planned_minutes=result.remaining_planned_minutes,
    )

    completed_second_session = complete_session(
        pomodoro_session_repository,
        second_session.id,
        ended_at=START_TIME + timedelta(minutes=25),
    )

    assert result.ended_session.task_id == first_task.id
    assert result.ended_session.actual_duration_minutes == 15
    assert completed_second_session.task_id == second_task.id
    assert completed_second_session.actual_duration_minutes == 10


def test_switching_does_not_reassign_original_session_to_target_task(
    pomodoro_session_repository: InMemoryPomodoroSessionRepository,
    task_repository: InMemoryTaskRepository,
) -> None:
    first_task = create_task_with_status(
        task_repository,
        TaskStatus.TODO,
        updated_at=START_TIME,
    )
    second_task = create_task_with_status(
        task_repository,
        TaskStatus.TODO,
        updated_at=START_TIME,
    )
    first_session = start_session(
        pomodoro_session_repository,
        task_repository,
        task_id=first_task.id,
    )

    end_focus_session_for_switch(
        pomodoro_session_repository,
        first_session.id,
        ended_at=START_TIME + timedelta(minutes=15),
        mode="complete",
    )
    start_carried_over_focus_session(
        pomodoro_session_repository,
        task_repository,
        task_id=second_task.id,
        started_at=START_TIME + timedelta(minutes=15),
        remaining_planned_minutes=10,
    )

    assert saved_session(pomodoro_session_repository, first_session).task_id == (
        first_task.id
    )


def test_switching_does_not_count_each_segment_as_a_full_pomodoro(
    pomodoro_session_repository: InMemoryPomodoroSessionRepository,
    task_repository: InMemoryTaskRepository,
) -> None:
    first_task = create_task_with_status(
        task_repository,
        TaskStatus.TODO,
        updated_at=START_TIME,
    )
    second_task = create_task_with_status(
        task_repository,
        TaskStatus.TODO,
        updated_at=START_TIME,
    )
    first_session = start_session(
        pomodoro_session_repository,
        task_repository,
        task_id=first_task.id,
    )
    result = end_focus_session_for_switch(
        pomodoro_session_repository,
        first_session.id,
        ended_at=START_TIME + timedelta(minutes=15),
        mode="complete",
    )
    second_session = start_carried_over_focus_session(
        pomodoro_session_repository,
        task_repository,
        task_id=second_task.id,
        started_at=START_TIME + timedelta(minutes=15),
        remaining_planned_minutes=result.remaining_planned_minutes,
    )
    complete_session(
        pomodoro_session_repository,
        second_session.id,
        ended_at=START_TIME + timedelta(minutes=25),
    )

    counted_minutes = sum(
        session.actual_duration_minutes or 0
        for session in pomodoro_session_repository.list()
        if session.type == PomodoroSessionType.FOCUS
        and session.status == PomodoroSessionStatus.COMPLETED
    )

    assert counted_minutes / 25 == 1


def test_interrupted_switch_segment_keeps_actual_minutes_on_original_task(
    pomodoro_session_repository: InMemoryPomodoroSessionRepository,
    task_repository: InMemoryTaskRepository,
) -> None:
    task = create_task_with_status(
        task_repository,
        TaskStatus.TODO,
        updated_at=START_TIME,
    )
    session = start_session(
        pomodoro_session_repository,
        task_repository,
        task_id=task.id,
    )

    result = end_focus_session_for_switch(
        pomodoro_session_repository,
        session.id,
        ended_at=START_TIME + timedelta(minutes=12),
        mode="interrupt",
    )

    assert result.ended_session.status == PomodoroSessionStatus.INTERRUPTED
    assert result.ended_session.task_id == task.id
    assert result.ended_session.actual_duration_minutes == 12
    assert result.remaining_planned_minutes == 13


def test_regular_full_pomodoro_can_be_started_instead_of_carry_over(
    pomodoro_session_repository: InMemoryPomodoroSessionRepository,
    task_repository: InMemoryTaskRepository,
) -> None:
    first_task = create_task_with_status(
        task_repository,
        TaskStatus.TODO,
        updated_at=START_TIME,
    )
    second_task = create_task_with_status(
        task_repository,
        TaskStatus.TODO,
        updated_at=START_TIME,
    )
    session = start_session(
        pomodoro_session_repository,
        task_repository,
        task_id=first_task.id,
    )
    result = end_focus_session_for_switch(
        pomodoro_session_repository,
        session.id,
        ended_at=START_TIME + timedelta(minutes=15),
        mode="complete",
    )

    regular_session = start_session(
        pomodoro_session_repository,
        task_repository,
        task_id=second_task.id,
        started_at=START_TIME + timedelta(minutes=15),
    )

    assert result.remaining_planned_minutes == 10
    assert regular_session.planned_duration_minutes == 25


def test_break_sessions_remain_unattached_to_tasks_during_switching_workflows(
    pomodoro_session_repository: InMemoryPomodoroSessionRepository,
    task_repository: InMemoryTaskRepository,
) -> None:
    break_session = start_session(
        pomodoro_session_repository,
        task_repository,
        session_type=PomodoroSessionType.SHORT_BREAK,
    )

    interrupted_break = interrupt_session(
        pomodoro_session_repository,
        break_session.id,
        ended_at=START_TIME + timedelta(minutes=2),
    )

    assert interrupted_break.task_id is None
    assert has_meaningful_task_switch_carry_over(interrupted_break) is False
