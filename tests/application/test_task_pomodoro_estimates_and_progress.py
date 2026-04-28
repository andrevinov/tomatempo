from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import pytest

from tomatempo.application.use_cases import (
    GetTaskPomodoroProgress,
    InvalidTaskPomodoroProgressError,
    ListTaskPomodoroProgress,
    TaskPomodoroProgressSummary,
    UpdateTaskPomodoroEstimate,
)
from tomatempo.domain.entities import PomodoroSession, Task
from tomatempo.domain.value_objects import (
    PomodoroSessionStatus,
    PomodoroSessionType,
)

from .conftest import (
    InMemoryPomodoroSessionRepository,
    InMemoryProjectRepository,
    InMemoryTaskRepository,
    create_task_with_updated_at,
    get_task,
)

BASE_TIME = datetime(2026, 5, 1, 9, 0, tzinfo=UTC)
UPDATED_TIME = datetime(2026, 5, 1, 10, 0, tzinfo=UTC)


def update_estimate(
    task_repository: InMemoryTaskRepository,
    task_id: UUID,
    estimated_pomodoros: int | None,
    updated_at: datetime = UPDATED_TIME,
) -> Task:
    return UpdateTaskPomodoroEstimate(task_repository).execute(
        task_id,
        estimated_pomodoros=estimated_pomodoros,
        updated_at=updated_at,
    )


def get_progress(
    task_repository: InMemoryTaskRepository,
    pomodoro_session_repository: InMemoryPomodoroSessionRepository,
    task_id: UUID,
) -> TaskPomodoroProgressSummary:
    return GetTaskPomodoroProgress(
        task_repository,
        pomodoro_session_repository,
    ).execute(task_id)


def list_progress(
    task_repository: InMemoryTaskRepository,
    pomodoro_session_repository: InMemoryPomodoroSessionRepository,
    task_ids: list[UUID],
) -> list[TaskPomodoroProgressSummary]:
    return ListTaskPomodoroProgress(
        task_repository,
        pomodoro_session_repository,
    ).execute(task_ids)


def add_session(
    pomodoro_session_repository: InMemoryPomodoroSessionRepository,
    task_id: UUID | None = None,
    session_type: PomodoroSessionType = PomodoroSessionType.FOCUS,
    status: PomodoroSessionStatus = PomodoroSessionStatus.COMPLETED,
    actual_duration_minutes: int | None = 25,
    started_at: datetime = BASE_TIME,
) -> PomodoroSession:
    ended_at = None
    if status in {
        PomodoroSessionStatus.COMPLETED,
        PomodoroSessionStatus.INTERRUPTED,
    }:
        ended_at = started_at + timedelta(minutes=actual_duration_minutes or 0)

    session = PomodoroSession(
        type=session_type,
        status=status,
        planned_duration_minutes=25,
        started_at=started_at,
        actual_duration_minutes=actual_duration_minutes,
        task_id=task_id,
        ended_at=ended_at,
    )
    return pomodoro_session_repository.save(session)


@pytest.mark.revised
def test_updating_task_estimate_stores_estimate_on_task(
    project_repository: InMemoryProjectRepository,
    task_repository: InMemoryTaskRepository,
) -> None:
    task = create_task_with_updated_at(
        task_repository,
        project_repository,
        updated_at=BASE_TIME,
    )

    update_estimate(task_repository, task.id, 3)

    assert get_task(task_repository, task.id).estimated_pomodoros == 3


@pytest.mark.revised
def test_updating_task_estimate_updates_task_updated_at(
    project_repository: InMemoryProjectRepository,
    task_repository: InMemoryTaskRepository,
) -> None:
    task = create_task_with_updated_at(
        task_repository,
        project_repository,
        updated_at=BASE_TIME,
    )

    update_estimate(task_repository, task.id, 2, updated_at=UPDATED_TIME)

    assert get_task(task_repository, task.id).updated_at == UPDATED_TIME


