from __future__ import annotations

from datetime import date

import pytest

from tomatempo.application.use_cases import (
    ArchiveTask,
    CompleteTask,
    GetOrCreateProjectByName,
    ReopenTask,
    UpdateTask,
)
from tomatempo.domain.exceptions import (
    DuplicateProjectNameError,
    DuplicateTaskTitleError,
    InvalidProjectNameError,
    InvalidTaskPriorityError,
    InvalidTaskTitleError,
)
from tomatempo.domain.value_objects import TaskPriority, TaskStatus

from .conftest import (
    InMemoryProjectRepository,
    InMemoryTaskRepository,
    create_project,
    create_task,
)


@pytest.mark.revised
def test_creating_project_with_valid_name_succeeds(
    project_repository: InMemoryProjectRepository,
) -> None:
    project = create_project(project_repository, name="Tomatempo")

    assert project.name == "Tomatempo"
    assert project.id is not None
    assert project.created_at is not None
    assert project.updated_at is not None


@pytest.mark.revised
def test_creating_project_trims_leading_and_trailing_spaces(
    project_repository: InMemoryProjectRepository,
) -> None:
    project = create_project(project_repository, name="  Tomatempo  ")

    assert project.name == "Tomatempo"


@pytest.mark.revised
@pytest.mark.parametrize("invalid_name", ["", "   "])
def test_creating_project_with_empty_or_blank_name_fails(
    project_repository: InMemoryProjectRepository,
    invalid_name: str,
) -> None:
    with pytest.raises(InvalidProjectNameError):
        create_project(project_repository, name=invalid_name)


@pytest.mark.revised
def test_creating_duplicated_project_name_fails(
    project_repository: InMemoryProjectRepository,
) -> None:
    create_project(project_repository, name="Tomatempo")

    with pytest.raises(DuplicateProjectNameError):
        create_project(project_repository, name="Tomatempo")


@pytest.mark.revised
def test_project_name_uniqueness_is_case_insensitive(
    project_repository: InMemoryProjectRepository,
) -> None:
    create_project(project_repository, name="Tomatempo")

    with pytest.raises(DuplicateProjectNameError):
        create_project(project_repository, name="tomatempo")


@pytest.mark.revised
def test_getting_or_creating_existing_project_does_not_create_duplicate(
    project_repository: InMemoryProjectRepository,
) -> None:
    existing_project = create_project(project_repository, name="  Tomatempo  ")

    project = GetOrCreateProjectByName(project_repository).execute("tomatempo")

    assert project.id == existing_project.id
    assert project_repository.count() == 1


@pytest.mark.revised
def test_getting_or_creating_missing_project_creates_it(
    project_repository: InMemoryProjectRepository,
) -> None:
    project = GetOrCreateProjectByName(project_repository).execute("Tomatempo")

    assert project.name == "Tomatempo"
    assert project_repository.count() == 1


@pytest.mark.revised
def test_creating_task_without_project_creates_inbox_automatically(
    project_repository: InMemoryProjectRepository,
    task_repository: InMemoryTaskRepository,
) -> None:
    task = create_task(task_repository, project_repository, title="Capture idea")
    inbox = project_repository.get_by_name("Inbox")

    assert inbox is not None
    assert task.project_id == inbox.id


@pytest.mark.revised
def test_creating_multiple_tasks_without_project_reuses_same_inbox(
    project_repository: InMemoryProjectRepository,
    task_repository: InMemoryTaskRepository,
) -> None:
    first_task = create_task(task_repository, project_repository, title="Capture idea")
    second_task = create_task(task_repository, project_repository, title="Review notes")

    assert first_task.project_id == second_task.project_id
    assert project_repository.count() == 1


@pytest.mark.revised
def test_inbox_uniqueness_is_case_insensitive(
    project_repository: InMemoryProjectRepository,
    task_repository: InMemoryTaskRepository,
) -> None:
    existing_inbox = create_project(project_repository, name="inbox")

    task = create_task(task_repository, project_repository, title="Capture idea")

    assert task.project_id == existing_inbox.id
    assert project_repository.count() == 1

@pytest.mark.revised
def test_creating_task_with_valid_data_succeeds(
    project_repository: InMemoryProjectRepository,
    task_repository: InMemoryTaskRepository,
) -> None:
    project = create_project(project_repository)

    task = create_task(task_repository, project_repository, project_id=project.id)

    assert task.title == "Prepare class"
    assert task.id is not None
    assert task.created_at is not None
    assert task.updated_at is not None


@pytest.mark.revised
def test_creating_task_trims_leading_and_trailing_spaces_from_title(
    project_repository: InMemoryProjectRepository,
    task_repository: InMemoryTaskRepository,
) -> None:
    project = create_project(project_repository)

    task = create_task(
        task_repository,
        project_repository,
        title="  Prepare class  ",
        project_id=project.id,
    )

    assert task.title == "Prepare class"


