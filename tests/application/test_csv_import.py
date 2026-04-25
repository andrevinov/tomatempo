from __future__ import annotations

from datetime import date

import pytest

from tomatempo.application.use_cases import (
    ImportCsvRow,
    ImportTasksFromCsvText,
    parse_tag_cell,
)
from tomatempo.domain.entities import Task
from tomatempo.domain.value_objects import TaskPriority

from .conftest import (
    InMemoryProjectRepository,
    InMemoryTagRepository,
    InMemoryTaskRepository,
    InMemoryTaskTagRepository,
    create_project,
    create_tag,
    list_task_tag_names,
)


def import_csv(
    csv_text: str,
    project_repository: InMemoryProjectRepository,
    task_repository: InMemoryTaskRepository,
    tag_repository: InMemoryTagRepository,
    task_tag_repository: InMemoryTaskTagRepository,
):
    return ImportTasksFromCsvText(
        task_repository=task_repository,
        project_repository=project_repository,
        tag_repository=tag_repository,
        task_tag_repository=task_tag_repository,
    ).execute(csv_text)


def import_row(
    row: dict[str, str],
    project_repository: InMemoryProjectRepository,
    task_repository: InMemoryTaskRepository,
    tag_repository: InMemoryTagRepository,
    task_tag_repository: InMemoryTaskTagRepository,
    row_number: int = 2,
) -> Task:
    return ImportCsvRow(
        task_repository=task_repository,
        project_repository=project_repository,
        tag_repository=tag_repository,
        task_tag_repository=task_tag_repository,
    ).execute(row=row, row_number=row_number)


def error_codes(result) -> list[str]:
    return [error.code for error in result.errors]


@pytest.mark.revised
def test_importing_empty_csv_text_fails(
    project_repository: InMemoryProjectRepository,
    task_repository: InMemoryTaskRepository,
    tag_repository: InMemoryTagRepository,
    task_tag_repository: InMemoryTaskTagRepository,
) -> None:
    result = import_csv(
        "",
        project_repository,
        task_repository,
        tag_repository,
        task_tag_repository,
    )

    assert result.created_count == 0
    assert result.errors[0].code == "empty_csv"


@pytest.mark.revised
def test_importing_csv_text_with_headers_and_no_rows_succeeds_with_zero_tasks(
    project_repository: InMemoryProjectRepository,
    task_repository: InMemoryTaskRepository,
    tag_repository: InMemoryTagRepository,
    task_tag_repository: InMemoryTaskTagRepository,
) -> None:
    result = import_csv(
        "title;project;tags\n",
        project_repository,
        task_repository,
        tag_repository,
        task_tag_repository,
    )

    assert result.processed_rows == 0
    assert result.created_count == 0
    assert result.errors == []


@pytest.mark.revised
def test_importing_csv_uses_semicolon_as_column_delimiter(
    project_repository: InMemoryProjectRepository,
    task_repository: InMemoryTaskRepository,
    tag_repository: InMemoryTagRepository,
    task_tag_repository: InMemoryTaskTagRepository,
) -> None:
    result = import_csv(
        "title;project\nPrepare class;English\n",
        project_repository,
        task_repository,
        tag_repository,
        task_tag_repository,
    )

    task = result.created_tasks[0]
    project = project_repository.get_by_id(task.project_id)

    assert task.title == "Prepare class"
    assert project is not None
    assert project.name == "English"


@pytest.mark.revised
def test_importing_csv_allows_commas_inside_task_titles(
    project_repository: InMemoryProjectRepository,
    task_repository: InMemoryTaskRepository,
    tag_repository: InMemoryTagRepository,
    task_tag_repository: InMemoryTaskTagRepository,
) -> None:
    result = import_csv(
        "title;project\nBuy rice, beans, and coffee;Personal\n",
        project_repository,
        task_repository,
        tag_repository,
        task_tag_repository,
    )

    assert result.created_tasks[0].title == "Buy rice, beans, and coffee"


@pytest.mark.revised
def test_importing_csv_with_missing_title_header_fails(
    project_repository: InMemoryProjectRepository,
    task_repository: InMemoryTaskRepository,
    tag_repository: InMemoryTagRepository,
    task_tag_repository: InMemoryTaskTagRepository,
) -> None:
    result = import_csv(
        "project;tags\nWork;urgent\n",
        project_repository,
        task_repository,
        tag_repository,
        task_tag_repository,
    )

    assert result.created_count == 0
    assert result.errors[0].code == "missing_required_header"


