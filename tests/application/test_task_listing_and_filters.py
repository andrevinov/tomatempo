from __future__ import annotations

from dataclasses import replace
from datetime import UTC, date, datetime, timedelta
from uuid import uuid4

import pytest

from tomatempo.application.use_cases import (
    BuildTaskListItem,
    InvalidTaskListFilterError,
    ListTasks,
    TaskListFilters,
    TaskListResult,
    TaskSort,
    normalize_task_list_filters,
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
    get_or_create_project,
)

BASE_TIME = datetime(2026, 5, 1, 9, 0, tzinfo=UTC)


def list_tasks(
    project_repository: InMemoryProjectRepository,
    task_repository: InMemoryTaskRepository,
    tag_repository: InMemoryTagRepository,
    task_tag_repository: InMemoryTaskTagRepository,
    filters: TaskListFilters | None = None,
    sort: TaskSort | None = None,
) -> TaskListResult:
    return ListTasks(
        task_repository=task_repository,
        project_repository=project_repository,
        tag_repository=tag_repository,
        task_tag_repository=task_tag_repository,
    ).execute(filters=filters, sort=sort)


def task_titles(result: TaskListResult) -> list[str]:
    return [item.task.title for item in result.items]


def add_task(
    project_repository: InMemoryProjectRepository,
    task_repository: InMemoryTaskRepository,
    tag_repository: InMemoryTagRepository,
    task_tag_repository: InMemoryTaskTagRepository,
    title: str,
    project_name: str = "Work",
    status: TaskStatus = TaskStatus.TODO,
    priority: TaskPriority = TaskPriority.NONE,
    due_date: date | None = None,
    description: str | None = None,
    tags: list[str] | None = None,
    sort_order: int | None = None,
    created_at: datetime | None = None,
    updated_at: datetime | None = None,
) -> Task:
    project = get_or_create_project(project_repository, project_name)
    created_task = Task(title=title, project_id=project.id)
    task = replace(
        created_task,
        status=status,
        priority=priority,
        due_date=due_date,
        description=description,
        sort_order=sort_order,
        created_at=created_at or created_task.created_at,
        updated_at=updated_at or created_task.updated_at,
    )
    task = task_repository.save(task)
    if tags:
        task = attach_tags(
            task_repository,
            tag_repository,
            task_tag_repository,
            task,
            tags,
        )
    return task


@pytest.mark.revised
def test_listing_tasks_returns_all_non_archived_tasks_by_default(
    project_repository: InMemoryProjectRepository,
    task_repository: InMemoryTaskRepository,
    tag_repository: InMemoryTagRepository,
    task_tag_repository: InMemoryTaskTagRepository,
) -> None:
    add_task(
        project_repository, task_repository, tag_repository, task_tag_repository, "A"
    )
    add_task(
        project_repository, task_repository, tag_repository, task_tag_repository, "B"
    )
    add_task(
        project_repository,
        task_repository,
        tag_repository,
        task_tag_repository,
        "Archived",
        status=TaskStatus.ARCHIVED,
    )

    result = list_tasks(
        project_repository,
        task_repository,
        tag_repository,
        task_tag_repository,
    )

    assert task_titles(result) == ["A", "B"]


@pytest.mark.revised
def test_listing_tasks_excludes_archived_tasks_by_default(
    project_repository: InMemoryProjectRepository,
    task_repository: InMemoryTaskRepository,
    tag_repository: InMemoryTagRepository,
    task_tag_repository: InMemoryTaskTagRepository,
) -> None:
    add_task(
        project_repository,
        task_repository,
        tag_repository,
        task_tag_repository,
        "Archived",
        status=TaskStatus.ARCHIVED,
    )

    result = list_tasks(
        project_repository,
        task_repository,
        tag_repository,
        task_tag_repository,
    )

    assert result.items == []


@pytest.mark.revised
def test_listing_tasks_can_include_archived_tasks_when_requested(
    project_repository: InMemoryProjectRepository,
    task_repository: InMemoryTaskRepository,
    tag_repository: InMemoryTagRepository,
    task_tag_repository: InMemoryTaskTagRepository,
) -> None:
    add_task(
        project_repository,
        task_repository,
        tag_repository,
        task_tag_repository,
        "Archived",
        status=TaskStatus.ARCHIVED,
    )

    result = list_tasks(
        project_repository,
        task_repository,
        tag_repository,
        task_tag_repository,
        filters=TaskListFilters(include_archived=True),
    )

    assert task_titles(result) == ["Archived"]


@pytest.mark.revised
def test_listing_tasks_returns_task_list_items(
    project_repository: InMemoryProjectRepository,
    task_repository: InMemoryTaskRepository,
    tag_repository: InMemoryTagRepository,
    task_tag_repository: InMemoryTaskTagRepository,
) -> None:
    add_task(
        project_repository, task_repository, tag_repository, task_tag_repository, "A"
    )

    result = list_tasks(
        project_repository,
        task_repository,
        tag_repository,
        task_tag_repository,
    )

    assert result.items[0].task.title == "A"
    assert result.items[0].project.name == "Work"
    assert result.items[0].tags == []


