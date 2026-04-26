from __future__ import annotations

from dataclasses import replace
from datetime import UTC, date, datetime
from uuid import UUID, uuid4

import pytest

from tomatempo.application.use_cases import (
    BatchEditTasks,
    BatchTaskOperation,
    BatchTaskResult,
    InvalidBatchTaskEditError,
    normalize_batch_task_selection,
)
from tomatempo.domain.entities import Task
from tomatempo.domain.value_objects import TaskPriority, TaskStatus

from .conftest import (
    InMemoryProjectRepository,
    InMemoryTagRepository,
    InMemoryTaskRepository,
    InMemoryTaskTagRepository,
    attach_tags,
    create_project,
    create_task,
    get_task,
    list_task_tag_names,
)

BASE_TIME = datetime(2026, 5, 1, 9, 0, tzinfo=UTC)


def batch_edit(
    project_repository: InMemoryProjectRepository,
    task_repository: InMemoryTaskRepository,
    tag_repository: InMemoryTagRepository,
    task_tag_repository: InMemoryTaskTagRepository,
    task_ids: list[UUID],
    operation: BatchTaskOperation,
    include_archived: bool = False,
) -> BatchTaskResult:
    return BatchEditTasks(
        task_repository=task_repository,
        project_repository=project_repository,
        tag_repository=tag_repository,
        task_tag_repository=task_tag_repository,
    ).execute(
        task_ids=task_ids,
        operation=operation,
        include_archived=include_archived,
    )


def add_task(
    project_repository: InMemoryProjectRepository,
    task_repository: InMemoryTaskRepository,
    title: str,
    project_name: str = "Work",
    status: TaskStatus = TaskStatus.TODO,
    priority: TaskPriority = TaskPriority.NONE,
    due_date: date | None = None,
    updated_at: datetime = BASE_TIME,
) -> Task:
    project = project_repository.get_by_name(project_name)
    if project is None:
        project = create_project(project_repository, name=project_name)

    task = create_task(
        task_repository,
        project_repository,
        title=title,
        project_id=project.id,
    )
    return task_repository.save(
        replace(
            task,
            status=status,
            priority=priority,
            due_date=due_date,
            updated_at=updated_at,
            completed_at=BASE_TIME if status == TaskStatus.DONE else None,
            archived_at=BASE_TIME if status == TaskStatus.ARCHIVED else None,
        )
    )


def changed_titles(result: BatchTaskResult) -> list[str]:
    return [task.title for task in result.changed_tasks]


def error_codes(result: BatchTaskResult) -> list[str]:
    return [error.code for error in result.errors]


@pytest.mark.revised
def test_batch_editing_rejects_empty_task_selection() -> None:
    with pytest.raises(InvalidBatchTaskEditError):
        normalize_batch_task_selection([])


@pytest.mark.revised
def test_batch_editing_de_duplicates_task_ids() -> None:
    task_id = uuid4()

    selection = normalize_batch_task_selection([task_id, task_id])

    assert selection == [task_id]


@pytest.mark.revised
def test_batch_editing_preserves_first_seen_task_id_order() -> None:
    first_id = uuid4()
    second_id = uuid4()

    selection = normalize_batch_task_selection([second_id, first_id, second_id])

    assert selection == [second_id, first_id]


@pytest.mark.revised
def test_batch_editing_reports_missing_task_ids(
    project_repository: InMemoryProjectRepository,
    task_repository: InMemoryTaskRepository,
    tag_repository: InMemoryTagRepository,
    task_tag_repository: InMemoryTaskTagRepository,
) -> None:
    missing_task_id = uuid4()

    result = batch_edit(
        project_repository,
        task_repository,
        tag_repository,
        task_tag_repository,
        [missing_task_id],
        BatchTaskOperation.update_priority(TaskPriority.HIGH),
    )

    assert result.error_count == 1
    assert result.errors[0].task_id == missing_task_id
    assert error_codes(result) == ["missing_task"]


@pytest.mark.revised
def test_batch_editing_continues_after_missing_task_ids(
    project_repository: InMemoryProjectRepository,
    task_repository: InMemoryTaskRepository,
    tag_repository: InMemoryTagRepository,
    task_tag_repository: InMemoryTaskTagRepository,
) -> None:
    task = add_task(project_repository, task_repository, "Existing")

    result = batch_edit(
        project_repository,
        task_repository,
        tag_repository,
        task_tag_repository,
        [uuid4(), task.id],
        BatchTaskOperation.update_priority(TaskPriority.HIGH),
    )

    assert changed_titles(result) == ["Existing"]
    assert get_task(task_repository, task.id).priority == TaskPriority.HIGH


@pytest.mark.revised
def test_batch_editing_skips_archived_tasks_by_default(
    project_repository: InMemoryProjectRepository,
    task_repository: InMemoryTaskRepository,
    tag_repository: InMemoryTagRepository,
    task_tag_repository: InMemoryTaskTagRepository,
) -> None:
    task = add_task(
        project_repository,
        task_repository,
        "Archived",
        status=TaskStatus.ARCHIVED,
    )

    result = batch_edit(
        project_repository,
        task_repository,
        tag_repository,
        task_tag_repository,
        [task.id],
        BatchTaskOperation.update_priority(TaskPriority.HIGH),
    )

    assert error_codes(result) == ["archived_task"]
    assert get_task(task_repository, task.id).priority == TaskPriority.NONE