@pytest.mark.revised
def test_updating_task_estimate_returns_updated_task(
    project_repository: InMemoryProjectRepository,
    task_repository: InMemoryTaskRepository,
) -> None:
    task = create_task_with_updated_at(
        task_repository,
        project_repository,
        updated_at=BASE_TIME,
    )

    updated_task = update_estimate(task_repository, task.id, 4)

    assert updated_task.estimated_pomodoros == 4


@pytest.mark.revised
def test_updating_task_estimate_can_clear_estimate(
    project_repository: InMemoryProjectRepository,
    task_repository: InMemoryTaskRepository,
) -> None:
    task = create_task_with_updated_at(
        task_repository,
        project_repository,
        updated_at=BASE_TIME,
    )
    update_estimate(task_repository, task.id, 4)

    update_estimate(task_repository, task.id, None)

    assert get_task(task_repository, task.id).estimated_pomodoros is None


@pytest.mark.revised
def test_updating_task_estimate_leaves_matching_estimate_unchanged(
    project_repository: InMemoryProjectRepository,
    task_repository: InMemoryTaskRepository,
) -> None:
    task = create_task_with_updated_at(
        task_repository,
        project_repository,
        updated_at=BASE_TIME,
    )
    update_estimate(task_repository, task.id, 2, updated_at=BASE_TIME)

    update_estimate(task_repository, task.id, 2, updated_at=UPDATED_TIME)

    assert get_task(task_repository, task.id).updated_at == BASE_TIME


@pytest.mark.revised
def test_updating_missing_task_estimate_fails(
    task_repository: InMemoryTaskRepository,
) -> None:
    with pytest.raises(InvalidTaskPomodoroProgressError):
        update_estimate(task_repository, uuid4(), 2)


@pytest.mark.revised
@pytest.mark.parametrize("estimate", [0, -1])
def test_updating_task_estimate_rejects_zero_or_negative_values(
    project_repository: InMemoryProjectRepository,
    task_repository: InMemoryTaskRepository,
    estimate: int,
) -> None:
    task = create_task_with_updated_at(
        task_repository,
        project_repository,
        updated_at=BASE_TIME,
    )

    with pytest.raises(InvalidTaskPomodoroProgressError):
        update_estimate(task_repository, task.id, estimate)


@pytest.mark.revised
def test_completed_focus_sessions_count_toward_actual_focus_minutes(
    project_repository: InMemoryProjectRepository,
    task_repository: InMemoryTaskRepository,
    pomodoro_session_repository: InMemoryPomodoroSessionRepository,
) -> None:
    task = create_task_with_updated_at(
        task_repository,
        project_repository,
        updated_at=BASE_TIME,
    )
    add_session(pomodoro_session_repository, task.id)

    progress = get_progress(task_repository, pomodoro_session_repository, task.id)

    assert progress.actual_focus_minutes == 25


@pytest.mark.revised
def test_interrupted_focus_sessions_count_toward_actual_focus_minutes(
    project_repository: InMemoryProjectRepository,
    task_repository: InMemoryTaskRepository,
    pomodoro_session_repository: InMemoryPomodoroSessionRepository,
) -> None:
    task = create_task_with_updated_at(
        task_repository,
        project_repository,
        updated_at=BASE_TIME,
    )
    add_session(
        pomodoro_session_repository,
        task.id,
        status=PomodoroSessionStatus.INTERRUPTED,
        actual_duration_minutes=12,
    )

    progress = get_progress(task_repository, pomodoro_session_repository, task.id)

    assert progress.actual_focus_minutes == 12


@pytest.mark.revised
def test_partial_focus_sessions_count_toward_actual_focus_minutes(
    project_repository: InMemoryProjectRepository,
    task_repository: InMemoryTaskRepository,
    pomodoro_session_repository: InMemoryPomodoroSessionRepository,
) -> None:
    task = create_task_with_updated_at(
        task_repository,
        project_repository,
        updated_at=BASE_TIME,
    )
    add_session(pomodoro_session_repository, task.id, actual_duration_minutes=10)

    progress = get_progress(task_repository, pomodoro_session_repository, task.id)

    assert progress.actual_focus_minutes == 10


