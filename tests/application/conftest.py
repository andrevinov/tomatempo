from __future__ import annotations

from collections.abc import Iterable
from typing import TYPE_CHECKING, Protocol
from uuid import UUID

import pytest

from tomatempo.application.use_cases import CreateProject, CreateTask
from tomatempo.domain.entities import Project, Task

if TYPE_CHECKING:
    from tomatempo.domain.entities import Tag


class ProjectRepositoryContract(Protocol):
    def save(self, project: Project) -> Project: ...

    def get_by_id(self, project_id: UUID) -> Project | None: ...

    def get_by_name(self, name: str) -> Project | None: ...

    def list(self) -> Iterable[Project]: ...


class TaskRepositoryContract(Protocol):
    def save(self, task: Task) -> Task: ...

    def get_by_id(self, task_id: UUID) -> Task | None: ...

    def get_by_project_and_title(self, project_id: UUID, title: str) -> Task | None: ...

    def list(self) -> Iterable[Task]: ...


def normalized_project_name(value: str) -> str:
    return value.strip().casefold()


def normalized_task_title(value: str) -> str:
    return value.strip().casefold()


def normalized_tag_name(value: str) -> str:
    return value.strip().removeprefix("#").replace(" ", "-").casefold()


class InMemoryProjectRepository:
    def __init__(self) -> None:
        self.projects: dict[UUID, Project] = {}

    def save(self, project: Project) -> Project:
        self.projects[project.id] = project
        return project

    def get_by_id(self, project_id: UUID) -> Project | None:
        return self.projects.get(project_id)

    def get_by_name(self, name: str) -> Project | None:
        normalized_name = normalized_project_name(name)
        return next(
            (
                project
                for project in self.projects.values()
                if normalized_project_name(project.name) == normalized_name
            ),
            None,
        )

    def list(self) -> Iterable[Project]:
        return self.projects.values()

    def count(self) -> int:
        return len(self.projects)


class InMemoryTaskRepository:
    def __init__(self) -> None:
        self.tasks: dict[UUID, Task] = {}

    def save(self, task: Task) -> Task:
        self.tasks[task.id] = task
        return task

    def get_by_id(self, task_id: UUID) -> Task | None:
        return self.tasks.get(task_id)

    def get_by_project_and_title(self, project_id: UUID, title: str) -> Task | None:
        normalized_title = normalized_task_title(title)
        return next(
            (
                task
                for task in self.tasks.values()
                if task.project_id == project_id
                and normalized_task_title(task.title) == normalized_title
            ),
            None,
        )

    def list(self) -> Iterable[Task]:
        return self.tasks.values()

    def count(self) -> int:
        return len(self.tasks)


class InMemoryTagRepository:
    def __init__(self) -> None:
        self.tags: dict[UUID, Tag] = {}

    def save(self, tag: Tag) -> Tag:
        self.tags[tag.id] = tag
        return tag

    def get_by_id(self, tag_id: UUID) -> Tag | None:
        return self.tags.get(tag_id)

    def get_by_name(self, name: str) -> Tag | None:
        normalized_name = normalized_tag_name(name)
        return next(
            (
                tag
                for tag in self.tags.values()
                if normalized_tag_name(tag.name) == normalized_name
            ),
            None,
        )

    def list(self) -> Iterable[Tag]:
        return self.tags.values()

    def count(self) -> int:
        return len(self.tags)


class InMemoryTaskTagRepository:
    def __init__(self) -> None:
        self.relationships: set[tuple[UUID, UUID]] = set()

    def attach(self, task_id: UUID, tag_id: UUID) -> bool:
        relationship = (task_id, tag_id)
        if relationship in self.relationships:
            return False

        self.relationships.add(relationship)
        return True

    def remove(self, task_id: UUID, tag_id: UUID) -> bool:
        relationship = (task_id, tag_id)
        if relationship not in self.relationships:
            return False

        self.relationships.remove(relationship)
        return True

    def replace_for_task(self, task_id: UUID, tag_ids: set[UUID]) -> bool:
        current_relationships = {
            relationship
            for relationship in self.relationships
            if relationship[0] == task_id
        }
        next_relationships = {(task_id, tag_id) for tag_id in tag_ids}
        if current_relationships == next_relationships:
            return False

        self.relationships.difference_update(current_relationships)
        self.relationships.update(next_relationships)
        return True

    def list_tag_ids_for_task(self, task_id: UUID) -> set[UUID]:
        return {
            tag_id
            for relationship_task_id, tag_id in self.relationships
            if relationship_task_id == task_id
        }

    def count_for_task(self, task_id: UUID) -> int:
        return len(self.list_tag_ids_for_task(task_id))


@pytest.fixture
def project_repository() -> InMemoryProjectRepository:
    return InMemoryProjectRepository()


@pytest.fixture
def task_repository() -> InMemoryTaskRepository:
    return InMemoryTaskRepository()


@pytest.fixture
def tag_repository() -> InMemoryTagRepository:
    return InMemoryTagRepository()


@pytest.fixture
def task_tag_repository() -> InMemoryTaskTagRepository:
    return InMemoryTaskTagRepository()


@pytest.fixture
def task(
    project_repository: InMemoryProjectRepository,
    task_repository: InMemoryTaskRepository,
) -> Task:
    project = CreateProject(project_repository).execute("Tomatempo")
    return CreateTask(task_repository, project_repository).execute(
        title="Prepare release notes",
        project_id=project.id,
    )


def create_project(
    project_repository: ProjectRepositoryContract,
    name: str = "Tomatempo",
) -> Project:
    return CreateProject(project_repository).execute(name=name)


def create_task(
    task_repository: TaskRepositoryContract,
    project_repository: ProjectRepositoryContract,
    title: str = "Prepare class",
    project_id: UUID | None = None,
) -> Task:
    return CreateTask(task_repository, project_repository).execute(
        title=title,
        project_id=project_id,
    )


def create_tag(tag_repository: InMemoryTagRepository, name: str = "urgent") -> Tag:
    from tomatempo.application.use_cases import CreateTag

    return CreateTag(tag_repository).execute(name=name)


def list_task_tag_names(
    task: Task,
    tag_repository: InMemoryTagRepository,
    task_tag_repository: InMemoryTaskTagRepository,
) -> list[str]:
    from tomatempo.application.use_cases import ListTaskTags

    return [
        tag.name
        for tag in ListTaskTags(tag_repository, task_tag_repository).execute(task.id)
    ]
