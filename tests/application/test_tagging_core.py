from __future__ import annotations

import pytest

from tomatempo.application.use_cases import (
    AttachTagsToTask,
    AttachTagToTask,
    GetOrCreateTagByName,
    ListTaskTags,
    RemoveTagFromTask,
    ReplaceTaskTags,
)
from tomatempo.domain.entities import Task
from tomatempo.domain.exceptions import DuplicateTagNameError, InvalidTagNameError

from .conftest import (
    InMemoryTagRepository,
    InMemoryTaskRepository,
    InMemoryTaskTagRepository,
    create_tag,
    list_task_tag_names,
)


@pytest.mark.revised
def test_creating_tag_with_valid_name_succeeds(
    tag_repository: InMemoryTagRepository,
) -> None:
    tag = create_tag(tag_repository, name="urgent")

    assert tag.name == "urgent"
    assert tag.id is not None
    assert tag.created_at is not None
    assert tag.updated_at is not None


@pytest.mark.revised
def test_creating_tag_trims_leading_and_trailing_spaces(
    tag_repository: InMemoryTagRepository,
) -> None:
    tag = create_tag(tag_repository, name="  urgent  ")

    assert tag.name == "urgent"


@pytest.mark.revised
def test_creating_tag_removes_leading_hash(
    tag_repository: InMemoryTagRepository,
) -> None:
    tag = create_tag(tag_repository, name="#urgent")

    assert tag.name == "urgent"


@pytest.mark.revised
def test_creating_tag_converts_name_to_lowercase(
    tag_repository: InMemoryTagRepository,
) -> None:
    tag = create_tag(tag_repository, name="URGENT")

    assert tag.name == "urgent"


@pytest.mark.revised
def test_creating_tag_converts_internal_spaces_to_hyphens(
    tag_repository: InMemoryTagRepository,
) -> None:
    tag = create_tag(tag_repository, name="Deep Work")

    assert tag.name == "deep-work"


@pytest.mark.revised
@pytest.mark.parametrize("invalid_name", ["", "   "])
def test_creating_tag_with_empty_or_blank_name_fails(
    tag_repository: InMemoryTagRepository,
    invalid_name: str,
) -> None:
    with pytest.raises(InvalidTagNameError):
        create_tag(tag_repository, name=invalid_name)


@pytest.mark.revised
def test_creating_duplicated_tag_fails(
    tag_repository: InMemoryTagRepository,
) -> None:
    create_tag(tag_repository, name="urgent")

    with pytest.raises(DuplicateTagNameError):
        create_tag(tag_repository, name="urgent")


def test_tag_uniqueness_is_case_insensitive(
    tag_repository: InMemoryTagRepository,
) -> None:
    create_tag(tag_repository, name="urgent")

    with pytest.raises(DuplicateTagNameError):
        create_tag(tag_repository, name="URGENT")


def test_tag_uniqueness_treats_spaces_and_hyphens_as_equivalent(
    tag_repository: InMemoryTagRepository,
) -> None:
    create_tag(tag_repository, name="Deep Work")

    with pytest.raises(DuplicateTagNameError):
        create_tag(tag_repository, name="deep-work")


@pytest.mark.revised
def test_tag_uniqueness_ignores_leading_hash(
    tag_repository: InMemoryTagRepository,
) -> None:
    create_tag(tag_repository, name="urgent")

    with pytest.raises(DuplicateTagNameError):
        create_tag(tag_repository, name="#urgent")


@pytest.mark.revised
def test_getting_or_creating_existing_tag_returns_existing_tag(
    tag_repository: InMemoryTagRepository,
) -> None:
    existing_tag = create_tag(tag_repository, name="urgent")

    tag = GetOrCreateTagByName(tag_repository).execute("urgent")

    assert tag.id == existing_tag.id


@pytest.mark.revised
def test_getting_or_creating_missing_tag_creates_it(
    tag_repository: InMemoryTagRepository,
) -> None:
    tag = GetOrCreateTagByName(tag_repository).execute("urgent")

    assert tag.name == "urgent"
    assert tag_repository.count() == 1