@pytest.mark.revised
def test_multiple_sessions_for_same_task_are_summed(
    project_repository: InMemoryProjectRepository,
    task_repository: InMemoryTaskRepository,
    pomodoro_session_repository: InMemoryPomodoroSessionRepository,
) -> None:
    task = create_task_with_updated_at(
        task_repository,
        project_repository,
        updated_at=BASE_TIME,
    )
    add_session(pomodoro_session_repository, task.id, actual_duration_minutes=25)
    add_session(pomodoro_session_repository, task.id, actual_duration_minutes=15)

    progress = get_progress(task_repository, pomodoro_session_repository, task.id)

    assert progress.actual_focus_minutes == 40


@pytest.mark.revised
def test_sessions_for_other_tasks_do_not_count(
    project_repository: InMemoryProjectRepository,
    task_repository: InMemoryTaskRepository,
    pomodoro_session_repository: InMemoryPomodoroSessionRepository,
) -> None:
    task = create_task_with_updated_at(
        task_repository,
        project_repository,
        title="Current task",
        updated_at=BASE_TIME,
    )
    other_task = create_task_with_updated_at(
        task_repository,
        project_repository,
        title="Other task",
        updated_at=BASE_TIME,
    )
    add_session(pomodoro_session_repository, other_task.id)

    progress = get_progress(task_repository, pomodoro_session_repository, task.id)

    assert progress.actual_focus_minutes == 0


@pytest.mark.revised
def test_focus_sessions_without_task_do_not_count(
    project_repository: InMemoryProjectRepository,
    task_repository: InMemoryTaskRepository,
    pomodoro_session_repository: InMemoryPomodoroSessionRepository,
) -> None:
    task = create_task_with_updated_at(
        task_repository,
        project_repository,
        updated_at=BASE_TIME,
    )
    add_session(pomodoro_session_repository, task_id=None)

    progress = get_progress(task_repository, pomodoro_session_repository, task.id)

    assert progress.actual_focus_minutes == 0


@pytest.mark.revised
@pytest.mark.parametrize(
    "session_type",
    [PomodoroSessionType.SHORT_BREAK, PomodoroSessionType.LONG_BREAK],
)
def test_break_sessions_do_not_count(
    project_repository: InMemoryProjectRepository,
    task_repository: InMemoryTaskRepository,
    pomodoro_session_repository: InMemoryPomodoroSessionRepository,
    session_type: PomodoroSessionType,
) -> None:
    task = create_task_with_updated_at(
        task_repository,
        project_repository,
        updated_at=BASE_TIME,
    )
    add_session(
        pomodoro_session_repository,
        task.id,
        session_type=session_type,
        actual_duration_minutes=5,
    )

    progress = get_progress(task_repository, pomodoro_session_repository, task.id)

    assert progress.actual_focus_minutes == 0


@pytest.mark.revised
@pytest.mark.parametrize(
    "status",
    [
        PomodoroSessionStatus.RUNNING,
        PomodoroSessionStatus.PAUSED,
        PomodoroSessionStatus.PLANNED,
    ],
)
def test_active_or_planned_sessions_do_not_count(
    project_repository: InMemoryProjectRepository,
    task_repository: InMemoryTaskRepository,
    pomodoro_session_repository: InMemoryPomodoroSessionRepository,
    status: PomodoroSessionStatus,
) -> None:
    task = create_task_with_updated_at(
        task_repository,
        project_repository,
        updated_at=BASE_TIME,
    )
    add_session(
        pomodoro_session_repository,
        task.id,
        status=status,
        actual_duration_minutes=10,
    )

    progress = get_progress(task_repository, pomodoro_session_repository, task.id)

    assert progress.actual_focus_minutes == 0