@pytest.mark.revised
def test_task_list_items_include_the_task(
    project_repository: InMemoryProjectRepository,
    task_repository: InMemoryTaskRepository,
    tag_repository: InMemoryTagRepository,
    task_tag_repository: InMemoryTaskTagRepository,
) -> None:
    task = add_task(
        project_repository,
        task_repository,
        tag_repository,
        task_tag_repository,
        "A",
    )

    item = BuildTaskListItem(
        project_repository,
        tag_repository,
        task_tag_repository,
    ).execute(task)

    assert item.task == task


@pytest.mark.revised
def test_task_list_items_include_the_task_project(
    project_repository: InMemoryProjectRepository,
    task_repository: InMemoryTaskRepository,
    tag_repository: InMemoryTagRepository,
    task_tag_repository: InMemoryTaskTagRepository,
) -> None:
    task = add_task(
        project_repository,
        task_repository,
        tag_repository,
        task_tag_repository,
        "A",
        project_name="English",
    )

    item = BuildTaskListItem(
        project_repository,
        tag_repository,
        task_tag_repository,
    ).execute(task)

    assert item.project.name == "English"


def test_task_list_items_include_attached_tags(
    project_repository: InMemoryProjectRepository,
    task_repository: InMemoryTaskRepository,
    tag_repository: InMemoryTagRepository,
    task_tag_repository: InMemoryTaskTagRepository,
) -> None:
    task = add_task(
        project_repository,
        task_repository,
        tag_repository,
        task_tag_repository,
        "A",
        tags=["urgent"],
    )

    item = BuildTaskListItem(
        project_repository,
        tag_repository,
        task_tag_repository,
    ).execute(task)

    assert [tag.name for tag in item.tags] == ["urgent"]


@pytest.mark.revised
def test_task_list_item_tags_are_sorted_alphabetically(
    project_repository: InMemoryProjectRepository,
    task_repository: InMemoryTaskRepository,
    tag_repository: InMemoryTagRepository,
    task_tag_repository: InMemoryTaskTagRepository,
) -> None:
    task = add_task(
        project_repository,
        task_repository,
        tag_repository,
        task_tag_repository,
        "A",
        tags=["urgent", "coding", "review"],
    )

    item = BuildTaskListItem(
        project_repository,
        tag_repository,
        task_tag_repository,
    ).execute(task)

    assert [tag.name for tag in item.tags] == ["coding", "review", "urgent"]


@pytest.mark.revised
def test_listing_tasks_reports_total_count(
    project_repository: InMemoryProjectRepository,
    task_repository: InMemoryTaskRepository,
    tag_repository: InMemoryTagRepository,
    task_tag_repository: InMemoryTaskTagRepository,
) -> None:
    add_task(
        project_repository, task_repository, tag_repository, task_tag_repository, "A"
    )
    add_task(
        project_repository, task_repository, tag_repository, task_tag_repository, "B"
    )

    result = list_tasks(
        project_repository,
        task_repository,
        tag_repository,
        task_tag_repository,
    )

    assert result.total_count == 2


@pytest.mark.revised
def test_listing_tasks_with_no_tasks_returns_empty_list(
    project_repository: InMemoryProjectRepository,
    task_repository: InMemoryTaskRepository,
    tag_repository: InMemoryTagRepository,
    task_tag_repository: InMemoryTaskTagRepository,
) -> None:
    result = list_tasks(
        project_repository,
        task_repository,
        tag_repository,
        task_tag_repository,
    )

    assert result.items == []
    assert result.total_count == 0


@pytest.mark.revised
def test_filtering_by_one_status_returns_only_tasks_with_that_status(
    project_repository: InMemoryProjectRepository,
    task_repository: InMemoryTaskRepository,
    tag_repository: InMemoryTagRepository,
    task_tag_repository: InMemoryTaskTagRepository,
) -> None:
    add_task(
        project_repository, task_repository, tag_repository, task_tag_repository, "Todo"
    )
    add_task(
        project_repository,
        task_repository,
        tag_repository,
        task_tag_repository,
        "Done",
        status=TaskStatus.DONE,
    )

    result = list_tasks(
        project_repository,
        task_repository,
        tag_repository,
        task_tag_repository,
        filters=TaskListFilters(statuses=[TaskStatus.DONE]),
    )

    assert task_titles(result) == ["Done"]


@pytest.mark.revised
def test_filtering_by_multiple_statuses_returns_tasks_matching_any_status(
    project_repository: InMemoryProjectRepository,
    task_repository: InMemoryTaskRepository,
    tag_repository: InMemoryTagRepository,
    task_tag_repository: InMemoryTaskTagRepository,
) -> None:
    add_task(
        project_repository, task_repository, tag_repository, task_tag_repository, "Todo"
    )
    add_task(
        project_repository,
        task_repository,
        tag_repository,
        task_tag_repository,
        "Doing",
        status=TaskStatus.DOING,
    )
    add_task(
        project_repository,
        task_repository,
        tag_repository,
        task_tag_repository,
        "Done",
        status=TaskStatus.DONE,
    )

    result = list_tasks(
        project_repository,
        task_repository,
        tag_repository,
        task_tag_repository,
        filters=TaskListFilters(statuses=[TaskStatus.DOING, TaskStatus.DONE]),
    )

    assert task_titles(result) == ["Doing", "Done"]