@pytest.mark.revised
def test_batch_editing_can_include_archived_tasks_when_explicitly_allowed(
    project_repository: InMemoryProjectRepository,
    task_repository: InMemoryTaskRepository,
    tag_repository: InMemoryTagRepository,
    task_tag_repository: InMemoryTaskTagRepository,
) -> None:
    task = add_task(
        project_repository,
        task_repository,
        "Archived",
        status=TaskStatus.ARCHIVED,
    )

    result = batch_edit(
        project_repository,
        task_repository,
        tag_repository,
        task_tag_repository,
        [task.id],
        BatchTaskOperation.update_priority(TaskPriority.HIGH),
        include_archived=True,
    )

    assert changed_titles(result) == ["Archived"]
    assert get_task(task_repository, task.id).priority == TaskPriority.HIGH


@pytest.mark.revised
def test_batch_updating_priority_changes_selected_tasks(
    project_repository: InMemoryProjectRepository,
    task_repository: InMemoryTaskRepository,
    tag_repository: InMemoryTagRepository,
    task_tag_repository: InMemoryTaskTagRepository,
) -> None:
    first = add_task(project_repository, task_repository, "First")
    second = add_task(project_repository, task_repository, "Second")

    result = batch_edit(
        project_repository,
        task_repository,
        tag_repository,
        task_tag_repository,
        [first.id, second.id],
        BatchTaskOperation.update_priority("high"),
    )

    assert changed_titles(result) == ["First", "Second"]
    assert get_task(task_repository, first.id).priority == TaskPriority.HIGH
    assert get_task(task_repository, second.id).priority == TaskPriority.HIGH


@pytest.mark.revised
def test_batch_updating_priority_reports_changed_count(
    project_repository: InMemoryProjectRepository,
    task_repository: InMemoryTaskRepository,
    tag_repository: InMemoryTagRepository,
    task_tag_repository: InMemoryTaskTagRepository,
) -> None:
    task = add_task(project_repository, task_repository, "Task")

    result = batch_edit(
        project_repository,
        task_repository,
        tag_repository,
        task_tag_repository,
        [task.id],
        BatchTaskOperation.update_priority(TaskPriority.HIGH),
    )

    assert result.changed_count == 1


@pytest.mark.revised
def test_batch_updating_priority_updates_task_updated_at(
    project_repository: InMemoryProjectRepository,
    task_repository: InMemoryTaskRepository,
    tag_repository: InMemoryTagRepository,
    task_tag_repository: InMemoryTaskTagRepository,
) -> None:
    task = add_task(project_repository, task_repository, "Task")

    batch_edit(
        project_repository,
        task_repository,
        tag_repository,
        task_tag_repository,
        [task.id],
        BatchTaskOperation.update_priority(TaskPriority.HIGH),
    )

    assert get_task(task_repository, task.id).updated_at > BASE_TIME


@pytest.mark.revised
def test_batch_updating_priority_leaves_matching_tasks_unchanged(
    project_repository: InMemoryProjectRepository,
    task_repository: InMemoryTaskRepository,
    tag_repository: InMemoryTagRepository,
    task_tag_repository: InMemoryTaskTagRepository,
) -> None:
    task = add_task(
        project_repository,
        task_repository,
        "Task",
        priority=TaskPriority.HIGH,
    )

    result = batch_edit(
        project_repository,
        task_repository,
        tag_repository,
        task_tag_repository,
        [task.id],
        BatchTaskOperation.update_priority(TaskPriority.HIGH),
    )

    assert result.unchanged_count == 1
    assert get_task(task_repository, task.id).updated_at == BASE_TIME


@pytest.mark.revised
def test_batch_updating_priority_rejects_invalid_priority(
    project_repository: InMemoryProjectRepository,
    task_repository: InMemoryTaskRepository,
    tag_repository: InMemoryTagRepository,
    task_tag_repository: InMemoryTaskTagRepository,
) -> None:
    task = add_task(project_repository, task_repository, "Task")

    with pytest.raises(InvalidBatchTaskEditError):
        batch_edit(
            project_repository,
            task_repository,
            tag_repository,
            task_tag_repository,
            [task.id],
            BatchTaskOperation.update_priority("urgent"),
        )

    assert get_task(task_repository, task.id).priority == TaskPriority.NONE


@pytest.mark.revised
def test_batch_updating_priority_does_not_modify_unselected_tasks(
    project_repository: InMemoryProjectRepository,
    task_repository: InMemoryTaskRepository,
    tag_repository: InMemoryTagRepository,
    task_tag_repository: InMemoryTaskTagRepository,
) -> None:
    selected = add_task(project_repository, task_repository, "Selected")
    unselected = add_task(project_repository, task_repository, "Unselected")

    batch_edit(
        project_repository,
        task_repository,
        tag_repository,
        task_tag_repository,
        [selected.id],
        BatchTaskOperation.update_priority(TaskPriority.HIGH),
    )

    assert get_task(task_repository, unselected.id).priority == TaskPriority.NONE


