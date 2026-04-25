from collections.abc import Iterable
from uuid import UUID

from tomatempo.application.ports import (
    TagRepository,
    TaskRepository,
    TaskTagRepository,
)
from tomatempo.application.tasks import (
    get_task_or_raise,
    save_task_with_updated_timestamp,
)
from tomatempo.domain.entities import Tag, Task
from tomatempo.domain.exceptions import DuplicateTagNameError, InvalidTagNameError


def normalize_required_tag_name(name: str) -> str:
    without_hash = name.strip().removeprefix("#").strip()
    if not without_hash:
        raise InvalidTagNameError
    return "-".join(without_hash.split()).casefold()


class CreateTag:
    def __init__(self, tag_repository: TagRepository) -> None:
        self.tag_repository = tag_repository

    def execute(self, name: str) -> Tag:
        normalized_name = normalize_required_tag_name(name)
        if self.tag_repository.get_by_name(normalized_name) is not None:
            raise DuplicateTagNameError

        return self.tag_repository.save(Tag(name=normalized_name))


class GetOrCreateTagByName:
    def __init__(self, tag_repository: TagRepository) -> None:
        self.tag_repository = tag_repository

    def execute(self, name: str) -> Tag:
        normalized_name = normalize_required_tag_name(name)
        existing_tag = self.tag_repository.get_by_name(normalized_name)
        if existing_tag is not None:
            return existing_tag

        return self.tag_repository.save(Tag(name=normalized_name))


class AttachTagToTask:
    def __init__(
        self,
        task_repository: TaskRepository,
        tag_repository: TagRepository,
        task_tag_repository: TaskTagRepository,
    ) -> None:
        self.task_repository = task_repository
        self.tag_repository = tag_repository
        self.task_tag_repository = task_tag_repository

    def execute(self, task_id: UUID, tag_name: str) -> Task:
        task = get_task_or_raise(self.task_repository, task_id)
        tag = GetOrCreateTagByName(self.tag_repository).execute(tag_name)
        attached = self.task_tag_repository.attach(task.id, tag.id)
        if not attached:
            return task

        return save_task_with_updated_timestamp(self.task_repository, task)


class AttachTagsToTask:
    def __init__(
        self,
        task_repository: TaskRepository,
        tag_repository: TagRepository,
        task_tag_repository: TaskTagRepository,
    ) -> None:
        self.task_repository = task_repository
        self.tag_repository = tag_repository
        self.task_tag_repository = task_tag_repository

    def execute(self, task_id: UUID, tag_names: Iterable[str]) -> Task:
        task = get_task_or_raise(self.task_repository, task_id)
        changed = False
        for tag_name in unique_normalized_tag_names(tag_names):
            tag = GetOrCreateTagByName(self.tag_repository).execute(tag_name)
            changed = self.task_tag_repository.attach(task.id, tag.id) or changed

        if not changed:
            return task

        return save_task_with_updated_timestamp(self.task_repository, task)


class RemoveTagFromTask:
    def __init__(
        self,
        task_repository: TaskRepository,
        tag_repository: TagRepository,
        task_tag_repository: TaskTagRepository,
    ) -> None:
        self.task_repository = task_repository
        self.tag_repository = tag_repository
        self.task_tag_repository = task_tag_repository

    def execute(self, task_id: UUID, tag_name: str) -> Task:
        task = get_task_or_raise(self.task_repository, task_id)
        tag = self.tag_repository.get_by_name(normalize_required_tag_name(tag_name))
        if tag is None:
            return task

        removed = self.task_tag_repository.remove(task.id, tag.id)
        if not removed:
            return task

        return save_task_with_updated_timestamp(self.task_repository, task)


class ReplaceTaskTags:
    def __init__(
        self,
        task_repository: TaskRepository,
        tag_repository: TagRepository,
        task_tag_repository: TaskTagRepository,
    ) -> None:
        self.task_repository = task_repository
        self.tag_repository = tag_repository
        self.task_tag_repository = task_tag_repository

    def execute(self, task_id: UUID, tag_names: Iterable[str]) -> Task:
        task = get_task_or_raise(self.task_repository, task_id)
        tags = [
            GetOrCreateTagByName(self.tag_repository).execute(tag_name)
            for tag_name in unique_normalized_tag_names(tag_names)
        ]
        changed = self.task_tag_repository.replace_for_task(
            task.id,
            {tag.id for tag in tags},
        )
        if not changed:
            return task

        return save_task_with_updated_timestamp(self.task_repository, task)


class ListTaskTags:
    def __init__(
        self,
        tag_repository: TagRepository,
        task_tag_repository: TaskTagRepository,
    ) -> None:
        self.tag_repository = tag_repository
        self.task_tag_repository = task_tag_repository

    def execute(self, task_id: UUID) -> list[Tag]:
        tags = [
            tag
            for tag_id in self.task_tag_repository.list_tag_ids_for_task(task_id)
            if (tag := self.tag_repository.get_by_id(tag_id)) is not None
        ]
        return sorted(tags, key=lambda tag: tag.name)


def unique_normalized_tag_names(tag_names: Iterable[str]) -> list[str]:
    names: list[str] = []
    seen: set[str] = set()
    for tag_name in tag_names:
        normalized_name = normalize_required_tag_name(tag_name)
        if normalized_name not in seen:
            names.append(normalized_name)
            seen.add(normalized_name)
    return names