@pytest.mark.revised
def test_filtering_by_archived_status_returns_archived_tasks(
    project_repository: InMemoryProjectRepository,
    task_repository: InMemoryTaskRepository,
    tag_repository: InMemoryTagRepository,
    task_tag_repository: InMemoryTaskTagRepository,
) -> None:
    add_task(
        project_repository,
        task_repository,
        tag_repository,
        task_tag_repository,
        "Archived",
        status=TaskStatus.ARCHIVED,
    )

    result = list_tasks(
        project_repository,
        task_repository,
        tag_repository,
        task_tag_repository,
        filters=TaskListFilters(statuses=[TaskStatus.ARCHIVED]),
    )

    assert task_titles(result) == ["Archived"]


@pytest.mark.revised
def test_filtering_by_invalid_status_fails() -> None:
    with pytest.raises(InvalidTaskListFilterError):
        normalize_task_list_filters(TaskListFilters(statuses=["blocked"]))


@pytest.mark.revised
def test_filtering_by_project_returns_only_tasks_from_that_project(
    project_repository: InMemoryProjectRepository,
    task_repository: InMemoryTaskRepository,
    tag_repository: InMemoryTagRepository,
    task_tag_repository: InMemoryTaskTagRepository,
) -> None:
    work = get_or_create_project(project_repository, "Work")
    add_task(
        project_repository, task_repository, tag_repository, task_tag_repository, "Work"
    )
    add_task(
        project_repository,
        task_repository,
        tag_repository,
        task_tag_repository,
        "Personal",
        project_name="Personal",
    )

    result = list_tasks(
        project_repository,
        task_repository,
        tag_repository,
        task_tag_repository,
        filters=TaskListFilters(project_id=work.id),
    )

    assert task_titles(result) == ["Work"]


@pytest.mark.revised
def test_filtering_by_project_with_no_matching_tasks_returns_empty_list(
    project_repository: InMemoryProjectRepository,
    task_repository: InMemoryTaskRepository,
    tag_repository: InMemoryTagRepository,
    task_tag_repository: InMemoryTaskTagRepository,
) -> None:
    empty_project = create_project(project_repository, name="Empty")
    add_task(
        project_repository, task_repository, tag_repository, task_tag_repository, "Work"
    )

    result = list_tasks(
        project_repository,
        task_repository,
        tag_repository,
        task_tag_repository,
        filters=TaskListFilters(project_id=empty_project.id),
    )

    assert result.items == []


@pytest.mark.revised
def test_filtering_by_missing_project_returns_empty_list(
    project_repository: InMemoryProjectRepository,
    task_repository: InMemoryTaskRepository,
    tag_repository: InMemoryTagRepository,
    task_tag_repository: InMemoryTaskTagRepository,
) -> None:
    add_task(
        project_repository, task_repository, tag_repository, task_tag_repository, "Work"
    )

    result = list_tasks(
        project_repository,
        task_repository,
        tag_repository,
        task_tag_repository,
        filters=TaskListFilters(project_id=uuid4()),
    )

    assert result.items == []


@pytest.mark.revised
def test_filtering_by_one_tag_returns_tasks_with_that_tag(
    project_repository: InMemoryProjectRepository,
    task_repository: InMemoryTaskRepository,
    tag_repository: InMemoryTagRepository,
    task_tag_repository: InMemoryTaskTagRepository,
) -> None:
    add_task(
        project_repository,
        task_repository,
        tag_repository,
        task_tag_repository,
        "Urgent",
        tags=["urgent"],
    )
    add_task(
        project_repository,
        task_repository,
        tag_repository,
        task_tag_repository,
        "Plain",
    )

    result = list_tasks(
        project_repository,
        task_repository,
        tag_repository,
        task_tag_repository,
        filters=TaskListFilters(tag_names=["urgent"]),
    )

    assert task_titles(result) == ["Urgent"]


@pytest.mark.revised
def test_filtering_by_multiple_tags_returns_only_tasks_with_all_requested_tags(
    project_repository: InMemoryProjectRepository,
    task_repository: InMemoryTaskRepository,
    tag_repository: InMemoryTagRepository,
    task_tag_repository: InMemoryTaskTagRepository,
) -> None:
    add_task(
        project_repository,
        task_repository,
        tag_repository,
        task_tag_repository,
        "Both",
        tags=["urgent", "review"],
    )
    add_task(
        project_repository,
        task_repository,
        tag_repository,
        task_tag_repository,
        "Only urgent",
        tags=["urgent"],
    )

    result = list_tasks(
        project_repository,
        task_repository,
        tag_repository,
        task_tag_repository,
        filters=TaskListFilters(tag_names=["urgent", "review"]),
    )

    assert task_titles(result) == ["Both"]