@pytest.mark.revised
def test_batch_updating_due_date_changes_selected_tasks(
    project_repository: InMemoryProjectRepository,
    task_repository: InMemoryTaskRepository,
    tag_repository: InMemoryTagRepository,
    task_tag_repository: InMemoryTaskTagRepository,
) -> None:
    task = add_task(project_repository, task_repository, "Task")
    due = date(2026, 5, 8)

    result = batch_edit(
        project_repository,
        task_repository,
        tag_repository,
        task_tag_repository,
        [task.id],
        BatchTaskOperation.update_due_date(due),
    )

    assert result.changed_count == 1
    assert get_task(task_repository, task.id).due_date == due
    assert get_task(task_repository, task.id).updated_at > BASE_TIME


def test_batch_updating_due_date_can_clear_due_dates(
    project_repository: InMemoryProjectRepository,
    task_repository: InMemoryTaskRepository,
    tag_repository: InMemoryTagRepository,
    task_tag_repository: InMemoryTaskTagRepository,
) -> None:
    task = add_task(
        project_repository,
        task_repository,
        "Task",
        due_date=date(2026, 5, 8),
    )

    batch_edit(
        project_repository,
        task_repository,
        tag_repository,
        task_tag_repository,
        [task.id],
        BatchTaskOperation.update_due_date(None),
    )

    assert get_task(task_repository, task.id).due_date is None


@pytest.mark.revised
def test_batch_updating_due_date_leaves_matching_tasks_unchanged(
    project_repository: InMemoryProjectRepository,
    task_repository: InMemoryTaskRepository,
    tag_repository: InMemoryTagRepository,
    task_tag_repository: InMemoryTaskTagRepository,
) -> None:
    due = date(2026, 5, 8)
    task = add_task(project_repository, task_repository, "Task", due_date=due)

    result = batch_edit(
        project_repository,
        task_repository,
        tag_repository,
        task_tag_repository,
        [task.id],
        BatchTaskOperation.update_due_date(due),
    )

    assert result.unchanged_count == 1
    assert get_task(task_repository, task.id).updated_at == BASE_TIME


@pytest.mark.revised
def test_batch_updating_due_date_does_not_modify_unselected_tasks(
    project_repository: InMemoryProjectRepository,
    task_repository: InMemoryTaskRepository,
    tag_repository: InMemoryTagRepository,
    task_tag_repository: InMemoryTaskTagRepository,
) -> None:
    selected = add_task(project_repository, task_repository, "Selected")
    unselected = add_task(project_repository, task_repository, "Unselected")

    batch_edit(
        project_repository,
        task_repository,
        tag_repository,
        task_tag_repository,
        [selected.id],
        BatchTaskOperation.update_due_date(date(2026, 5, 8)),
    )

    assert get_task(task_repository, unselected.id).due_date is None


@pytest.mark.revised
def test_batch_moving_tasks_moves_selected_tasks_to_target_project(
    project_repository: InMemoryProjectRepository,
    task_repository: InMemoryTaskRepository,
    tag_repository: InMemoryTagRepository,
    task_tag_repository: InMemoryTaskTagRepository,
) -> None:
    task = add_task(project_repository, task_repository, "Task", project_name="Work")
    target_project = create_project(project_repository, name="Personal")

    result = batch_edit(
        project_repository,
        task_repository,
        tag_repository,
        task_tag_repository,
        [task.id],
        BatchTaskOperation.move_to_project(target_project.id),
    )

    assert result.changed_count == 1
    assert get_task(task_repository, task.id).project_id == target_project.id
    assert get_task(task_repository, task.id).updated_at > BASE_TIME


@pytest.mark.revised
def test_batch_moving_tasks_rejects_missing_target_project(
    project_repository: InMemoryProjectRepository,
    task_repository: InMemoryTaskRepository,
    tag_repository: InMemoryTagRepository,
    task_tag_repository: InMemoryTaskTagRepository,
) -> None:
    task = add_task(project_repository, task_repository, "Task", project_name="Work")
    original_project_id = task.project_id

    with pytest.raises(InvalidBatchTaskEditError):
        batch_edit(
            project_repository,
            task_repository,
            tag_repository,
            task_tag_repository,
            [task.id],
            BatchTaskOperation.move_to_project(uuid4()),
        )

    assert get_task(task_repository, task.id).project_id == original_project_id


@pytest.mark.revised
def test_batch_moving_tasks_leaves_tasks_unchanged_when_already_in_target_project(
    project_repository: InMemoryProjectRepository,
    task_repository: InMemoryTaskRepository,
    tag_repository: InMemoryTagRepository,
    task_tag_repository: InMemoryTaskTagRepository,
) -> None:
    task = add_task(project_repository, task_repository, "Task", project_name="Work")

    result = batch_edit(
        project_repository,
        task_repository,
        tag_repository,
        task_tag_repository,
        [task.id],
        BatchTaskOperation.move_to_project(task.project_id),
    )

    assert result.unchanged_count == 1
    assert get_task(task_repository, task.id).updated_at == BASE_TIME