@pytest.mark.revised
def test_getting_or_creating_tag_does_not_create_duplicates(
    tag_repository: InMemoryTagRepository,
) -> None:
    GetOrCreateTagByName(tag_repository).execute("urgent")
    GetOrCreateTagByName(tag_repository).execute("URGENT")

    assert tag_repository.count() == 1


@pytest.mark.revised
def test_getting_or_creating_tag_uses_normalized_comparison(
    tag_repository: InMemoryTagRepository,
) -> None:
    existing_tag = GetOrCreateTagByName(tag_repository).execute("#Deep Work")

    tag = GetOrCreateTagByName(tag_repository).execute("deep-work")

    assert tag.id == existing_tag.id
    assert tag.name == "deep-work"


@pytest.mark.revised
def test_attaching_existing_tag_to_task_succeeds(
    tag_repository: InMemoryTagRepository,
    task_repository: InMemoryTaskRepository,
    task_tag_repository: InMemoryTaskTagRepository,
    task: Task,
) -> None:
    tag = create_tag(tag_repository, name="urgent")

    AttachTagToTask(task_repository, tag_repository, task_tag_repository).execute(
        task.id,
        "urgent",
    )

    assert task_tag_repository.list_tag_ids_for_task(task.id) == {tag.id}


@pytest.mark.revised
def test_attaching_missing_tag_to_task_creates_tag(
    tag_repository: InMemoryTagRepository,
    task_repository: InMemoryTaskRepository,
    task_tag_repository: InMemoryTaskTagRepository,
    task: Task,
) -> None:
    AttachTagToTask(task_repository, tag_repository, task_tag_repository).execute(
        task.id,
        "urgent",
    )

    assert tag_repository.get_by_name("urgent") is not None


@pytest.mark.revised
def test_attaching_same_tag_twice_to_same_task_does_not_duplicate_relationship(
    tag_repository: InMemoryTagRepository,
    task_repository: InMemoryTaskRepository,
    task_tag_repository: InMemoryTaskTagRepository,
    task: Task,
) -> None:
    use_case = AttachTagToTask(task_repository, tag_repository, task_tag_repository)

    use_case.execute(task.id, "urgent")
    use_case.execute(task.id, "#URGENT")

    assert task_tag_repository.count_for_task(task.id) == 1


@pytest.mark.revised
def test_attaching_tag_updates_task_updated_at(
    tag_repository: InMemoryTagRepository,
    task_repository: InMemoryTaskRepository,
    task_tag_repository: InMemoryTaskTagRepository,
    task: Task,
) -> None:
    updated_task = AttachTagToTask(
        task_repository,
        tag_repository,
        task_tag_repository,
    ).execute(task.id, "urgent")

    assert updated_task.updated_at != task.updated_at


@pytest.mark.revised
def test_attaching_already_attached_tag_does_not_unnecessarily_change_task_updated_at(
    tag_repository: InMemoryTagRepository,
    task_repository: InMemoryTaskRepository,
    task_tag_repository: InMemoryTaskTagRepository,
    task: Task,
) -> None:
    use_case = AttachTagToTask(task_repository, tag_repository, task_tag_repository)
    attached_task = use_case.execute(task.id, "urgent")

    unchanged_task = use_case.execute(task.id, "#URGENT")

    assert unchanged_task.updated_at == attached_task.updated_at


@pytest.mark.revised
def test_attaching_multiple_tags_to_task_succeeds(
    tag_repository: InMemoryTagRepository,
    task_repository: InMemoryTaskRepository,
    task_tag_repository: InMemoryTaskTagRepository,
    task: Task,
) -> None:
    AttachTagsToTask(task_repository, tag_repository, task_tag_repository).execute(
        task.id,
        ["urgent", "deep-work"],
    )

    assert list_task_tag_names(task, tag_repository, task_tag_repository) == [
        "deep-work",
        "urgent",
    ]


@pytest.mark.revised
def test_attaching_multiple_tags_creates_missing_tags(
    tag_repository: InMemoryTagRepository,
    task_repository: InMemoryTaskRepository,
    task_tag_repository: InMemoryTaskTagRepository,
    task: Task,
) -> None:
    AttachTagsToTask(task_repository, tag_repository, task_tag_repository).execute(
        task.id,
        ["urgent", "deep-work"],
    )

    assert tag_repository.count() == 2