@pytest.mark.revised
def test_filtering_by_tag_normalizes_tag_names(
    project_repository: InMemoryProjectRepository,
    task_repository: InMemoryTaskRepository,
    tag_repository: InMemoryTagRepository,
    task_tag_repository: InMemoryTaskTagRepository,
) -> None:
    add_task(
        project_repository,
        task_repository,
        tag_repository,
        task_tag_repository,
        "Deep",
        tags=["deep-work"],
    )

    result = list_tasks(
        project_repository,
        task_repository,
        tag_repository,
        task_tag_repository,
        filters=TaskListFilters(tag_names=["#Deep Work"]),
    )

    assert task_titles(result) == ["Deep"]


@pytest.mark.revised
def test_filtering_by_duplicated_tag_names_behaves_like_filtering_once(
    project_repository: InMemoryProjectRepository,
    task_repository: InMemoryTaskRepository,
    tag_repository: InMemoryTagRepository,
    task_tag_repository: InMemoryTaskTagRepository,
) -> None:
    add_task(
        project_repository,
        task_repository,
        tag_repository,
        task_tag_repository,
        "Urgent",
        tags=["urgent"],
    )

    result = list_tasks(
        project_repository,
        task_repository,
        tag_repository,
        task_tag_repository,
        filters=TaskListFilters(tag_names=["urgent", "#URGENT"]),
    )

    assert task_titles(result) == ["Urgent"]


@pytest.mark.revised
def test_filtering_by_missing_tag_returns_empty_list(
    project_repository: InMemoryProjectRepository,
    task_repository: InMemoryTaskRepository,
    tag_repository: InMemoryTagRepository,
    task_tag_repository: InMemoryTaskTagRepository,
) -> None:
    add_task(
        project_repository, task_repository, tag_repository, task_tag_repository, "A"
    )

    result = list_tasks(
        project_repository,
        task_repository,
        tag_repository,
        task_tag_repository,
        filters=TaskListFilters(tag_names=["missing"]),
    )

    assert result.items == []


def test_filtering_by_tag_does_not_return_tasks_with_only_some_requested_tags(
    project_repository: InMemoryProjectRepository,
    task_repository: InMemoryTaskRepository,
    tag_repository: InMemoryTagRepository,
    task_tag_repository: InMemoryTaskTagRepository,
) -> None:
    add_task(
        project_repository,
        task_repository,
        tag_repository,
        task_tag_repository,
        "Only urgent",
        tags=["urgent"],
    )

    result = list_tasks(
        project_repository,
        task_repository,
        tag_repository,
        task_tag_repository,
        filters=TaskListFilters(tag_names=["urgent", "review"]),
    )

    assert result.items == []


@pytest.mark.revised
def test_filtering_by_one_priority_returns_only_tasks_with_that_priority(
    project_repository: InMemoryProjectRepository,
    task_repository: InMemoryTaskRepository,
    tag_repository: InMemoryTagRepository,
    task_tag_repository: InMemoryTaskTagRepository,
) -> None:
    add_task(
        project_repository,
        task_repository,
        tag_repository,
        task_tag_repository,
        "High",
        priority=TaskPriority.HIGH,
    )
    add_task(
        project_repository, task_repository, tag_repository, task_tag_repository, "None"
    )

    result = list_tasks(
        project_repository,
        task_repository,
        tag_repository,
        task_tag_repository,
        filters=TaskListFilters(priorities=[TaskPriority.HIGH]),
    )

    assert task_titles(result) == ["High"]


@pytest.mark.revised
def test_filtering_by_multiple_priorities_returns_tasks_matching_any_priority(
    project_repository: InMemoryProjectRepository,
    task_repository: InMemoryTaskRepository,
    tag_repository: InMemoryTagRepository,
    task_tag_repository: InMemoryTaskTagRepository,
) -> None:
    add_task(
        project_repository,
        task_repository,
        tag_repository,
        task_tag_repository,
        "Low",
        priority=TaskPriority.LOW,
    )
    add_task(
        project_repository,
        task_repository,
        tag_repository,
        task_tag_repository,
        "High",
        priority=TaskPriority.HIGH,
    )
    add_task(
        project_repository, task_repository, tag_repository, task_tag_repository, "None"
    )

    result = list_tasks(
        project_repository,
        task_repository,
        tag_repository,
        task_tag_repository,
        filters=TaskListFilters(priorities=[TaskPriority.LOW, TaskPriority.HIGH]),
    )

    assert task_titles(result) == ["Low", "High"]


@pytest.mark.revised
def test_filtering_by_invalid_priority_fails() -> None:
    with pytest.raises(InvalidTaskListFilterError):
        normalize_task_list_filters(TaskListFilters(priorities=["urgent"]))