@pytest.mark.revised
def test_batch_moving_tasks_reports_duplicate_title_conflicts(
    project_repository: InMemoryProjectRepository,
    task_repository: InMemoryTaskRepository,
    tag_repository: InMemoryTagRepository,
    task_tag_repository: InMemoryTaskTagRepository,
) -> None:
    source_task = add_task(project_repository, task_repository, "Task", "Work")
    target_task = add_task(project_repository, task_repository, "Task", "Personal")

    result = batch_edit(
        project_repository,
        task_repository,
        tag_repository,
        task_tag_repository,
        [source_task.id],
        BatchTaskOperation.move_to_project(target_task.project_id),
    )

    assert error_codes(result) == ["duplicate_task_title"]
    assert (
        get_task(task_repository, source_task.id).project_id == source_task.project_id
    )


@pytest.mark.revised
def test_batch_moving_tasks_continues_after_duplicate_title_conflicts(
    project_repository: InMemoryProjectRepository,
    task_repository: InMemoryTaskRepository,
    tag_repository: InMemoryTagRepository,
    task_tag_repository: InMemoryTaskTagRepository,
) -> None:
    conflicting = add_task(project_repository, task_repository, "Same", "Work")
    movable = add_task(project_repository, task_repository, "Different", "Work")
    target_project = create_project(project_repository, name="Personal")
    add_task(project_repository, task_repository, "Same", "Personal")

    result = batch_edit(
        project_repository,
        task_repository,
        tag_repository,
        task_tag_repository,
        [conflicting.id, movable.id],
        BatchTaskOperation.move_to_project(target_project.id),
    )

    assert changed_titles(result) == ["Different"]
    assert error_codes(result) == ["duplicate_task_title"]


@pytest.mark.revised
def test_batch_moving_tasks_does_not_modify_unselected_tasks(
    project_repository: InMemoryProjectRepository,
    task_repository: InMemoryTaskRepository,
    tag_repository: InMemoryTagRepository,
    task_tag_repository: InMemoryTaskTagRepository,
) -> None:
    selected = add_task(project_repository, task_repository, "Selected", "Work")
    unselected = add_task(project_repository, task_repository, "Unselected", "Work")
    original_project_id = unselected.project_id
    target_project = create_project(project_repository, name="Personal")

    batch_edit(
        project_repository,
        task_repository,
        tag_repository,
        task_tag_repository,
        [selected.id],
        BatchTaskOperation.move_to_project(target_project.id),
    )

    assert get_task(task_repository, unselected.id).project_id == original_project_id


@pytest.mark.revised
def test_batch_attaching_tags_creates_missing_tags(
    project_repository: InMemoryProjectRepository,
    task_repository: InMemoryTaskRepository,
    tag_repository: InMemoryTagRepository,
    task_tag_repository: InMemoryTaskTagRepository,
) -> None:
    task = add_task(project_repository, task_repository, "Task")

    batch_edit(
        project_repository,
        task_repository,
        tag_repository,
        task_tag_repository,
        [task.id],
        BatchTaskOperation.attach_tags(["urgent"]),
    )

    assert tag_repository.get_by_name("urgent") is not None


@pytest.mark.revised
def test_batch_attaching_tags_reuses_existing_tags(
    project_repository: InMemoryProjectRepository,
    task_repository: InMemoryTaskRepository,
    tag_repository: InMemoryTagRepository,
    task_tag_repository: InMemoryTaskTagRepository,
) -> None:
    first = add_task(project_repository, task_repository, "First")
    second = add_task(project_repository, task_repository, "Second")

    batch_edit(
        project_repository,
        task_repository,
        tag_repository,
        task_tag_repository,
        [first.id, second.id],
        BatchTaskOperation.attach_tags(["urgent"]),
    )

    assert tag_repository.count() == 1


@pytest.mark.revised
def test_batch_attaching_tags_attaches_tags_to_each_selected_task(
    project_repository: InMemoryProjectRepository,
    task_repository: InMemoryTaskRepository,
    tag_repository: InMemoryTagRepository,
    task_tag_repository: InMemoryTaskTagRepository,
) -> None:
    first = add_task(project_repository, task_repository, "First")
    second = add_task(project_repository, task_repository, "Second")

    result = batch_edit(
        project_repository,
        task_repository,
        tag_repository,
        task_tag_repository,
        [first.id, second.id],
        BatchTaskOperation.attach_tags(["urgent"]),
    )

    assert result.changed_count == 2
    assert list_task_tag_names(first, tag_repository, task_tag_repository) == ["urgent"]
    assert list_task_tag_names(second, tag_repository, task_tag_repository) == [
        "urgent"
    ]
    assert get_task(task_repository, first.id).updated_at > BASE_TIME


@pytest.mark.revised
def test_batch_attaching_tags_normalizes_tag_names(
    project_repository: InMemoryProjectRepository,
    task_repository: InMemoryTaskRepository,
    tag_repository: InMemoryTagRepository,
    task_tag_repository: InMemoryTaskTagRepository,
) -> None:
    task = add_task(project_repository, task_repository, "Task")

    batch_edit(
        project_repository,
        task_repository,
        tag_repository,
        task_tag_repository,
        [task.id],
        BatchTaskOperation.attach_tags(["#Deep Work"]),
    )

    assert list_task_tag_names(task, tag_repository, task_tag_repository) == [
        "deep-work"
    ]