@pytest.mark.revised
def test_importing_csv_ignores_unknown_columns(
    project_repository: InMemoryProjectRepository,
    task_repository: InMemoryTaskRepository,
    tag_repository: InMemoryTagRepository,
    task_tag_repository: InMemoryTaskTagRepository,
) -> None:
    result = import_csv(
        "title;unknown\nPrepare class;ignored\n",
        project_repository,
        task_repository,
        tag_repository,
        task_tag_repository,
    )

    assert result.created_tasks[0].title == "Prepare class"


@pytest.mark.revised
def test_importing_csv_matches_headers_case_insensitively(
    project_repository: InMemoryProjectRepository,
    task_repository: InMemoryTaskRepository,
    tag_repository: InMemoryTagRepository,
    task_tag_repository: InMemoryTaskTagRepository,
) -> None:
    result = import_csv(
        "TITLE;PROJECT\nPrepare class;English\n",
        project_repository,
        task_repository,
        tag_repository,
        task_tag_repository,
    )

    task = result.created_tasks[0]
    project = project_repository.get_by_id(task.project_id)

    assert project is not None
    assert project.name == "English"


@pytest.mark.revised
def test_importing_csv_trims_header_names(
    project_repository: InMemoryProjectRepository,
    task_repository: InMemoryTaskRepository,
    tag_repository: InMemoryTagRepository,
    task_tag_repository: InMemoryTaskTagRepository,
) -> None:
    result = import_csv(
        " title ; project \nPrepare class;English\n",
        project_repository,
        task_repository,
        tag_repository,
        task_tag_repository,
    )

    task = result.created_tasks[0]
    project = project_repository.get_by_id(task.project_id)

    assert project is not None
    assert project.name == "English"


@pytest.mark.revised
def test_importing_one_valid_row_creates_one_task(
    project_repository: InMemoryProjectRepository,
    task_repository: InMemoryTaskRepository,
    tag_repository: InMemoryTagRepository,
    task_tag_repository: InMemoryTaskTagRepository,
) -> None:
    result = import_csv(
        "title\nPrepare class\n",
        project_repository,
        task_repository,
        tag_repository,
        task_tag_repository,
    )

    assert result.created_count == 1
    assert task_repository.count() == 1


@pytest.mark.revised
def test_importing_multiple_valid_rows_creates_multiple_tasks(
    project_repository: InMemoryProjectRepository,
    task_repository: InMemoryTaskRepository,
    tag_repository: InMemoryTagRepository,
    task_tag_repository: InMemoryTaskTagRepository,
) -> None:
    result = import_csv(
        "title\nPrepare class\nReview notes\n",
        project_repository,
        task_repository,
        tag_repository,
        task_tag_repository,
    )

    assert result.created_count == 2
    assert task_repository.count() == 2


@pytest.mark.revised
def test_importing_row_trims_task_title(
    project_repository: InMemoryProjectRepository,
    task_repository: InMemoryTaskRepository,
    tag_repository: InMemoryTagRepository,
    task_tag_repository: InMemoryTaskTagRepository,
) -> None:
    task = import_row(
        {"title": "  Prepare class  "},
        project_repository,
        task_repository,
        tag_repository,
        task_tag_repository,
    )

    assert task.title == "Prepare class"


@pytest.mark.revised
def test_importing_row_stores_description_when_provided(
    project_repository: InMemoryProjectRepository,
    task_repository: InMemoryTaskRepository,
    tag_repository: InMemoryTagRepository,
    task_tag_repository: InMemoryTaskTagRepository,
) -> None:
    task = import_row(
        {"title": "Prepare class", "description": " Prepare examples. "},
        project_repository,
        task_repository,
        tag_repository,
        task_tag_repository,
    )

    assert task.description == "Prepare examples."


@pytest.mark.revised
def test_importing_row_stores_none_for_blank_description(
    project_repository: InMemoryProjectRepository,
    task_repository: InMemoryTaskRepository,
    tag_repository: InMemoryTagRepository,
    task_tag_repository: InMemoryTaskTagRepository,
) -> None:
    task = import_row(
        {"title": "Prepare class", "description": "   "},
        project_repository,
        task_repository,
        tag_repository,
        task_tag_repository,
    )

    assert task.description is None