@pytest.mark.revised
@pytest.mark.parametrize("invalid_title", ["", "   "])
def test_creating_task_with_empty_or_blank_title_fails(
    project_repository: InMemoryProjectRepository,
    task_repository: InMemoryTaskRepository,
    invalid_title: str,
) -> None:
    project = create_project(project_repository)

    with pytest.raises(InvalidTaskTitleError):
        create_task(
            task_repository,
            project_repository,
            title=invalid_title,
            project_id=project.id,
        )


@pytest.mark.revised
def test_new_task_starts_with_status_todo(
    project_repository: InMemoryProjectRepository,
    task_repository: InMemoryTaskRepository,
) -> None:
    project = create_project(project_repository)

    task = create_task(task_repository, project_repository, project_id=project.id)

    assert task.status == TaskStatus.TODO


@pytest.mark.revised
def test_new_task_starts_with_priority_none(
    project_repository: InMemoryProjectRepository,
    task_repository: InMemoryTaskRepository,
) -> None:
    project = create_project(project_repository)

    task = create_task(task_repository, project_repository, project_id=project.id)

    assert task.priority == TaskPriority.NONE


@pytest.mark.revised
def test_new_task_belongs_to_selected_project(
    project_repository: InMemoryProjectRepository,
    task_repository: InMemoryTaskRepository,
) -> None:
    project = create_project(project_repository, name="English Classes")

    task = create_task(task_repository, project_repository, project_id=project.id)

    assert task.project_id == project.id


@pytest.mark.revised
def test_creating_same_task_twice_in_same_project_is_rejected(
    project_repository: InMemoryProjectRepository,
    task_repository: InMemoryTaskRepository,
) -> None:
    project = create_project(project_repository)
    create_task(task_repository, project_repository, project_id=project.id)

    with pytest.raises(DuplicateTaskTitleError):
        create_task(task_repository, project_repository, project_id=project.id)


@pytest.mark.revised
def test_task_duplicate_detection_is_case_insensitive(
    project_repository: InMemoryProjectRepository,
    task_repository: InMemoryTaskRepository,
) -> None:
    project = create_project(project_repository)
    create_task(
        task_repository,
        project_repository,
        title="Prepare class",
        project_id=project.id,
    )

    with pytest.raises(DuplicateTaskTitleError):
        create_task(
            task_repository,
            project_repository,
            title="PREPARE CLASS",
            project_id=project.id,
        )


@pytest.mark.revised
def test_task_duplicate_detection_ignores_leading_and_trailing_spaces(
    project_repository: InMemoryProjectRepository,
    task_repository: InMemoryTaskRepository,
) -> None:
    project = create_project(project_repository)
    create_task(
        task_repository,
        project_repository,
        title="Prepare class",
        project_id=project.id,
    )

    with pytest.raises(DuplicateTaskTitleError):
        create_task(
            task_repository,
            project_repository,
            title="  prepare class  ",
            project_id=project.id,
        )


@pytest.mark.revised
def test_same_task_title_can_exist_in_different_projects(
    project_repository: InMemoryProjectRepository,
    task_repository: InMemoryTaskRepository,
) -> None:
    work = create_project(project_repository, name="Work")
    personal = create_project(project_repository, name="Personal")

    work_task = create_task(
        task_repository,
        project_repository,
        title="Prepare class",
        project_id=work.id,
    )
    personal_task = create_task(
        task_repository,
        project_repository,
        title="Prepare class",
        project_id=personal.id,
    )

    assert work_task.project_id == work.id
    assert personal_task.project_id == personal.id
    assert task_repository.count() == 2


@pytest.mark.revised
def test_completing_task_sets_status_to_done(
    project_repository: InMemoryProjectRepository,
    task_repository: InMemoryTaskRepository,
) -> None:
    project = create_project(project_repository)
    task = create_task(task_repository, project_repository, project_id=project.id)

    completed_task = CompleteTask(task_repository).execute(task.id)

    assert completed_task.status == TaskStatus.DONE


@pytest.mark.revised
def test_completing_task_sets_completed_at(
    project_repository: InMemoryProjectRepository,
    task_repository: InMemoryTaskRepository,
) -> None:
    project = create_project(project_repository)
    task = create_task(task_repository, project_repository, project_id=project.id)

    completed_task = CompleteTask(task_repository).execute(task.id)

    assert completed_task.completed_at is not None
    assert completed_task.updated_at != task.updated_at


@pytest.mark.revised
def test_reopening_completed_task_sets_status_to_todo(
    project_repository: InMemoryProjectRepository,
    task_repository: InMemoryTaskRepository,
) -> None:
    project = create_project(project_repository)
    task = create_task(task_repository, project_repository, project_id=project.id)
    completed_task = CompleteTask(task_repository).execute(task.id)

    reopened_task = ReopenTask(task_repository).execute(completed_task.id)

    assert reopened_task.status == TaskStatus.TODO