@pytest.mark.revised
def test_attaching_multiple_tags_reuses_existing_tags(
    tag_repository: InMemoryTagRepository,
    task_repository: InMemoryTaskRepository,
    task_tag_repository: InMemoryTaskTagRepository,
    task: Task,
) -> None:
    existing_tag = create_tag(tag_repository, name="urgent")

    AttachTagsToTask(task_repository, tag_repository, task_tag_repository).execute(
        task.id,
        ["urgent", "deep-work"],
    )

    assert tag_repository.get_by_name("urgent") == existing_tag
    assert tag_repository.count() == 2


@pytest.mark.revised
def test_attaching_multiple_tags_ignores_duplicated_input_values(
    tag_repository: InMemoryTagRepository,
    task_repository: InMemoryTaskRepository,
    task_tag_repository: InMemoryTaskTagRepository,
    task: Task,
) -> None:
    AttachTagsToTask(task_repository, tag_repository, task_tag_repository).execute(
        task.id,
        ["urgent", "#URGENT", " urgent "],
    )

    assert tag_repository.count() == 1


@pytest.mark.revised
def test_attaching_multiple_tags_does_not_create_duplicated_relationships(
    tag_repository: InMemoryTagRepository,
    task_repository: InMemoryTaskRepository,
    task_tag_repository: InMemoryTaskTagRepository,
    task: Task,
) -> None:
    AttachTagsToTask(task_repository, tag_repository, task_tag_repository).execute(
        task.id,
        ["urgent", "#URGENT", "deep work", "deep-work"],
    )

    assert task_tag_repository.count_for_task(task.id) == 2


@pytest.mark.revised
def test_attaching_multiple_tags_normalizes_all_tag_names(
    tag_repository: InMemoryTagRepository,
    task_repository: InMemoryTaskRepository,
    task_tag_repository: InMemoryTaskTagRepository,
    task: Task,
) -> None:
    AttachTagsToTask(task_repository, tag_repository, task_tag_repository).execute(
        task.id,
        ["#URGENT", "Deep Work"],
    )

    assert list_task_tag_names(task, tag_repository, task_tag_repository) == [
        "deep-work",
        "urgent",
    ]


@pytest.mark.revised
def test_removing_attached_tag_from_task_succeeds(
    tag_repository: InMemoryTagRepository,
    task_repository: InMemoryTaskRepository,
    task_tag_repository: InMemoryTaskTagRepository,
    task: Task,
) -> None:
    AttachTagToTask(task_repository, tag_repository, task_tag_repository).execute(
        task.id,
        "urgent",
    )

    RemoveTagFromTask(task_repository, tag_repository, task_tag_repository).execute(
        task.id,
        "urgent",
    )

    assert task_tag_repository.count_for_task(task.id) == 0


@pytest.mark.revised
def test_removing_tag_does_not_delete_tag_itself(
    tag_repository: InMemoryTagRepository,
    task_repository: InMemoryTaskRepository,
    task_tag_repository: InMemoryTaskTagRepository,
    task: Task,
) -> None:
    AttachTagToTask(task_repository, tag_repository, task_tag_repository).execute(
        task.id,
        "urgent",
    )

    RemoveTagFromTask(task_repository, tag_repository, task_tag_repository).execute(
        task.id,
        "urgent",
    )

    assert tag_repository.get_by_name("urgent") is not None


@pytest.mark.revised
def test_removing_missing_tag_from_task_does_not_crash(
    tag_repository: InMemoryTagRepository,
    task_repository: InMemoryTaskRepository,
    task_tag_repository: InMemoryTaskTagRepository,
    task: Task,
) -> None:
    unchanged_task = RemoveTagFromTask(
        task_repository,
        tag_repository,
        task_tag_repository,
    ).execute(task.id, "missing")

    assert unchanged_task == task