@pytest.mark.revised
def test_importing_row_sets_default_priority_to_none(
    project_repository: InMemoryProjectRepository,
    task_repository: InMemoryTaskRepository,
    tag_repository: InMemoryTagRepository,
    task_tag_repository: InMemoryTaskTagRepository,
) -> None:
    task = import_row(
        {"title": "Prepare class"},
        project_repository,
        task_repository,
        tag_repository,
        task_tag_repository,
    )

    assert task.priority == TaskPriority.NONE


@pytest.mark.revised
def test_importing_row_sets_provided_priority(
    project_repository: InMemoryProjectRepository,
    task_repository: InMemoryTaskRepository,
    tag_repository: InMemoryTagRepository,
    task_tag_repository: InMemoryTaskTagRepository,
) -> None:
    task = import_row(
        {"title": "Prepare class", "priority": " HIGH "},
        project_repository,
        task_repository,
        tag_repository,
        task_tag_repository,
    )

    assert task.priority == TaskPriority.HIGH


@pytest.mark.revised
def test_importing_row_parses_due_date(
    project_repository: InMemoryProjectRepository,
    task_repository: InMemoryTaskRepository,
    tag_repository: InMemoryTagRepository,
    task_tag_repository: InMemoryTaskTagRepository,
) -> None:
    task = import_row(
        {"title": "Prepare class", "due_date": "2026-05-01"},
        project_repository,
        task_repository,
        tag_repository,
        task_tag_repository,
    )

    assert task.due_date == date(2026, 5, 1)


@pytest.mark.revised
def test_importing_row_stores_none_for_blank_due_date(
    project_repository: InMemoryProjectRepository,
    task_repository: InMemoryTaskRepository,
    tag_repository: InMemoryTagRepository,
    task_tag_repository: InMemoryTaskTagRepository,
) -> None:
    task = import_row(
        {"title": "Prepare class", "due_date": "   "},
        project_repository,
        task_repository,
        tag_repository,
        task_tag_repository,
    )

    assert task.due_date is None


@pytest.mark.revised
def test_importing_row_with_project_creates_project_when_missing(
    project_repository: InMemoryProjectRepository,
    task_repository: InMemoryTaskRepository,
    tag_repository: InMemoryTagRepository,
    task_tag_repository: InMemoryTaskTagRepository,
) -> None:
    task = import_row(
        {"title": "Prepare class", "project": "English"},
        project_repository,
        task_repository,
        tag_repository,
        task_tag_repository,
    )

    project = project_repository.get_by_id(task.project_id)

    assert project is not None
    assert project.name == "English"


@pytest.mark.revised
def test_importing_row_with_existing_project_reuses_it(
    project_repository: InMemoryProjectRepository,
    task_repository: InMemoryTaskRepository,
    tag_repository: InMemoryTagRepository,
    task_tag_repository: InMemoryTaskTagRepository,
) -> None:
    project = create_project(project_repository, name="English")

    task = import_row(
        {"title": "Prepare class", "project": "english"},
        project_repository,
        task_repository,
        tag_repository,
        task_tag_repository,
    )

    assert task.project_id == project.id
    assert project_repository.count() == 1


@pytest.mark.revised
def test_importing_row_without_project_uses_inbox(
    project_repository: InMemoryProjectRepository,
    task_repository: InMemoryTaskRepository,
    tag_repository: InMemoryTagRepository,
    task_tag_repository: InMemoryTaskTagRepository,
) -> None:
    task = import_row(
        {"title": "Capture idea"},
        project_repository,
        task_repository,
        tag_repository,
        task_tag_repository,
    )

    inbox = project_repository.get_by_name("Inbox")

    assert inbox is not None
    assert task.project_id == inbox.id


@pytest.mark.revised
def test_importing_row_with_blank_project_uses_inbox(
    project_repository: InMemoryProjectRepository,
    task_repository: InMemoryTaskRepository,
    tag_repository: InMemoryTagRepository,
    task_tag_repository: InMemoryTaskTagRepository,
) -> None:
    task = import_row(
        {"title": "Capture idea", "project": "   "},
        project_repository,
        task_repository,
        tag_repository,
        task_tag_repository,
    )

    inbox = project_repository.get_by_name("Inbox")

    assert inbox is not None
    assert task.project_id == inbox.id