@pytest.mark.revised
def test_filtering_by_due_on_returns_tasks_due_on_that_date(
    project_repository: InMemoryProjectRepository,
    task_repository: InMemoryTaskRepository,
    tag_repository: InMemoryTagRepository,
    task_tag_repository: InMemoryTaskTagRepository,
) -> None:
    due = date(2026, 5, 1)
    add_task(
        project_repository,
        task_repository,
        tag_repository,
        task_tag_repository,
        "Due",
        due_date=due,
    )
    add_task(
        project_repository,
        task_repository,
        tag_repository,
        task_tag_repository,
        "Other",
        due_date=date(2026, 5, 2),
    )

    result = list_tasks(
        project_repository,
        task_repository,
        tag_repository,
        task_tag_repository,
        filters=TaskListFilters(due_on=due),
    )

    assert task_titles(result) == ["Due"]


@pytest.mark.revised
def test_filtering_by_due_before_returns_tasks_due_before_that_date(
    project_repository: InMemoryProjectRepository,
    task_repository: InMemoryTaskRepository,
    tag_repository: InMemoryTagRepository,
    task_tag_repository: InMemoryTaskTagRepository,
) -> None:
    add_task(
        project_repository,
        task_repository,
        tag_repository,
        task_tag_repository,
        "Before",
        due_date=date(2026, 4, 30),
    )
    add_task(
        project_repository,
        task_repository,
        tag_repository,
        task_tag_repository,
        "On",
        due_date=date(2026, 5, 1),
    )

    result = list_tasks(
        project_repository,
        task_repository,
        tag_repository,
        task_tag_repository,
        filters=TaskListFilters(due_before=date(2026, 5, 1)),
    )

    assert task_titles(result) == ["Before"]


@pytest.mark.revised
def test_filtering_by_due_after_returns_tasks_due_after_that_date(
    project_repository: InMemoryProjectRepository,
    task_repository: InMemoryTaskRepository,
    tag_repository: InMemoryTagRepository,
    task_tag_repository: InMemoryTaskTagRepository,
) -> None:
    add_task(
        project_repository,
        task_repository,
        tag_repository,
        task_tag_repository,
        "After",
        due_date=date(2026, 5, 2),
    )
    add_task(
        project_repository,
        task_repository,
        tag_repository,
        task_tag_repository,
        "On",
        due_date=date(2026, 5, 1),
    )

    result = list_tasks(
        project_repository,
        task_repository,
        tag_repository,
        task_tag_repository,
        filters=TaskListFilters(due_after=date(2026, 5, 1)),
    )

    assert task_titles(result) == ["After"]


def test_filtering_by_due_date_excludes_tasks_without_due_dates(
    project_repository: InMemoryProjectRepository,
    task_repository: InMemoryTaskRepository,
    tag_repository: InMemoryTagRepository,
    task_tag_repository: InMemoryTaskTagRepository,
) -> None:
    add_task(
        project_repository,
        task_repository,
        tag_repository,
        task_tag_repository,
        "No date",
    )
    add_task(
        project_repository,
        task_repository,
        tag_repository,
        task_tag_repository,
        "Due",
        due_date=date(2026, 5, 1),
    )

    result = list_tasks(
        project_repository,
        task_repository,
        tag_repository,
        task_tag_repository,
        filters=TaskListFilters(due_before=date(2026, 5, 2)),
    )

    assert task_titles(result) == ["Due"]


@pytest.mark.revised
def test_combining_due_date_filters_returns_tasks_matching_all_constraints(
    project_repository: InMemoryProjectRepository,
    task_repository: InMemoryTaskRepository,
    tag_repository: InMemoryTagRepository,
    task_tag_repository: InMemoryTaskTagRepository,
) -> None:
    add_task(
        project_repository,
        task_repository,
        tag_repository,
        task_tag_repository,
        "Inside",
        due_date=date(2026, 5, 5),
    )
    add_task(
        project_repository,
        task_repository,
        tag_repository,
        task_tag_repository,
        "Outside",
        due_date=date(2026, 5, 10),
    )

    result = list_tasks(
        project_repository,
        task_repository,
        tag_repository,
        task_tag_repository,
        filters=TaskListFilters(
            due_after=date(2026, 5, 1),
            due_before=date(2026, 5, 8),
        ),
    )

    assert task_titles(result) == ["Inside"]


@pytest.mark.revised
def test_searching_by_title_returns_matching_tasks(
    project_repository: InMemoryProjectRepository,
    task_repository: InMemoryTaskRepository,
    tag_repository: InMemoryTagRepository,
    task_tag_repository: InMemoryTaskTagRepository,
) -> None:
    add_task(
        project_repository,
        task_repository,
        tag_repository,
        task_tag_repository,
        "Prepare class",
    )
    add_task(
        project_repository,
        task_repository,
        tag_repository,
        task_tag_repository,
        "Review notes",
    )

    result = list_tasks(
        project_repository,
        task_repository,
        tag_repository,
        task_tag_repository,
        filters=TaskListFilters(search="class"),
    )

    assert task_titles(result) == ["Prepare class"]