@pytest.mark.revised
def test_batch_attaching_tags_ignores_duplicate_tag_names(
    project_repository: InMemoryProjectRepository,
    task_repository: InMemoryTaskRepository,
    tag_repository: InMemoryTagRepository,
    task_tag_repository: InMemoryTaskTagRepository,
) -> None:
    task = add_task(project_repository, task_repository, "Task")

    batch_edit(
        project_repository,
        task_repository,
        tag_repository,
        task_tag_repository,
        [task.id],
        BatchTaskOperation.attach_tags(["urgent", "#URGENT"]),
    )

    assert task_tag_repository.count_for_task(task.id) == 1


@pytest.mark.revised
def test_batch_attaching_tags_leaves_tasks_unchanged_when_all_tags_already_attached(
    project_repository: InMemoryProjectRepository,
    task_repository: InMemoryTaskRepository,
    tag_repository: InMemoryTagRepository,
    task_tag_repository: InMemoryTaskTagRepository,
) -> None:
    task = add_task(project_repository, task_repository, "Task")
    attach_tags(
        task_repository,
        tag_repository,
        task_tag_repository,
        task,
        ["urgent"],
        updated_at=BASE_TIME,
    )

    result = batch_edit(
        project_repository,
        task_repository,
        tag_repository,
        task_tag_repository,
        [task.id],
        BatchTaskOperation.attach_tags(["urgent"]),
    )

    assert result.unchanged_count == 1
    assert get_task(task_repository, task.id).updated_at == BASE_TIME


@pytest.mark.revised
def test_batch_attaching_tags_does_not_modify_unselected_tasks(
    project_repository: InMemoryProjectRepository,
    task_repository: InMemoryTaskRepository,
    tag_repository: InMemoryTagRepository,
    task_tag_repository: InMemoryTaskTagRepository,
) -> None:
    selected = add_task(project_repository, task_repository, "Selected")
    unselected = add_task(project_repository, task_repository, "Unselected")

    batch_edit(
        project_repository,
        task_repository,
        tag_repository,
        task_tag_repository,
        [selected.id],
        BatchTaskOperation.attach_tags(["urgent"]),
    )

    assert list_task_tag_names(unselected, tag_repository, task_tag_repository) == []


@pytest.mark.revised
def test_batch_removing_tags_removes_matching_task_tag_relationships(
    project_repository: InMemoryProjectRepository,
    task_repository: InMemoryTaskRepository,
    tag_repository: InMemoryTagRepository,
    task_tag_repository: InMemoryTaskTagRepository,
) -> None:
    task = add_task(project_repository, task_repository, "Task")
    attach_tags(
        task_repository,
        tag_repository,
        task_tag_repository,
        task,
        ["urgent"],
        updated_at=BASE_TIME,
    )

    result = batch_edit(
        project_repository,
        task_repository,
        tag_repository,
        task_tag_repository,
        [task.id],
        BatchTaskOperation.remove_tags(["urgent"]),
    )

    assert result.changed_count == 1
    assert list_task_tag_names(task, tag_repository, task_tag_repository) == []
    assert get_task(task_repository, task.id).updated_at > BASE_TIME


@pytest.mark.revised
def test_batch_removing_tags_ignores_missing_tag_names(
    project_repository: InMemoryProjectRepository,
    task_repository: InMemoryTaskRepository,
    tag_repository: InMemoryTagRepository,
    task_tag_repository: InMemoryTaskTagRepository,
) -> None:
    task = add_task(project_repository, task_repository, "Task")

    result = batch_edit(
        project_repository,
        task_repository,
        tag_repository,
        task_tag_repository,
        [task.id],
        BatchTaskOperation.remove_tags(["missing"]),
    )

    assert result.unchanged_count == 1
    assert result.error_count == 0


@pytest.mark.revised
def test_batch_removing_tags_leaves_tasks_unchanged_when_no_requested_tags_are_attached(
    project_repository: InMemoryProjectRepository,
    task_repository: InMemoryTaskRepository,
    tag_repository: InMemoryTagRepository,
    task_tag_repository: InMemoryTaskTagRepository,
) -> None:
    task = add_task(project_repository, task_repository, "Task")
    attach_tags(
        task_repository,
        tag_repository,
        task_tag_repository,
        task,
        ["other"],
        updated_at=BASE_TIME,
    )

    result = batch_edit(
        project_repository,
        task_repository,
        tag_repository,
        task_tag_repository,
        [task.id],
        BatchTaskOperation.remove_tags(["urgent"]),
    )

    assert result.unchanged_count == 1
    assert get_task(task_repository, task.id).updated_at == BASE_TIME