@pytest.mark.revised
def test_reopening_completed_task_clears_completed_at(
    project_repository: InMemoryProjectRepository,
    task_repository: InMemoryTaskRepository,
) -> None:
    project = create_project(project_repository)
    task = create_task(task_repository, project_repository, project_id=project.id)
    completed_task = CompleteTask(task_repository).execute(task.id)

    reopened_task = ReopenTask(task_repository).execute(completed_task.id)

    assert reopened_task.completed_at is None
    assert reopened_task.updated_at != completed_task.updated_at


@pytest.mark.revised
def test_archiving_task_sets_status_to_archived(
    project_repository: InMemoryProjectRepository,
    task_repository: InMemoryTaskRepository,
) -> None:
    project = create_project(project_repository)
    task = create_task(task_repository, project_repository, project_id=project.id)

    archived_task = ArchiveTask(task_repository).execute(task.id)

    assert archived_task.status == TaskStatus.ARCHIVED


@pytest.mark.revised
def test_archiving_task_sets_archived_at(
    project_repository: InMemoryProjectRepository,
    task_repository: InMemoryTaskRepository,
) -> None:
    project = create_project(project_repository)
    task = create_task(task_repository, project_repository, project_id=project.id)

    archived_task = ArchiveTask(task_repository).execute(task.id)

    assert archived_task.archived_at is not None
    assert archived_task.updated_at != task.updated_at


@pytest.mark.revised
def test_updating_task_title_succeeds_with_valid_title(
    project_repository: InMemoryProjectRepository,
    task_repository: InMemoryTaskRepository,
) -> None:
    project = create_project(project_repository)
    task = create_task(task_repository, project_repository, project_id=project.id)

    updated_task = UpdateTask(task_repository, project_repository).execute(
        task.id,
        title="Review vocabulary",
    )

    assert updated_task.title == "Review vocabulary"


def test_updating_task_title_trims_leading_and_trailing_spaces(
    project_repository: InMemoryProjectRepository,
    task_repository: InMemoryTaskRepository,
) -> None:
    project = create_project(project_repository)
    task = create_task(task_repository, project_repository, project_id=project.id)

    updated_task = UpdateTask(task_repository, project_repository).execute(
        task.id,
        title="  Review vocabulary  ",
    )

    assert updated_task.title == "Review vocabulary"


@pytest.mark.revised
@pytest.mark.parametrize("invalid_title", ["", "   "])
def test_updating_task_title_to_empty_or_blank_value_fails(
    project_repository: InMemoryProjectRepository,
    task_repository: InMemoryTaskRepository,
    invalid_title: str,
) -> None:
    project = create_project(project_repository)
    task = create_task(task_repository, project_repository, project_id=project.id)

    with pytest.raises(InvalidTaskTitleError):
        UpdateTask(task_repository, project_repository).execute(
            task.id,
            title=invalid_title,
        )


@pytest.mark.revised
def test_updating_task_priority_succeeds_with_allowed_priority(
    project_repository: InMemoryProjectRepository,
    task_repository: InMemoryTaskRepository,
) -> None:
    project = create_project(project_repository)
    task = create_task(task_repository, project_repository, project_id=project.id)

    updated_task = UpdateTask(task_repository, project_repository).execute(
        task.id,
        priority=TaskPriority.HIGH,
    )

    assert updated_task.priority == TaskPriority.HIGH


@pytest.mark.revised
def test_updating_task_priority_with_invalid_priority_fails(
    project_repository: InMemoryProjectRepository,
    task_repository: InMemoryTaskRepository,
) -> None:
    project = create_project(project_repository)
    task = create_task(task_repository, project_repository, project_id=project.id)

    with pytest.raises(InvalidTaskPriorityError):
        UpdateTask(task_repository, project_repository).execute(
            task.id,
            priority="urgent",
        )


@pytest.mark.revised
def test_updating_task_due_date_succeeds(
    project_repository: InMemoryProjectRepository,
    task_repository: InMemoryTaskRepository,
) -> None:
    project = create_project(project_repository)
    task = create_task(task_repository, project_repository, project_id=project.id)
    due_date = date(2026, 5, 1)

    updated_task = UpdateTask(task_repository, project_repository).execute(
        task.id,
        due_date=due_date,
    )

    assert updated_task.due_date == due_date


def test_updating_task_preserves_created_at(
    project_repository: InMemoryProjectRepository,
    task_repository: InMemoryTaskRepository,
) -> None:
    project = create_project(project_repository)
    task = create_task(task_repository, project_repository, project_id=project.id)

    updated_task = UpdateTask(task_repository, project_repository).execute(
        task.id,
        description="Prepare grammar examples.",
    )

    assert updated_task.created_at == task.created_at


@pytest.mark.revised
def test_updating_task_changes_updated_at(
    project_repository: InMemoryProjectRepository,
    task_repository: InMemoryTaskRepository,
) -> None:
    project = create_project(project_repository)
    task = create_task(task_repository, project_repository, project_id=project.id)

    updated_task = UpdateTask(task_repository, project_repository).execute(
        task.id,
        description="Prepare grammar examples.",
    )

    assert updated_task.updated_at != task.updated_at