@pytest.mark.revised
def test_searching_by_description_returns_matching_tasks(
    project_repository: InMemoryProjectRepository,
    task_repository: InMemoryTaskRepository,
    tag_repository: InMemoryTagRepository,
    task_tag_repository: InMemoryTaskTagRepository,
) -> None:
    add_task(
        project_repository,
        task_repository,
        tag_repository,
        task_tag_repository,
        "Prepare",
        description="Grammar examples",
    )
    add_task(
        project_repository,
        task_repository,
        tag_repository,
        task_tag_repository,
        "Review",
    )

    result = list_tasks(
        project_repository,
        task_repository,
        tag_repository,
        task_tag_repository,
        filters=TaskListFilters(search="grammar"),
    )

    assert task_titles(result) == ["Prepare"]


@pytest.mark.revised
def test_searching_is_case_insensitive(
    project_repository: InMemoryProjectRepository,
    task_repository: InMemoryTaskRepository,
    tag_repository: InMemoryTagRepository,
    task_tag_repository: InMemoryTaskTagRepository,
) -> None:
    add_task(
        project_repository,
        task_repository,
        tag_repository,
        task_tag_repository,
        "Prepare Class",
    )

    result = list_tasks(
        project_repository,
        task_repository,
        tag_repository,
        task_tag_repository,
        filters=TaskListFilters(search="class"),
    )

    assert task_titles(result) == ["Prepare Class"]


@pytest.mark.revised
def test_searching_trims_the_query(
    project_repository: InMemoryProjectRepository,
    task_repository: InMemoryTaskRepository,
    tag_repository: InMemoryTagRepository,
    task_tag_repository: InMemoryTaskTagRepository,
) -> None:
    add_task(
        project_repository,
        task_repository,
        tag_repository,
        task_tag_repository,
        "Prepare class",
    )

    result = list_tasks(
        project_repository,
        task_repository,
        tag_repository,
        task_tag_repository,
        filters=TaskListFilters(search="  class  "),
    )

    assert task_titles(result) == ["Prepare class"]


@pytest.mark.revised
def test_blank_search_query_is_ignored(
    project_repository: InMemoryProjectRepository,
    task_repository: InMemoryTaskRepository,
    tag_repository: InMemoryTagRepository,
    task_tag_repository: InMemoryTaskTagRepository,
) -> None:
    add_task(
        project_repository, task_repository, tag_repository, task_tag_repository, "A"
    )

    result = list_tasks(
        project_repository,
        task_repository,
        tag_repository,
        task_tag_repository,
        filters=TaskListFilters(search="   "),
    )

    assert task_titles(result) == ["A"]


@pytest.mark.revised
def test_searching_with_no_matches_returns_empty_list(
    project_repository: InMemoryProjectRepository,
    task_repository: InMemoryTaskRepository,
    tag_repository: InMemoryTagRepository,
    task_tag_repository: InMemoryTaskTagRepository,
) -> None:
    add_task(
        project_repository, task_repository, tag_repository, task_tag_repository, "A"
    )

    result = list_tasks(
        project_repository,
        task_repository,
        tag_repository,
        task_tag_repository,
        filters=TaskListFilters(search="missing"),
    )

    assert result.items == []


@pytest.mark.revised
def test_combining_project_and_status_filters_returns_tasks_matching_both(
    project_repository: InMemoryProjectRepository,
    task_repository: InMemoryTaskRepository,
    tag_repository: InMemoryTagRepository,
    task_tag_repository: InMemoryTaskTagRepository,
) -> None:
    work = get_or_create_project(project_repository, "Work")
    add_task(
        project_repository,
        task_repository,
        tag_repository,
        task_tag_repository,
        "Match",
        project_name="Work",
        status=TaskStatus.DONE,
    )
    add_task(
        project_repository,
        task_repository,
        tag_repository,
        task_tag_repository,
        "Wrong status",
        project_name="Work",
    )

    result = list_tasks(
        project_repository,
        task_repository,
        tag_repository,
        task_tag_repository,
        filters=TaskListFilters(project_id=work.id, statuses=[TaskStatus.DONE]),
    )

    assert task_titles(result) == ["Match"]


@pytest.mark.revised
def test_combining_tag_and_priority_filters_returns_tasks_matching_both(
    project_repository: InMemoryProjectRepository,
    task_repository: InMemoryTaskRepository,
    tag_repository: InMemoryTagRepository,
    task_tag_repository: InMemoryTaskTagRepository,
) -> None:
    add_task(
        project_repository,
        task_repository,
        tag_repository,
        task_tag_repository,
        "Match",
        tags=["urgent"],
        priority=TaskPriority.HIGH,
    )
    add_task(
        project_repository,
        task_repository,
        tag_repository,
        task_tag_repository,
        "Wrong priority",
        tags=["urgent"],
        priority=TaskPriority.LOW,
    )

    result = list_tasks(
        project_repository,
        task_repository,
        tag_repository,
        task_tag_repository,
        filters=TaskListFilters(tag_names=["urgent"], priorities=[TaskPriority.HIGH]),
    )

    assert task_titles(result) == ["Match"]