@pytest.mark.revised
def test_batch_removing_tags_does_not_delete_tag_records(
    project_repository: InMemoryProjectRepository,
    task_repository: InMemoryTaskRepository,
    tag_repository: InMemoryTagRepository,
    task_tag_repository: InMemoryTaskTagRepository,
) -> None:
    task = add_task(project_repository, task_repository, "Task")
    attach_tags(
        task_repository,
        tag_repository,
        task_tag_repository,
        task,
        ["urgent"],
        updated_at=BASE_TIME,
    )

    batch_edit(
        project_repository,
        task_repository,
        tag_repository,
        task_tag_repository,
        [task.id],
        BatchTaskOperation.remove_tags(["urgent"]),
    )

    assert tag_repository.get_by_name("urgent") is not None


@pytest.mark.revised
def test_batch_removing_tags_does_not_modify_unselected_tasks(
    project_repository: InMemoryProjectRepository,
    task_repository: InMemoryTaskRepository,
    tag_repository: InMemoryTagRepository,
    task_tag_repository: InMemoryTaskTagRepository,
) -> None:
    selected = add_task(project_repository, task_repository, "Selected")
    unselected = add_task(project_repository, task_repository, "Unselected")
    attach_tags(
        task_repository,
        tag_repository,
        task_tag_repository,
        selected,
        ["urgent"],
        updated_at=BASE_TIME,
    )
    attach_tags(
        task_repository,
        tag_repository,
        task_tag_repository,
        unselected,
        ["urgent"],
        updated_at=BASE_TIME,
    )

    batch_edit(
        project_repository,
        task_repository,
        tag_repository,
        task_tag_repository,
        [selected.id],
        BatchTaskOperation.remove_tags(["urgent"]),
    )

    assert list_task_tag_names(unselected, tag_repository, task_tag_repository) == [
        "urgent"
    ]


@pytest.mark.revised
def test_batch_replacing_tags_replaces_each_selected_task_tag_set(
    project_repository: InMemoryProjectRepository,
    task_repository: InMemoryTaskRepository,
    tag_repository: InMemoryTagRepository,
    task_tag_repository: InMemoryTaskTagRepository,
) -> None:
    task = add_task(project_repository, task_repository, "Task")
    attach_tags(
        task_repository,
        tag_repository,
        task_tag_repository,
        task,
        ["old"],
        updated_at=BASE_TIME,
    )

    result = batch_edit(
        project_repository,
        task_repository,
        tag_repository,
        task_tag_repository,
        [task.id],
        BatchTaskOperation.replace_tags(["new"]),
    )

    assert result.changed_count == 1
    assert list_task_tag_names(task, tag_repository, task_tag_repository) == ["new"]
    assert get_task(task_repository, task.id).updated_at > BASE_TIME


@pytest.mark.revised
def test_batch_replacing_tags_creates_missing_tags(
    project_repository: InMemoryProjectRepository,
    task_repository: InMemoryTaskRepository,
    tag_repository: InMemoryTagRepository,
    task_tag_repository: InMemoryTaskTagRepository,
) -> None:
    task = add_task(project_repository, task_repository, "Task")

    batch_edit(
        project_repository,
        task_repository,
        tag_repository,
        task_tag_repository,
        [task.id],
        BatchTaskOperation.replace_tags(["new"]),
    )

    assert tag_repository.get_by_name("new") is not None


@pytest.mark.revised
def test_batch_replacing_tags_reuses_existing_tags(
    project_repository: InMemoryProjectRepository,
    task_repository: InMemoryTaskRepository,
    tag_repository: InMemoryTagRepository,
    task_tag_repository: InMemoryTaskTagRepository,
) -> None:
    first = add_task(project_repository, task_repository, "First")
    second = add_task(project_repository, task_repository, "Second")

    batch_edit(
        project_repository,
        task_repository,
        tag_repository,
        task_tag_repository,
        [first.id, second.id],
        BatchTaskOperation.replace_tags(["new"]),
    )

    assert tag_repository.count() == 1


@pytest.mark.revised
def test_batch_replacing_tags_normalizes_tag_names(
    project_repository: InMemoryProjectRepository,
    task_repository: InMemoryTaskRepository,
    tag_repository: InMemoryTagRepository,
    task_tag_repository: InMemoryTaskTagRepository,
) -> None:
    task = add_task(project_repository, task_repository, "Task")

    batch_edit(
        project_repository,
        task_repository,
        tag_repository,
        task_tag_repository,
        [task.id],
        BatchTaskOperation.replace_tags(["#Deep Work"]),
    )

    assert list_task_tag_names(task, tag_repository, task_tag_repository) == [
        "deep-work"
    ]


@pytest.mark.revised
def test_batch_replacing_tags_clears_tags_when_given_empty_tag_list(
    project_repository: InMemoryProjectRepository,
    task_repository: InMemoryTaskRepository,
    tag_repository: InMemoryTagRepository,
    task_tag_repository: InMemoryTaskTagRepository,
) -> None:
    task = add_task(project_repository, task_repository, "Task")
    attach_tags(
        task_repository,
        tag_repository,
        task_tag_repository,
        task,
        ["urgent"],
        updated_at=BASE_TIME,
    )

    batch_edit(
        project_repository,
        task_repository,
        tag_repository,
        task_tag_repository,
        [task.id],
        BatchTaskOperation.replace_tags([]),
    )

    assert list_task_tag_names(task, tag_repository, task_tag_repository) == []


