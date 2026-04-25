# 002 - Tagging Core

## Purpose

Define the core behavior for tags in Tomatempo.

Tags are used to classify, filter, group, and batch-edit tasks across projects.

This spec establishes tagging as a first-class concept before implementing CSV import, task filters, batch editing, Pomodoro reports, and statistics.

The goal is to create a simple and reliable tagging model that can support future automation without depending on the database or web interface.

---

## Concepts

### Tag

A tag represents a label that can be attached to one or more tasks.

Tags are useful for grouping tasks across different projects.

Examples:

- `urgent`
- `deep-work`
- `english`
- `coding`
- `school`
- `verite`
- `tomatempo`
- `review`

### Task Tagging

A task may have zero, one, or many tags.

The same tag may be attached to many tasks.

Tags are independent from projects.

---

## Tag Rules

### Tag fields

A tag must have:

- `id`
- `name`
- `created_at`
- `updated_at`

A tag may have:

- `description`
- `is_archived`

### Tag name rules

A tag name is required.

A tag name must not be empty or blank.

The stored tag name should be normalized by:

- trimming leading and trailing spaces
- removing a leading `#`, if provided
- converting internal spaces to hyphens
- converting the name to lowercase

Examples:

- `Urgent`
- ` urgent `
- `#urgent`
- `URGENT`

These should all be stored as:

```text
urgent
````

Examples:

* `Deep Work`
* `deep work`
* `#Deep Work`

These should all be stored as:

```text
deep-work
```

### Tag uniqueness

Tag names must be unique.

Tag uniqueness is case-insensitive.

Tag uniqueness must ignore:

* leading spaces
* trailing spaces
* a leading `#`
* differences between spaces and hyphens

Examples:

* `Deep Work`
* `deep-work`
* `#deep work`
* `DEEP-WORK`

These should be treated as the same tag.

---

## Task-Tag Rules

### Attaching tags to tasks

A tag can be attached to a task.

Expected behavior:

* if the tag already exists, reuse it
* if the tag does not exist, create it
* attach the tag to the task
* do not attach the same tag twice to the same task

### Removing tags from tasks

A tag can be removed from a task.

Expected behavior:

* removing an attached tag succeeds
* removing a tag that is not attached does not crash
* removing a tag from a task does not delete the tag itself

### Replacing task tags

The system should support replacing all tags from a task with a new set of tags.

Expected behavior:

* existing task tags not present in the new set are removed
* new tags are created if needed
* existing tags are reused
* duplicate tags in the input are ignored
* the final task tag list contains each tag only once

---

## Required Use Cases

### Create tag

Given a valid tag name, the system must create a tag.

Expected behavior:

* normalizes the tag name
* rejects empty names
* rejects blank names
* rejects duplicated names
* stores creation and update timestamps

### Get or create tag by name

Given a tag name, the system must return the existing tag if it already exists.

If it does not exist, the system must create it.

Expected behavior:

* normalizes the tag name
* compares names using normalized form
* does not create duplicates

### Attach tag to task

Given an existing task and a tag name, the system must attach the tag to the task.

Expected behavior:

* creates the tag if it does not exist
* reuses the tag if it already exists
* does not create duplicated task-tag relationships
* updates the task `updated_at`

### Attach multiple tags to task

Given an existing task and a list of tag names, the system must attach all valid tags to the task.

Expected behavior:

* normalizes all tag names
* creates missing tags
* reuses existing tags
* ignores duplicated tag names in the input
* does not create duplicated task-tag relationships
* updates the task `updated_at`

### Remove tag from task

Given an existing task and a tag name, the system must remove that tag from the task.

Expected behavior:

* removes the task-tag relationship if it exists
* does not delete the tag
* does not crash if the tag does not exist
* does not crash if the tag is not attached to the task
* updates the task `updated_at` only when a relationship is actually removed

### Replace task tags

Given an existing task and a list of tag names, the system must replace the task's current tags with the provided tags.

Expected behavior:

* normalizes all tag names
* creates missing tags
* reuses existing tags
* removes old task-tag relationships not present in the new list
* keeps existing task-tag relationships that are still present
* ignores duplicated tag names in the input
* updates the task `updated_at` if the final tag set changes

### List task tags

Given an existing task, the system must list its tags.

Expected behavior:

* returns only tags attached to the task
* returns tags using normalized names
* returns tags in alphabetical order

---

## Application-Level Test Scenarios

The agent should create application-level tests for the following behaviors.

These tests should use fake or in-memory repositories.

Do not use SQLModel, FastAPI, or a real database in these tests.

### Tag creation tests

* creating a tag with a valid name succeeds
* creating a tag trims leading and trailing spaces
* creating a tag removes a leading `#`
* creating a tag converts the name to lowercase
* creating a tag converts internal spaces to hyphens
* creating a tag with an empty name fails
* creating a tag with a blank name fails
* creating a duplicated tag fails
* tag uniqueness is case-insensitive
* tag uniqueness treats spaces and hyphens as equivalent
* tag uniqueness ignores a leading `#`

### Get or create tag tests

* getting or creating an existing tag returns the existing tag
* getting or creating a missing tag creates it
* getting or creating a tag does not create duplicates
* getting or creating a tag uses normalized comparison

### Attach tag tests

* attaching an existing tag to a task succeeds
* attaching a missing tag to a task creates the tag
* attaching the same tag twice to the same task does not duplicate the relationship
* attaching a tag updates the task `updated_at`
* attaching an already attached tag does not unnecessarily change the task `updated_at`

### Attach multiple tags tests

* attaching multiple tags to a task succeeds
* attaching multiple tags creates missing tags
* attaching multiple tags reuses existing tags
* attaching multiple tags ignores duplicated input values
* attaching multiple tags does not create duplicated task-tag relationships
* attaching multiple tags normalizes all tag names

### Remove tag tests

* removing an attached tag from a task succeeds
* removing a tag does not delete the tag itself
* removing a missing tag from a task does not crash
* removing a tag that is not attached to the task does not crash
* removing an attached tag updates the task `updated_at`
* removing a non-attached tag does not unnecessarily change the task `updated_at`

### Replace task tags tests

* replacing task tags removes tags not present in the new list
* replacing task tags keeps tags already present in the new list
* replacing task tags creates missing tags
* replacing task tags reuses existing tags
* replacing task tags ignores duplicated input values
* replacing task tags normalizes all tag names
* replacing task tags updates the task `updated_at` when the final tag set changes
* replacing task tags does not unnecessarily update the task when the final tag set is unchanged

### List task tags tests

* listing tags for a task returns only attached tags
* listing tags for a task returns normalized tag names
* listing tags for a task returns tags alphabetically
* listing tags for a task with no tags returns an empty list

---

## Out of Scope

The following features must not be implemented in this spec:

* CSV import
* CSV export
* batch editing
* Pomodoro sessions
* reports
* recurring tasks
* reminders
* notifications
* user accounts
* authentication
* permissions
* frontend screens
* FastAPI routes
* SQLModel persistence
* Alembic migrations

These features will be handled in later specs.

---

## Expected Outcome

After this spec is implemented, the system should have a tested application core capable of:

* creating tags
* normalizing tag names
* avoiding duplicate tags
* attaching tags to tasks
* attaching multiple tags to tasks
* removing tags from tasks
* replacing all tags from a task
* listing tags attached to a task

This foundation must remain independent from the database and web interface.
