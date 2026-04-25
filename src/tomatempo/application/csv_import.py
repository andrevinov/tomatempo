import csv
from dataclasses import dataclass, field
from datetime import date
from io import StringIO

from tomatempo.application.ports import (
    ProjectRepository,
    TagRepository,
    TaskRepository,
    TaskTagRepository,
)
from tomatempo.application.projects import GetOrCreateProjectByName
from tomatempo.application.tags import AttachTagsToTask, normalize_required_tag_name
from tomatempo.application.tasks import CreateTask, UpdateTask
from tomatempo.domain.entities import Task
from tomatempo.domain.exceptions import (
    DuplicateTaskTitleError,
    InvalidTaskPriorityError,
    InvalidTaskTitleError,
)
from tomatempo.domain.value_objects import TaskPriority

SUPPORTED_HEADERS = {"description", "due_date", "priority", "project", "tags", "title"}


@dataclass(frozen=True)
class CsvImportError:
    row_number: int
    code: str
    message: str


@dataclass(frozen=True)
class CsvImportResult:
    processed_rows: int = 0
    created_count: int = 0
    skipped_count: int = 0
    errors: list[CsvImportError] = field(default_factory=list)
    created_tasks: list[Task] = field(default_factory=list)


class ImportCsvRow:
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

    def execute(self, row: dict[str, str], row_number: int) -> Task:
        title = row.get("title", "")
        project_name = normalized_optional_value(row.get("project")) or "Inbox"
        description = normalized_optional_value(row.get("description"))
        priority = parse_priority(row.get("priority"))
        due_date = parse_due_date(row.get("due_date"))
        tag_names = parse_tag_cell(row.get("tags", ""))

        project = GetOrCreateProjectByName(self.project_repository).execute(
            project_name
        )
        task = CreateTask(self.task_repository, self.project_repository).execute(
            title=title,
            project_id=project.id,
        )

        should_update_task = (
            description is not None
            or priority != TaskPriority.NONE
            or due_date is not None
        )
        if should_update_task:
            task = UpdateTask(self.task_repository, self.project_repository).execute(
                task.id,
                description=description,
                priority=priority,
                due_date=due_date,
            )

        if tag_names:
            task = AttachTagsToTask(
                self.task_repository,
                self.tag_repository,
                self.task_tag_repository,
            ).execute(task.id, tag_names)

        return task


class ImportTasksFromCsvText:
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

    def execute(self, csv_text: str) -> CsvImportResult:
        if not csv_text.strip():
            return CsvImportResult(
                errors=[
                    CsvImportError(
                        row_number=0,
                        code="empty_csv",
                        message="CSV input is empty.",
                    )
                ]
            )

        reader = csv.reader(StringIO(csv_text), delimiter=";")
        try:
            headers = next(reader)
        except StopIteration:
            return CsvImportResult(
                errors=[
                    CsvImportError(
                        row_number=0,
                        code="empty_csv",
                        message="CSV input is empty.",
                    )
                ]
            )

        normalized_headers = [normalize_header(header) for header in headers]
        if "title" not in normalized_headers:
            return CsvImportResult(
                errors=[
                    CsvImportError(
                        row_number=1,
                        code="missing_required_header",
                        message="Missing required title header.",
                    )
                ]
            )

        created_tasks: list[Task] = []
        errors: list[CsvImportError] = []
        processed_rows = 0

        for row_number, values in enumerate(reader, start=2):
            processed_rows += 1
            row = normalize_row(normalized_headers, values)
            try:
                task = ImportCsvRow(
                    self.task_repository,
                    self.project_repository,
                    self.tag_repository,
                    self.task_tag_repository,
                ).execute(row=row, row_number=row_number)
            except InvalidTaskTitleError:
                errors.append(import_error(row_number, "invalid_title"))
            except InvalidTaskPriorityError:
                errors.append(import_error(row_number, "invalid_priority"))
            except ValueError as exc:
                if str(exc) == "invalid_due_date":
                    errors.append(import_error(row_number, "invalid_due_date"))
                else:
                    raise
            except DuplicateTaskTitleError:
                errors.append(import_error(row_number, "duplicate_task"))
            else:
                created_tasks.append(task)

        return CsvImportResult(
            processed_rows=processed_rows,
            created_count=len(created_tasks),
            skipped_count=len(errors),
            errors=errors,
            created_tasks=created_tasks,
        )


def parse_tag_cell(tag_cell: str) -> list[str]:
    tag_names: list[str] = []
    seen: set[str] = set()
    for raw_tag_name in tag_cell.split(","):
        if not raw_tag_name.strip():
            continue
        tag_name = normalize_required_tag_name(raw_tag_name)
        if tag_name not in seen:
            tag_names.append(tag_name)
            seen.add(tag_name)
    return tag_names


def parse_priority(raw_priority: str | None) -> TaskPriority:
    priority = normalized_optional_value(raw_priority)
    if priority is None:
        return TaskPriority.NONE

    try:
        return TaskPriority(priority.casefold())
    except ValueError as exc:
        raise InvalidTaskPriorityError from exc


def parse_due_date(raw_due_date: str | None) -> date | None:
    due_date = normalized_optional_value(raw_due_date)
    if due_date is None:
        return None
    if "T" in due_date:
        raise ValueError("invalid_due_date")

    try:
        return date.fromisoformat(due_date)
    except ValueError as exc:
        raise ValueError("invalid_due_date") from exc


def normalized_optional_value(value: str | None) -> str | None:
    if value is None:
        return None
    normalized_value = value.strip()
    return normalized_value or None


def normalize_header(header: str) -> str:
    return header.strip().casefold()


def normalize_row(headers: list[str], values: list[str]) -> dict[str, str]:
    row: dict[str, str] = {}
    for header, value in zip(headers, values, strict=False):
        if header in SUPPORTED_HEADERS:
            row[header] = value
    return row


def import_error(row_number: int, code: str) -> CsvImportError:
    return CsvImportError(
        row_number=row_number,
        code=code,
        message=code.replace("_", " "),
    )