@pytest.mark.revised
def test_batch_replacing_tags_leaves_tasks_unchanged_when_tag_sets_already_match(
    project_repository: InMemoryProjectRepository,
    task_repository: InMemoryTaskRepository,
    tag_repository: InMemoryTagRepository,
    task_tag_repository: InMemoryTaskTagRepository,
) -> None:
    task = add_task(project_repository, task_repository, "Task")
    attach_tags(
        task_repository,
        tag_repository,
        task_tag_repository,
        task,
        ["urgent"],
        updated_at=BASE_TIME,
    )

    result = batch_edit(
        project_repository,
        task_repository,
        tag_repository,
        task_tag_repository,
        [task.id],
        BatchTaskOperation.replace_tags(["urgent"]),
    )

    assert result.unchanged_count == 1
    assert get_task(task_repository, task.id).updated_at == BASE_TIME


@pytest.mark.revised
def test_batch_replacing_tags_does_not_modify_unselected_tasks(
    project_repository: InMemoryProjectRepository,
    task_repository: InMemoryTaskRepository,
    tag_repository: InMemoryTagRepository,
    task_tag_repository: InMemoryTaskTagRepository,
) -> None:
    selected = add_task(project_repository, task_repository, "Selected")
    unselected = add_task(project_repository, task_repository, "Unselected")
    attach_tags(
        task_repository,
        tag_repository,
        task_tag_repository,
        unselected,
        ["old"],
        updated_at=BASE_TIME,
    )

    batch_edit(
        project_repository,
        task_repository,
        tag_repository,
        task_tag_repository,
        [selected.id],
        BatchTaskOperation.replace_tags(["new"]),
    )

    assert list_task_tag_names(unselected, tag_repository, task_tag_repository) == [
        "old"
    ]


@pytest.mark.revised
def test_batch_completing_tasks_marks_selected_tasks_as_done(
    project_repository: InMemoryProjectRepository,
    task_repository: InMemoryTaskRepository,
    tag_repository: InMemoryTagRepository,
    task_tag_repository: InMemoryTaskTagRepository,
) -> None:
    task = add_task(project_repository, task_repository, "Task")

    result = batch_edit(
        project_repository,
        task_repository,
        tag_repository,
        task_tag_repository,
        [task.id],
        BatchTaskOperation.complete(),
    )

    updated_task = get_task(task_repository, task.id)
    assert result.changed_count == 1
    assert updated_task.status == TaskStatus.DONE
    assert updated_task.completed_at is not None
    assert updated_task.updated_at > BASE_TIME


@pytest.mark.revised
def test_batch_completing_tasks_leaves_already_done_tasks_unchanged(
    project_repository: InMemoryProjectRepository,
    task_repository: InMemoryTaskRepository,
    tag_repository: InMemoryTagRepository,
    task_tag_repository: InMemoryTaskTagRepository,
) -> None:
    task = add_task(project_repository, task_repository, "Task", status=TaskStatus.DONE)

    result = batch_edit(
        project_repository,
        task_repository,
        tag_repository,
        task_tag_repository,
        [task.id],
        BatchTaskOperation.complete(),
    )

    assert result.unchanged_count == 1
    assert get_task(task_repository, task.id).updated_at == BASE_TIME


@pytest.mark.revised
def test_batch_reopening_tasks_marks_selected_tasks_as_todo(
    project_repository: InMemoryProjectRepository,
    task_repository: InMemoryTaskRepository,
    tag_repository: InMemoryTagRepository,
    task_tag_repository: InMemoryTaskTagRepository,
) -> None:
    task = add_task(project_repository, task_repository, "Task", status=TaskStatus.DONE)

    result = batch_edit(
        project_repository,
        task_repository,
        tag_repository,
        task_tag_repository,
        [task.id],
        BatchTaskOperation.reopen(),
    )

    updated_task = get_task(task_repository, task.id)
    assert result.changed_count == 1
    assert updated_task.status == TaskStatus.TODO
    assert updated_task.completed_at is None
    assert updated_task.updated_at > BASE_TIME


@pytest.mark.revised
def test_batch_reopening_tasks_leaves_already_todo_tasks_unchanged(
    project_repository: InMemoryProjectRepository,
    task_repository: InMemoryTaskRepository,
    tag_repository: InMemoryTagRepository,
    task_tag_repository: InMemoryTaskTagRepository,
) -> None:
    task = add_task(project_repository, task_repository, "Task")

    result = batch_edit(
        project_repository,
        task_repository,
        tag_repository,
        task_tag_repository,
        [task.id],
        BatchTaskOperation.reopen(),
    )

    assert result.unchanged_count == 1
    assert get_task(task_repository, task.id).updated_at == BASE_TIME