@pytest.mark.revised
def test_sessions_without_actual_duration_do_not_count(
    project_repository: InMemoryProjectRepository,
    task_repository: InMemoryTaskRepository,
    pomodoro_session_repository: InMemoryPomodoroSessionRepository,
) -> None:
    task = create_task_with_updated_at(
        task_repository,
        project_repository,
        updated_at=BASE_TIME,
    )
    add_session(
        pomodoro_session_repository,
        task.id,
        actual_duration_minutes=None,
    )

    progress = get_progress(task_repository, pomodoro_session_repository, task.id)

    assert progress.actual_focus_minutes == 0


@pytest.mark.revised
def test_progress_summary_includes_task(
    project_repository: InMemoryProjectRepository,
    task_repository: InMemoryTaskRepository,
    pomodoro_session_repository: InMemoryPomodoroSessionRepository,
) -> None:
    task = create_task_with_updated_at(
        task_repository,
        project_repository,
        updated_at=BASE_TIME,
    )

    progress = get_progress(task_repository, pomodoro_session_repository, task.id)

    assert progress.task == task


@pytest.mark.revised
def test_progress_summary_includes_estimated_pomodoros(
    project_repository: InMemoryProjectRepository,
    task_repository: InMemoryTaskRepository,
    pomodoro_session_repository: InMemoryPomodoroSessionRepository,
) -> None:
    task = create_task_with_updated_at(
        task_repository,
        project_repository,
        updated_at=BASE_TIME,
    )
    update_estimate(task_repository, task.id, 3)

    progress = get_progress(task_repository, pomodoro_session_repository, task.id)

    assert progress.estimated_pomodoros == 3


@pytest.mark.revised
def test_progress_summary_calculates_estimated_minutes(
    project_repository: InMemoryProjectRepository,
    task_repository: InMemoryTaskRepository,
    pomodoro_session_repository: InMemoryPomodoroSessionRepository,
) -> None:
    task = create_task_with_updated_at(
        task_repository,
        project_repository,
        updated_at=BASE_TIME,
    )
    update_estimate(task_repository, task.id, 3)

    progress = get_progress(task_repository, pomodoro_session_repository, task.id)

    assert progress.estimated_minutes == 75


@pytest.mark.revised
def test_progress_summary_calculates_actual_focus_minutes(
    project_repository: InMemoryProjectRepository,
    task_repository: InMemoryTaskRepository,
    pomodoro_session_repository: InMemoryPomodoroSessionRepository,
) -> None:
    task = create_task_with_updated_at(
        task_repository,
        project_repository,
        updated_at=BASE_TIME,
    )
    add_session(pomodoro_session_repository, task.id, actual_duration_minutes=35)

    progress = get_progress(task_repository, pomodoro_session_repository, task.id)

    assert progress.actual_focus_minutes == 35


@pytest.mark.revised
def test_progress_summary_calculates_actual_pomodoro_equivalents(
    project_repository: InMemoryProjectRepository,
    task_repository: InMemoryTaskRepository,
    pomodoro_session_repository: InMemoryPomodoroSessionRepository,
) -> None:
    task = create_task_with_updated_at(
        task_repository,
        project_repository,
        updated_at=BASE_TIME,
    )
    add_session(pomodoro_session_repository, task.id, actual_duration_minutes=10)

    progress = get_progress(task_repository, pomodoro_session_repository, task.id)

    assert progress.actual_pomodoro_equivalents == pytest.approx(0.4)


@pytest.mark.revised
def test_progress_summary_returns_zero_actual_equivalents_when_no_sessions_count(
    project_repository: InMemoryProjectRepository,
    task_repository: InMemoryTaskRepository,
    pomodoro_session_repository: InMemoryPomodoroSessionRepository,
) -> None:
    task = create_task_with_updated_at(
        task_repository,
        project_repository,
        updated_at=BASE_TIME,
    )

    progress = get_progress(task_repository, pomodoro_session_repository, task.id)

    assert progress.actual_pomodoro_equivalents == 0