@pytest.mark.revised
def test_importing_rows_with_equivalent_project_names_does_not_duplicate_projects(
    project_repository: InMemoryProjectRepository,
    task_repository: InMemoryTaskRepository,
    tag_repository: InMemoryTagRepository,
    task_tag_repository: InMemoryTaskTagRepository,
) -> None:
    import_csv(
        "title;project\nFirst task; English \nSecond task;english\n",
        project_repository,
        task_repository,
        tag_repository,
        task_tag_repository,
    )

    assert project_repository.count() == 1


@pytest.mark.revised
def test_importing_row_with_tags_creates_missing_tags(
    project_repository: InMemoryProjectRepository,
    task_repository: InMemoryTaskRepository,
    tag_repository: InMemoryTagRepository,
    task_tag_repository: InMemoryTaskTagRepository,
) -> None:
    import_row(
        {"title": "Prepare class", "tags": "urgent,deep-work"},
        project_repository,
        task_repository,
        tag_repository,
        task_tag_repository,
    )

    assert tag_repository.count() == 2


@pytest.mark.revised
def test_importing_row_with_tags_reuses_existing_tags(
    project_repository: InMemoryProjectRepository,
    task_repository: InMemoryTaskRepository,
    tag_repository: InMemoryTagRepository,
    task_tag_repository: InMemoryTaskTagRepository,
) -> None:
    existing_tag = create_tag(tag_repository, name="urgent")

    import_row(
        {"title": "Prepare class", "tags": "#URGENT,review"},
        project_repository,
        task_repository,
        tag_repository,
        task_tag_repository,
    )

    assert tag_repository.get_by_name("urgent") == existing_tag
    assert tag_repository.count() == 2


@pytest.mark.revised
def test_importing_row_attaches_tags_to_created_task(
    project_repository: InMemoryProjectRepository,
    task_repository: InMemoryTaskRepository,
    tag_repository: InMemoryTagRepository,
    task_tag_repository: InMemoryTaskTagRepository,
) -> None:
    task = import_row(
        {"title": "Prepare class", "tags": "urgent,review"},
        project_repository,
        task_repository,
        tag_repository,
        task_tag_repository,
    )

    assert list_task_tag_names(task, tag_repository, task_tag_repository) == [
        "review",
        "urgent",
    ]


@pytest.mark.revised
def test_importing_row_normalizes_tag_names(
    project_repository: InMemoryProjectRepository,
    task_repository: InMemoryTaskRepository,
    tag_repository: InMemoryTagRepository,
    task_tag_repository: InMemoryTaskTagRepository,
) -> None:
    task = import_row(
        {"title": "Prepare class", "tags": "#URGENT,Deep Work"},
        project_repository,
        task_repository,
        tag_repository,
        task_tag_repository,
    )

    assert list_task_tag_names(task, tag_repository, task_tag_repository) == [
        "deep-work",
        "urgent",
    ]


@pytest.mark.revised
def test_importing_row_ignores_duplicate_tag_names(
    project_repository: InMemoryProjectRepository,
    task_repository: InMemoryTaskRepository,
    tag_repository: InMemoryTagRepository,
    task_tag_repository: InMemoryTaskTagRepository,
) -> None:
    task = import_row(
        {"title": "Prepare class", "tags": "urgent,#URGENT, urgent "},
        project_repository,
        task_repository,
        tag_repository,
        task_tag_repository,
    )

    assert tag_repository.count() == 1
    assert task_tag_repository.count_for_task(task.id) == 1


@pytest.mark.revised
def test_importing_row_with_blank_tags_creates_no_task_tag_relationships(
    project_repository: InMemoryProjectRepository,
    task_repository: InMemoryTaskRepository,
    tag_repository: InMemoryTagRepository,
    task_tag_repository: InMemoryTaskTagRepository,
) -> None:
    task = import_row(
        {"title": "Prepare class", "tags": "   "},
        project_repository,
        task_repository,
        tag_repository,
        task_tag_repository,
    )

    assert task_tag_repository.count_for_task(task.id) == 0


@pytest.mark.revised
def test_parsing_tag_cell_splits_tags_by_comma() -> None:
    tags = parse_tag_cell("urgent,review")

    assert tags == ["urgent", "review"]


@pytest.mark.revised
def test_parsing_tag_cell_ignores_blank_tag_items() -> None:
    tags = parse_tag_cell("urgent, ,review,,")

    assert tags == ["urgent", "review"]


@pytest.mark.revised
def test_parsing_tag_cell_preserves_first_seen_order_after_normalization() -> None:
    tags = parse_tag_cell("Deep Work,urgent,deep-work,#review")

    assert tags == ["deep-work", "urgent", "review"]