@pytest.mark.revised
def test_removing_tag_that_is_not_attached_to_task_does_not_crash(
    tag_repository: InMemoryTagRepository,
    task_repository: InMemoryTaskRepository,
    task_tag_repository: InMemoryTaskTagRepository,
    task: Task,
) -> None:
    create_tag(tag_repository, name="urgent")

    unchanged_task = RemoveTagFromTask(
        task_repository,
        tag_repository,
        task_tag_repository,
    ).execute(task.id, "urgent")

    assert unchanged_task == task


@pytest.mark.revised
def test_removing_attached_tag_updates_task_updated_at(
    tag_repository: InMemoryTagRepository,
    task_repository: InMemoryTaskRepository,
    task_tag_repository: InMemoryTaskTagRepository,
    task: Task,
) -> None:
    attached_task = AttachTagToTask(
        task_repository,
        tag_repository,
        task_tag_repository,
    ).execute(task.id, "urgent")

    updated_task = RemoveTagFromTask(
        task_repository,
        tag_repository,
        task_tag_repository,
    ).execute(task.id, "urgent")

    assert updated_task.updated_at != attached_task.updated_at


@pytest.mark.revised
def test_removing_non_attached_tag_does_not_unnecessarily_change_task_updated_at(
    tag_repository: InMemoryTagRepository,
    task_repository: InMemoryTaskRepository,
    task_tag_repository: InMemoryTaskTagRepository,
    task: Task,
) -> None:
    create_tag(tag_repository, name="urgent")

    unchanged_task = RemoveTagFromTask(
        task_repository,
        tag_repository,
        task_tag_repository,
    ).execute(task.id, "urgent")

    assert unchanged_task.updated_at == task.updated_at


@pytest.mark.revised
def test_replacing_task_tags_removes_tags_not_present_in_new_list(
    tag_repository: InMemoryTagRepository,
    task_repository: InMemoryTaskRepository,
    task_tag_repository: InMemoryTaskTagRepository,
    task: Task,
) -> None:
    AttachTagsToTask(task_repository, tag_repository, task_tag_repository).execute(
        task.id,
        ["urgent", "review"],
    )

    ReplaceTaskTags(task_repository, tag_repository, task_tag_repository).execute(
        task.id,
        ["review"],
    )

    assert list_task_tag_names(task, tag_repository, task_tag_repository) == ["review"]


@pytest.mark.revised
def test_replacing_task_tags_keeps_tags_already_present_in_new_list(
    tag_repository: InMemoryTagRepository,
    task_repository: InMemoryTaskRepository,
    task_tag_repository: InMemoryTaskTagRepository,
    task: Task,
) -> None:
    AttachTagsToTask(task_repository, tag_repository, task_tag_repository).execute(
        task.id,
        ["urgent", "review"],
    )
    review_tag = tag_repository.get_by_name("review")

    ReplaceTaskTags(task_repository, tag_repository, task_tag_repository).execute(
        task.id,
        ["review", "deep-work"],
    )

    assert tag_repository.get_by_name("review") == review_tag
    assert list_task_tag_names(task, tag_repository, task_tag_repository) == [
        "deep-work",
        "review",
    ]


@pytest.mark.revised
def test_replacing_task_tags_creates_missing_tags(
    tag_repository: InMemoryTagRepository,
    task_repository: InMemoryTaskRepository,
    task_tag_repository: InMemoryTaskTagRepository,
    task: Task,
) -> None:
    ReplaceTaskTags(task_repository, tag_repository, task_tag_repository).execute(
        task.id,
        ["urgent", "review"],
    )

    assert tag_repository.count() == 2


@pytest.mark.revised
def test_replacing_task_tags_reuses_existing_tags(
    tag_repository: InMemoryTagRepository,
    task_repository: InMemoryTaskRepository,
    task_tag_repository: InMemoryTaskTagRepository,
    task: Task,
) -> None:
    existing_tag = create_tag(tag_repository, name="urgent")

    ReplaceTaskTags(task_repository, tag_repository, task_tag_repository).execute(
        task.id,
        ["urgent", "review"],
    )

    assert tag_repository.get_by_name("urgent") == existing_tag
    assert tag_repository.count() == 2