@pytest.mark.revised
def test_progress_summary_calculates_remaining_estimated_minutes(
    project_repository: InMemoryProjectRepository,
    task_repository: InMemoryTaskRepository,
    pomodoro_session_repository: InMemoryPomodoroSessionRepository,
) -> None:
    task = create_task_with_updated_at(
        task_repository,
        project_repository,
        updated_at=BASE_TIME,
    )
    update_estimate(task_repository, task.id, 2)
    add_session(pomodoro_session_repository, task.id, actual_duration_minutes=15)

    progress = get_progress(task_repository, pomodoro_session_repository, task.id)

    assert progress.remaining_estimated_minutes == 35


@pytest.mark.revised
def test_progress_summary_never_returns_negative_remaining_estimated_minutes(
    project_repository: InMemoryProjectRepository,
    task_repository: InMemoryTaskRepository,
    pomodoro_session_repository: InMemoryPomodoroSessionRepository,
) -> None:
    task = create_task_with_updated_at(
        task_repository,
        project_repository,
        updated_at=BASE_TIME,
    )
    update_estimate(task_repository, task.id, 1)
    add_session(pomodoro_session_repository, task.id, actual_duration_minutes=40)

    progress = get_progress(task_repository, pomodoro_session_repository, task.id)

    assert progress.remaining_estimated_minutes == 0


@pytest.mark.revised
def test_progress_summary_marks_estimate_as_exceeded_when_actual_exceeds_estimate(
    project_repository: InMemoryProjectRepository,
    task_repository: InMemoryTaskRepository,
    pomodoro_session_repository: InMemoryPomodoroSessionRepository,
) -> None:
    task = create_task_with_updated_at(
        task_repository,
        project_repository,
        updated_at=BASE_TIME,
    )
    update_estimate(task_repository, task.id, 1)
    add_session(pomodoro_session_repository, task.id, actual_duration_minutes=26)

    progress = get_progress(task_repository, pomodoro_session_repository, task.id)

    assert progress.estimate_exceeded is True


@pytest.mark.revised
def test_progress_summary_does_not_exceed_when_actual_equals_estimate(
    project_repository: InMemoryProjectRepository,
    task_repository: InMemoryTaskRepository,
    pomodoro_session_repository: InMemoryPomodoroSessionRepository,
) -> None:
    task = create_task_with_updated_at(
        task_repository,
        project_repository,
        updated_at=BASE_TIME,
    )
    update_estimate(task_repository, task.id, 1)
    add_session(pomodoro_session_repository, task.id, actual_duration_minutes=25)

    progress = get_progress(task_repository, pomodoro_session_repository, task.id)

    assert progress.estimate_exceeded is False


@pytest.mark.revised
def test_progress_summary_does_not_mark_estimate_as_exceeded_without_estimate(
    project_repository: InMemoryProjectRepository,
    task_repository: InMemoryTaskRepository,
    pomodoro_session_repository: InMemoryPomodoroSessionRepository,
) -> None:
    task = create_task_with_updated_at(
        task_repository,
        project_repository,
        updated_at=BASE_TIME,
    )
    add_session(pomodoro_session_repository, task.id, actual_duration_minutes=50)

    progress = get_progress(task_repository, pomodoro_session_repository, task.id)

    assert progress.estimate_exceeded is False


@pytest.mark.revised
def test_progress_summary_handles_tasks_without_estimates(
    project_repository: InMemoryProjectRepository,
    task_repository: InMemoryTaskRepository,
    pomodoro_session_repository: InMemoryPomodoroSessionRepository,
) -> None:
    task = create_task_with_updated_at(
        task_repository,
        project_repository,
        updated_at=BASE_TIME,
    )
    add_session(pomodoro_session_repository, task.id, actual_duration_minutes=10)

    progress = get_progress(task_repository, pomodoro_session_repository, task.id)

    assert progress.estimated_pomodoros is None
    assert progress.estimated_minutes is None
    assert progress.remaining_estimated_minutes is None
    assert progress.actual_focus_minutes == 10


@pytest.mark.revised
def test_progress_summary_rejects_missing_task(
    task_repository: InMemoryTaskRepository,
    pomodoro_session_repository: InMemoryPomodoroSessionRepository,
) -> None:
    with pytest.raises(InvalidTaskPomodoroProgressError):
        get_progress(task_repository, pomodoro_session_repository, uuid4())