@pytest.mark.revised
def test_importing_duplicate_task_in_same_project_skips_duplicate_row(
    project_repository: InMemoryProjectRepository,
    task_repository: InMemoryTaskRepository,
    tag_repository: InMemoryTagRepository,
    task_tag_repository: InMemoryTaskTagRepository,
) -> None:
    result = import_csv(
        "title;project\nPrepare class;English\n prepare class ;english\n",
        project_repository,
        task_repository,
        tag_repository,
        task_tag_repository,
    )

    assert result.created_count == 1
    assert result.skipped_count == 1


@pytest.mark.revised
def test_importing_duplicate_task_titles_in_different_projects_creates_both(
    project_repository: InMemoryProjectRepository,
    task_repository: InMemoryTaskRepository,
    tag_repository: InMemoryTagRepository,
    task_tag_repository: InMemoryTaskTagRepository,
) -> None:
    result = import_csv(
        "title;project\nPrepare class;English\nPrepare class;Work\n",
        project_repository,
        task_repository,
        tag_repository,
        task_tag_repository,
    )

    assert result.created_count == 2
    assert task_repository.count() == 2


@pytest.mark.revised
def test_importing_duplicate_rows_reports_duplicate_task_errors(
    project_repository: InMemoryProjectRepository,
    task_repository: InMemoryTaskRepository,
    tag_repository: InMemoryTagRepository,
    task_tag_repository: InMemoryTaskTagRepository,
) -> None:
    result = import_csv(
        "title;project\nPrepare class;English\nPREPARE CLASS;English\n",
        project_repository,
        task_repository,
        tag_repository,
        task_tag_repository,
    )

    assert error_codes(result) == ["duplicate_task"]


@pytest.mark.revised
def test_importing_duplicate_rows_continues_importing_later_valid_rows(
    project_repository: InMemoryProjectRepository,
    task_repository: InMemoryTaskRepository,
    tag_repository: InMemoryTagRepository,
    task_tag_repository: InMemoryTaskTagRepository,
) -> None:
    result = import_csv(
        "title;project\nPrepare class;English\nPREPARE CLASS;English\nReview;English\n",
        project_repository,
        task_repository,
        tag_repository,
        task_tag_repository,
    )

    assert result.created_count == 2
    assert [task.title for task in result.created_tasks] == ["Prepare class", "Review"]


@pytest.mark.revised
def test_importing_row_with_blank_title_reports_invalid_title_error(
    project_repository: InMemoryProjectRepository,
    task_repository: InMemoryTaskRepository,
    tag_repository: InMemoryTagRepository,
    task_tag_repository: InMemoryTaskTagRepository,
) -> None:
    result = import_csv(
        "title;project\n ;Work\n",
        project_repository,
        task_repository,
        tag_repository,
        task_tag_repository,
    )

    assert result.errors[0].code == "invalid_title"


@pytest.mark.revised
def test_importing_row_with_invalid_priority_reports_invalid_priority_error(
    project_repository: InMemoryProjectRepository,
    task_repository: InMemoryTaskRepository,
    tag_repository: InMemoryTagRepository,
    task_tag_repository: InMemoryTaskTagRepository,
) -> None:
    result = import_csv(
        "title;priority\nPrepare class;urgent\n",
        project_repository,
        task_repository,
        tag_repository,
        task_tag_repository,
    )

    assert result.errors[0].code == "invalid_priority"


@pytest.mark.revised
def test_importing_row_with_invalid_due_date_reports_invalid_due_date_error(
    project_repository: InMemoryProjectRepository,
    task_repository: InMemoryTaskRepository,
    tag_repository: InMemoryTagRepository,
    task_tag_repository: InMemoryTaskTagRepository,
) -> None:
    result = import_csv(
        "title;due_date\nPrepare class;2026-02-31\n",
        project_repository,
        task_repository,
        tag_repository,
        task_tag_repository,
    )

    assert result.errors[0].code == "invalid_due_date"


@pytest.mark.revised
def test_importing_row_with_datetime_due_date_reports_invalid_due_date_error(
    project_repository: InMemoryProjectRepository,
    task_repository: InMemoryTaskRepository,
    tag_repository: InMemoryTagRepository,
    task_tag_repository: InMemoryTaskTagRepository,
) -> None:
    result = import_csv(
        "title;due_date\nPrepare class;2026-05-01T10:00:00\n",
        project_repository,
        task_repository,
        tag_repository,
        task_tag_repository,
    )

    assert result.errors[0].code == "invalid_due_date"