@pytest.mark.revised
def test_combining_search_and_due_date_filters_returns_tasks_matching_both(
    project_repository: InMemoryProjectRepository,
    task_repository: InMemoryTaskRepository,
    tag_repository: InMemoryTagRepository,
    task_tag_repository: InMemoryTaskTagRepository,
) -> None:
    add_task(
        project_repository,
        task_repository,
        tag_repository,
        task_tag_repository,
        "Prepare class",
        due_date=date(2026, 5, 1),
    )
    add_task(
        project_repository,
        task_repository,
        tag_repository,
        task_tag_repository,
        "Prepare later",
        due_date=date(2026, 5, 2),
    )

    result = list_tasks(
        project_repository,
        task_repository,
        tag_repository,
        task_tag_repository,
        filters=TaskListFilters(search="prepare", due_on=date(2026, 5, 1)),
    )

    assert task_titles(result) == ["Prepare class"]


@pytest.mark.revised
def test_filters_are_applied_with_and_semantics_across_filter_types(
    project_repository: InMemoryProjectRepository,
    task_repository: InMemoryTaskRepository,
    tag_repository: InMemoryTagRepository,
    task_tag_repository: InMemoryTaskTagRepository,
) -> None:
    work = get_or_create_project(project_repository, "Work")
    add_task(
        project_repository,
        task_repository,
        tag_repository,
        task_tag_repository,
        "Match",
        project_name="Work",
        tags=["urgent"],
    )
    add_task(
        project_repository,
        task_repository,
        tag_repository,
        task_tag_repository,
        "Wrong project",
        project_name="Personal",
        tags=["urgent"],
    )

    result = list_tasks(
        project_repository,
        task_repository,
        tag_repository,
        task_tag_repository,
        filters=TaskListFilters(project_id=work.id, tag_names=["urgent"]),
    )

    assert task_titles(result) == ["Match"]


@pytest.mark.revised
def test_default_sorting_uses_sort_order_before_created_date(
    project_repository: InMemoryProjectRepository,
    task_repository: InMemoryTaskRepository,
    tag_repository: InMemoryTagRepository,
    task_tag_repository: InMemoryTaskTagRepository,
) -> None:
    add_task(
        project_repository,
        task_repository,
        tag_repository,
        task_tag_repository,
        "Second",
        sort_order=2,
        created_at=BASE_TIME,
    )
    add_task(
        project_repository,
        task_repository,
        tag_repository,
        task_tag_repository,
        "First",
        sort_order=1,
        created_at=BASE_TIME + timedelta(days=1),
    )

    result = list_tasks(
        project_repository,
        task_repository,
        tag_repository,
        task_tag_repository,
    )

    assert task_titles(result) == ["First", "Second"]


@pytest.mark.revised
def test_default_sorting_places_tasks_without_sort_order_after_tasks_with_sort_order(
    project_repository: InMemoryProjectRepository,
    task_repository: InMemoryTaskRepository,
    tag_repository: InMemoryTagRepository,
    task_tag_repository: InMemoryTaskTagRepository,
) -> None:
    add_task(
        project_repository,
        task_repository,
        tag_repository,
        task_tag_repository,
        "No order",
    )
    add_task(
        project_repository,
        task_repository,
        tag_repository,
        task_tag_repository,
        "Ordered",
        sort_order=1,
    )

    result = list_tasks(
        project_repository,
        task_repository,
        tag_repository,
        task_tag_repository,
    )

    assert task_titles(result) == ["Ordered", "No order"]


@pytest.mark.revised
def test_sorting_by_title_orders_tasks_alphabetically(
    project_repository: InMemoryProjectRepository,
    task_repository: InMemoryTaskRepository,
    tag_repository: InMemoryTagRepository,
    task_tag_repository: InMemoryTaskTagRepository,
) -> None:
    add_task(
        project_repository, task_repository, tag_repository, task_tag_repository, "Beta"
    )
    add_task(
        project_repository,
        task_repository,
        tag_repository,
        task_tag_repository,
        "Alpha",
    )

    result = list_tasks(
        project_repository,
        task_repository,
        tag_repository,
        task_tag_repository,
        sort=TaskSort(key="title"),
    )

    assert task_titles(result) == ["Alpha", "Beta"]


@pytest.mark.revised
def test_sorting_by_created_date_orders_tasks_by_creation_date(
    project_repository: InMemoryProjectRepository,
    task_repository: InMemoryTaskRepository,
    tag_repository: InMemoryTagRepository,
    task_tag_repository: InMemoryTaskTagRepository,
) -> None:
    add_task(
        project_repository,
        task_repository,
        tag_repository,
        task_tag_repository,
        "Later",
        created_at=BASE_TIME + timedelta(days=1),
    )
    add_task(
        project_repository,
        task_repository,
        tag_repository,
        task_tag_repository,
        "Earlier",
        created_at=BASE_TIME,
    )

    result = list_tasks(
        project_repository,
        task_repository,
        tag_repository,
        task_tag_repository,
        sort=TaskSort(key="created_at"),
    )

    assert task_titles(result) == ["Earlier", "Later"]