@pytest.mark.revised
def test_replacing_task_tags_ignores_duplicated_input_values(
    tag_repository: InMemoryTagRepository,
    task_repository: InMemoryTaskRepository,
    task_tag_repository: InMemoryTaskTagRepository,
    task: Task,
) -> None:
    ReplaceTaskTags(task_repository, tag_repository, task_tag_repository).execute(
        task.id,
        ["urgent", "#URGENT", "review"],
    )

    assert task_tag_repository.count_for_task(task.id) == 2


@pytest.mark.revised
def test_replacing_task_tags_normalizes_all_tag_names(
    tag_repository: InMemoryTagRepository,
    task_repository: InMemoryTaskRepository,
    task_tag_repository: InMemoryTaskTagRepository,
    task: Task,
) -> None:
    ReplaceTaskTags(task_repository, tag_repository, task_tag_repository).execute(
        task.id,
        ["#URGENT", "Deep Work"],
    )

    assert list_task_tag_names(task, tag_repository, task_tag_repository) == [
        "deep-work",
        "urgent",
    ]


@pytest.mark.revised
def test_replacing_task_tags_updates_task_updated_at_when_final_tag_set_changes(
    tag_repository: InMemoryTagRepository,
    task_repository: InMemoryTaskRepository,
    task_tag_repository: InMemoryTaskTagRepository,
    task: Task,
) -> None:
    updated_task = ReplaceTaskTags(
        task_repository,
        tag_repository,
        task_tag_repository,
    ).execute(task.id, ["urgent"])

    assert updated_task.updated_at != task.updated_at


@pytest.mark.revised
def test_replacing_task_tags_does_not_unnecessarily_update_when_set_is_unchanged(
    tag_repository: InMemoryTagRepository,
    task_repository: InMemoryTaskRepository,
    task_tag_repository: InMemoryTaskTagRepository,
    task: Task,
) -> None:
    updated_task = ReplaceTaskTags(
        task_repository,
        tag_repository,
        task_tag_repository,
    ).execute(task.id, ["urgent", "deep-work"])

    unchanged_task = ReplaceTaskTags(
        task_repository,
        tag_repository,
        task_tag_repository,
    ).execute(task.id, ["#URGENT", "Deep Work"])

    assert unchanged_task.updated_at == updated_task.updated_at


@pytest.mark.revised
def test_listing_tags_for_task_returns_only_attached_tags(
    tag_repository: InMemoryTagRepository,
    task_repository: InMemoryTaskRepository,
    task_tag_repository: InMemoryTaskTagRepository,
    task: Task,
) -> None:
    create_tag(tag_repository, name="unattached")
    AttachTagsToTask(task_repository, tag_repository, task_tag_repository).execute(
        task.id,
        ["urgent", "review"],
    )

    assert list_task_tag_names(task, tag_repository, task_tag_repository) == [
        "review",
        "urgent",
    ]


@pytest.mark.revised
def test_listing_tags_for_task_returns_normalized_tag_names(
    tag_repository: InMemoryTagRepository,
    task_repository: InMemoryTaskRepository,
    task_tag_repository: InMemoryTaskTagRepository,
    task: Task,
) -> None:
    AttachTagsToTask(task_repository, tag_repository, task_tag_repository).execute(
        task.id,
        ["#URGENT", "Deep Work"],
    )

    assert list_task_tag_names(task, tag_repository, task_tag_repository) == [
        "deep-work",
        "urgent",
    ]


@pytest.mark.revised
def test_listing_tags_for_task_returns_tags_alphabetically(
    tag_repository: InMemoryTagRepository,
    task_repository: InMemoryTaskRepository,
    task_tag_repository: InMemoryTaskTagRepository,
    task: Task,
) -> None:
    AttachTagsToTask(task_repository, tag_repository, task_tag_repository).execute(
        task.id,
        ["urgent", "coding", "review"],
    )

    assert list_task_tag_names(task, tag_repository, task_tag_repository) == [
        "coding",
        "review",
        "urgent",
    ]


@pytest.mark.revised
def test_listing_tags_for_task_with_no_tags_returns_empty_list(
    tag_repository: InMemoryTagRepository,
    task_tag_repository: InMemoryTaskTagRepository,
    task: Task,
) -> None:
    tags = ListTaskTags(tag_repository, task_tag_repository).execute(task.id)

    assert tags == []