@pytest.mark.revised
def test_listing_task_progress_returns_one_summary_per_selected_task(
    project_repository: InMemoryProjectRepository,
    task_repository: InMemoryTaskRepository,
    pomodoro_session_repository: InMemoryPomodoroSessionRepository,
) -> None:
    first_task = create_task_with_updated_at(
        task_repository,
        project_repository,
        title="First",
        updated_at=BASE_TIME,
    )
    second_task = create_task_with_updated_at(
        task_repository,
        project_repository,
        title="Second",
        updated_at=BASE_TIME,
    )

    summaries = list_progress(
        task_repository,
        pomodoro_session_repository,
        [first_task.id, second_task.id],
    )

    assert len(summaries) == 2


@pytest.mark.revised
def test_listing_task_progress_preserves_first_seen_task_id_order(
    project_repository: InMemoryProjectRepository,
    task_repository: InMemoryTaskRepository,
    pomodoro_session_repository: InMemoryPomodoroSessionRepository,
) -> None:
    first_task = create_task_with_updated_at(
        task_repository,
        project_repository,
        title="First",
        updated_at=BASE_TIME,
    )
    second_task = create_task_with_updated_at(
        task_repository,
        project_repository,
        title="Second",
        updated_at=BASE_TIME,
    )

    summaries = list_progress(
        task_repository,
        pomodoro_session_repository,
        [second_task.id, first_task.id],
    )

    assert [summary.task.id for summary in summaries] == [second_task.id, first_task.id]


@pytest.mark.revised
def test_listing_task_progress_ignores_duplicate_task_ids(
    project_repository: InMemoryProjectRepository,
    task_repository: InMemoryTaskRepository,
    pomodoro_session_repository: InMemoryPomodoroSessionRepository,
) -> None:
    task = create_task_with_updated_at(
        task_repository,
        project_repository,
        updated_at=BASE_TIME,
    )

    summaries = list_progress(
        task_repository,
        pomodoro_session_repository,
        [task.id, task.id],
    )

    assert [summary.task.id for summary in summaries] == [task.id]


@pytest.mark.revised
def test_listing_task_progress_rejects_empty_selections(
    task_repository: InMemoryTaskRepository,
    pomodoro_session_repository: InMemoryPomodoroSessionRepository,
) -> None:
    with pytest.raises(InvalidTaskPomodoroProgressError):
        list_progress(task_repository, pomodoro_session_repository, [])


@pytest.mark.revised
def test_listing_task_progress_rejects_missing_task_ids(
    task_repository: InMemoryTaskRepository,
    pomodoro_session_repository: InMemoryPomodoroSessionRepository,
) -> None:
    with pytest.raises(InvalidTaskPomodoroProgressError):
        list_progress(task_repository, pomodoro_session_repository, [uuid4()])


@pytest.mark.revised
def test_listing_task_progress_calculates_each_task_independently(
    project_repository: InMemoryProjectRepository,
    task_repository: InMemoryTaskRepository,
    pomodoro_session_repository: InMemoryPomodoroSessionRepository,
) -> None:
    first_task = create_task_with_updated_at(
        task_repository,
        project_repository,
        title="First",
        updated_at=BASE_TIME,
    )
    second_task = create_task_with_updated_at(
        task_repository,
        project_repository,
        title="Second",
        updated_at=BASE_TIME,
    )
    update_estimate(task_repository, first_task.id, 1)
    update_estimate(task_repository, second_task.id, 2)
    add_session(pomodoro_session_repository, first_task.id, actual_duration_minutes=10)
    add_session(pomodoro_session_repository, second_task.id, actual_duration_minutes=40)

    summaries = list_progress(
        task_repository,
        pomodoro_session_repository,
        [first_task.id, second_task.id],
    )

    assert [summary.actual_focus_minutes for summary in summaries] == [10, 40]
    assert [summary.remaining_estimated_minutes for summary in summaries] == [15, 10]
