from tomatempo.application.ports import ProjectRepository
from tomatempo.domain.entities import Project
from tomatempo.domain.exceptions import (
    DuplicateProjectNameError,
    InvalidProjectNameError,
)

DEFAULT_PROJECT_NAME = "Inbox"


def normalize_required_project_name(name: str) -> str:
    normalized_name = name.strip()
    if not normalized_name:
        raise InvalidProjectNameError
    return normalized_name


class CreateProject:
    def __init__(self, project_repository: ProjectRepository) -> None:
        self.project_repository = project_repository

    def execute(self, name: str) -> Project:
        normalized_name = normalize_required_project_name(name)
        if self.project_repository.get_by_name(normalized_name) is not None:
            raise DuplicateProjectNameError

        return self.project_repository.save(Project(name=normalized_name))


class GetOrCreateProjectByName:
    def __init__(self, project_repository: ProjectRepository) -> None:
        self.project_repository = project_repository

    def execute(self, name: str) -> Project:
        normalized_name = normalize_required_project_name(name)
        existing_project = self.project_repository.get_by_name(normalized_name)
        if existing_project is not None:
            return existing_project

        return self.project_repository.save(Project(name=normalized_name))