@pytest.mark.revised
def test_sorting_by_updated_date_orders_tasks_by_update_date(
    project_repository: InMemoryProjectRepository,
    task_repository: InMemoryTaskRepository,
    tag_repository: InMemoryTagRepository,
    task_tag_repository: InMemoryTaskTagRepository,
) -> None:
    add_task(
        project_repository,
        task_repository,
        tag_repository,
        task_tag_repository,
        "Later",
        updated_at=BASE_TIME + timedelta(days=1),
    )
    add_task(
        project_repository,
        task_repository,
        tag_repository,
        task_tag_repository,
        "Earlier",
        updated_at=BASE_TIME,
    )

    result = list_tasks(
        project_repository,
        task_repository,
        tag_repository,
        task_tag_repository,
        sort=TaskSort(key="updated_at"),
    )

    assert task_titles(result) == ["Earlier", "Later"]


@pytest.mark.revised
def test_sorting_by_due_date_places_dated_tasks_before_undated_tasks_ascending(
    project_repository: InMemoryProjectRepository,
    task_repository: InMemoryTaskRepository,
    tag_repository: InMemoryTagRepository,
    task_tag_repository: InMemoryTaskTagRepository,
) -> None:
    add_task(
        project_repository,
        task_repository,
        tag_repository,
        task_tag_repository,
        "No date",
    )
    add_task(
        project_repository,
        task_repository,
        tag_repository,
        task_tag_repository,
        "Due",
        due_date=date(2026, 5, 1),
    )

    result = list_tasks(
        project_repository,
        task_repository,
        tag_repository,
        task_tag_repository,
        sort=TaskSort(key="due_date"),
    )

    assert task_titles(result) == ["Due", "No date"]


@pytest.mark.revised
def test_sorting_by_priority_orders_tasks_by_priority_rank(
    project_repository: InMemoryProjectRepository,
    task_repository: InMemoryTaskRepository,
    tag_repository: InMemoryTagRepository,
    task_tag_repository: InMemoryTaskTagRepository,
) -> None:
    add_task(
        project_repository,
        task_repository,
        tag_repository,
        task_tag_repository,
        "High",
        priority=TaskPriority.HIGH,
    )
    add_task(
        project_repository, task_repository, tag_repository, task_tag_repository, "None"
    )
    add_task(
        project_repository,
        task_repository,
        tag_repository,
        task_tag_repository,
        "Low",
        priority=TaskPriority.LOW,
    )

    result = list_tasks(
        project_repository,
        task_repository,
        tag_repository,
        task_tag_repository,
        sort=TaskSort(key="priority"),
    )

    assert task_titles(result) == ["None", "Low", "High"]


@pytest.mark.revised
def test_descending_sort_reverses_selected_sort_order(
    project_repository: InMemoryProjectRepository,
    task_repository: InMemoryTaskRepository,
    tag_repository: InMemoryTagRepository,
    task_tag_repository: InMemoryTaskTagRepository,
) -> None:
    add_task(
        project_repository,
        task_repository,
        tag_repository,
        task_tag_repository,
        "Alpha",
    )
    add_task(
        project_repository, task_repository, tag_repository, task_tag_repository, "Beta"
    )

    result = list_tasks(
        project_repository,
        task_repository,
        tag_repository,
        task_tag_repository,
        sort=TaskSort(key="title", direction="desc"),
    )

    assert task_titles(result) == ["Beta", "Alpha"]


@pytest.mark.revised
def test_sorting_uses_task_id_as_final_tie_breaker(
    project_repository: InMemoryProjectRepository,
    task_repository: InMemoryTaskRepository,
    tag_repository: InMemoryTagRepository,
    task_tag_repository: InMemoryTaskTagRepository,
) -> None:
    first = add_task(
        project_repository,
        task_repository,
        tag_repository,
        task_tag_repository,
        "Same",
        created_at=BASE_TIME,
    )
    second = add_task(
        project_repository,
        task_repository,
        tag_repository,
        task_tag_repository,
        "Same",
        project_name="Other",
        created_at=BASE_TIME,
    )

    result = list_tasks(
        project_repository,
        task_repository,
        tag_repository,
        task_tag_repository,
        filters=TaskListFilters(include_archived=True),
        sort=TaskSort(key="title"),
    )

    assert [item.task.id for item in result.items] == sorted([first.id, second.id])


@pytest.mark.revised
def test_invalid_sort_key_fails() -> None:
    with pytest.raises(InvalidTaskListFilterError):
        list_tasks_with_invalid_sort(TaskSort(key="project"))


@pytest.mark.revised
def test_invalid_sort_direction_fails() -> None:
    with pytest.raises(InvalidTaskListFilterError):
        list_tasks_with_invalid_sort(TaskSort(key="title", direction="sideways"))


@pytest.mark.revised
def list_tasks_with_invalid_sort(sort: TaskSort) -> None:
    project_repository = InMemoryProjectRepository()
    task_repository = InMemoryTaskRepository()
    tag_repository = InMemoryTagRepository()
    task_tag_repository = InMemoryTaskTagRepository()

    list_tasks(
        project_repository,
        task_repository,
        tag_repository,
        task_tag_repository,
        sort=sort,
    )