@pytest.mark.revised
def test_importing_invalid_rows_does_not_create_tasks_for_those_rows(
    project_repository: InMemoryProjectRepository,
    task_repository: InMemoryTaskRepository,
    tag_repository: InMemoryTagRepository,
    task_tag_repository: InMemoryTaskTagRepository,
) -> None:
    result = import_csv(
        "title;priority\nValid task;low\nInvalid task;urgent\n",
        project_repository,
        task_repository,
        tag_repository,
        task_tag_repository,
    )

    assert result.created_count == 1
    assert task_repository.count() == 1


@pytest.mark.revised
def test_importing_invalid_rows_still_imports_later_valid_rows(
    project_repository: InMemoryProjectRepository,
    task_repository: InMemoryTaskRepository,
    tag_repository: InMemoryTagRepository,
    task_tag_repository: InMemoryTaskTagRepository,
) -> None:
    result = import_csv(
        "title;priority\nInvalid task;urgent\nLater valid task;medium\n",
        project_repository,
        task_repository,
        tag_repository,
        task_tag_repository,
    )

    assert result.created_count == 1
    assert result.created_tasks[0].title == "Later valid task"


@pytest.mark.revised
def test_import_errors_include_row_numbers_based_on_csv_data_rows(
    project_repository: InMemoryProjectRepository,
    task_repository: InMemoryTaskRepository,
    tag_repository: InMemoryTagRepository,
    task_tag_repository: InMemoryTaskTagRepository,
) -> None:
    result = import_csv(
        "title;project\nValid task;Work\n ;Work\nAnother task;Work\n",
        project_repository,
        task_repository,
        tag_repository,
        task_tag_repository,´
    )

    assert result.errors[0].row_number == 3


@pytest.mark.revised
def test_import_result_reports_processed_row_count(
    project_repository: InMemoryProjectRepository,
    task_repository: InMemoryTaskRepository,
    tag_repository: InMemoryTagRepository,
    task_tag_repository: InMemoryTaskTagRepository,
) -> None:
    result = import_csv(
        "title\nFirst task\nSecond task\n",
        project_repository,
        task_repository,
        tag_repository,
        task_tag_repository,
    )

    assert result.processed_rows == 2


@pytest.mark.revised
def test_import_result_reports_created_task_count(
    project_repository: InMemoryProjectRepository,
    task_repository: InMemoryTaskRepository,
    tag_repository: InMemoryTagRepository,
    task_tag_repository: InMemoryTaskTagRepository,
) -> None:
    result = import_csv(
        "title\nFirst task\nSecond task\n",
        project_repository,
        task_repository,
        tag_repository,
        task_tag_repository,
    )

    assert result.created_count == 2


@pytest.mark.revised
def test_import_result_reports_skipped_row_count(
    project_repository: InMemoryProjectRepository,
    task_repository: InMemoryTaskRepository,
    tag_repository: InMemoryTagRepository,
    task_tag_repository: InMemoryTaskTagRepository,
) -> None:
    result = import_csv(
        "title\nFirst task\nFIRST TASK\n \n",
        project_repository,
        task_repository,
        tag_repository,
        task_tag_repository,
    )

    assert result.skipped_count == 2


@pytest.mark.revised
def test_import_result_includes_created_tasks(
    project_repository: InMemoryProjectRepository,
    task_repository: InMemoryTaskRepository,
    tag_repository: InMemoryTagRepository,
    task_tag_repository: InMemoryTaskTagRepository,
) -> None:
    result = import_csv(
        "title\nFirst task\nSecond task\n",
        project_repository,
        task_repository,
        tag_repository,
        task_tag_repository,
    )

    assert [task.title for task in result.created_tasks] == [
        "First task",
        "Second task",
    ]


@pytest.mark.revised
def test_import_result_includes_validation_errors(
    project_repository: InMemoryProjectRepository,
    task_repository: InMemoryTaskRepository,
    tag_repository: InMemoryTagRepository,
    task_tag_repository: InMemoryTaskTagRepository,
) -> None:
    result = import_csv(
        "title;priority\nValid task;low\nInvalid task;urgent\n",
        project_repository,
        task_repository,
        tag_repository,
        task_tag_repository,
    )

    assert len(result.errors) == 1
    assert result.errors[0].message