@pytest.mark.revised
def test_batch_archiving_tasks_marks_selected_tasks_as_archived(
    project_repository: InMemoryProjectRepository,
    task_repository: InMemoryTaskRepository,
    tag_repository: InMemoryTagRepository,
    task_tag_repository: InMemoryTaskTagRepository,
) -> None:
    task = add_task(project_repository, task_repository, "Task")

    result = batch_edit(
        project_repository,
        task_repository,
        tag_repository,
        task_tag_repository,
        [task.id],
        BatchTaskOperation.archive(),
    )

    updated_task = get_task(task_repository, task.id)
    assert result.changed_count == 1
    assert updated_task.status == TaskStatus.ARCHIVED
    assert updated_task.archived_at is not None
    assert updated_task.updated_at > BASE_TIME


@pytest.mark.revised
def test_batch_archiving_tasks_leaves_already_archived_tasks_unchanged_when_allowed(
    project_repository: InMemoryProjectRepository,
    task_repository: InMemoryTaskRepository,
    tag_repository: InMemoryTagRepository,
    task_tag_repository: InMemoryTaskTagRepository,
) -> None:
    task = add_task(
        project_repository,
        task_repository,
        "Task",
        status=TaskStatus.ARCHIVED,
    )

    result = batch_edit(
        project_repository,
        task_repository,
        tag_repository,
        task_tag_repository,
        [task.id],
        BatchTaskOperation.archive(),
        include_archived=True,
    )

    assert result.unchanged_count == 1
    assert get_task(task_repository, task.id).updated_at == BASE_TIME


@pytest.mark.revised
def test_status_operations_do_not_modify_unselected_tasks(
    project_repository: InMemoryProjectRepository,
    task_repository: InMemoryTaskRepository,
    tag_repository: InMemoryTagRepository,
    task_tag_repository: InMemoryTaskTagRepository,
) -> None:
    selected = add_task(project_repository, task_repository, "Selected")
    unselected = add_task(project_repository, task_repository, "Unselected")

    batch_edit(
        project_repository,
        task_repository,
        tag_repository,
        task_tag_repository,
        [selected.id],
        BatchTaskOperation.complete(),
    )

    assert get_task(task_repository, unselected.id).status == TaskStatus.TODO


@pytest.mark.revised
def test_batch_result_reports_requested_count(
    project_repository: InMemoryProjectRepository,
    task_repository: InMemoryTaskRepository,
    tag_repository: InMemoryTagRepository,
    task_tag_repository: InMemoryTaskTagRepository,
) -> None:
    task = add_task(project_repository, task_repository, "Task")

    result = batch_edit(
        project_repository,
        task_repository,
        tag_repository,
        task_tag_repository,
        [task.id, task.id],
        BatchTaskOperation.update_priority(TaskPriority.HIGH),
    )

    assert result.requested_count == 1


@pytest.mark.revised
def test_batch_result_reports_unchanged_and_error_counts(
    project_repository: InMemoryProjectRepository,
    task_repository: InMemoryTaskRepository,
    tag_repository: InMemoryTagRepository,
    task_tag_repository: InMemoryTaskTagRepository,
) -> None:
    task = add_task(
        project_repository,
        task_repository,
        "Task",
        priority=TaskPriority.HIGH,
    )

    result = batch_edit(
        project_repository,
        task_repository,
        tag_repository,
        task_tag_repository,
        [task.id, uuid4()],
        BatchTaskOperation.update_priority(TaskPriority.HIGH),
    )

    assert result.changed_count == 0
    assert result.unchanged_count == 1
    assert result.error_count == 1


@pytest.mark.revised
def test_batch_result_includes_changed_tasks(
    project_repository: InMemoryProjectRepository,
    task_repository: InMemoryTaskRepository,
    tag_repository: InMemoryTagRepository,
    task_tag_repository: InMemoryTaskTagRepository,
) -> None:
    task = add_task(project_repository, task_repository, "Task")

    result = batch_edit(
        project_repository,
        task_repository,
        tag_repository,
        task_tag_repository,
        [task.id],
        BatchTaskOperation.update_priority(TaskPriority.HIGH),
    )

    assert result.changed_tasks[0].id == task.id


@pytest.mark.revised
def test_batch_result_includes_item_level_errors(
    project_repository: InMemoryProjectRepository,
    task_repository: InMemoryTaskRepository,
    tag_repository: InMemoryTagRepository,
    task_tag_repository: InMemoryTaskTagRepository,
) -> None:
    missing_task_id = uuid4()

    result = batch_edit(
        project_repository,
        task_repository,
        tag_repository,
        task_tag_repository,
        [missing_task_id],
        BatchTaskOperation.update_priority(TaskPriority.HIGH),
    )

    assert result.errors[0].task_id == missing_task_id
    assert result.errors[0].message


@pytest.mark.revised
def test_changed_tasks_are_returned_in_selected_task_order(
    project_repository: InMemoryProjectRepository,
    task_repository: InMemoryTaskRepository,
    tag_repository: InMemoryTagRepository,
    task_tag_repository: InMemoryTaskTagRepository,
) -> None:
    first = add_task(project_repository, task_repository, "First")
    second = add_task(project_repository, task_repository, "Second")

    result = batch_edit(
        project_repository,
        task_repository,
        tag_repository,
        task_tag_repository,
        [second.id, first.id],
        BatchTaskOperation.update_priority(TaskPriority.HIGH),
    )

    assert changed_titles(result) == ["Second", "First"]
