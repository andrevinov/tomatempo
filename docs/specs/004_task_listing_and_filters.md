# 004 - Task Listing and Filters

## Purpose

Define the core behavior for listing and filtering tasks in Tomatempo.

Task listing is the foundation for future screens, batch editing, focus flows, reports, and CSV export. The application must be able to retrieve tasks by status, project, tags, priority, due date, and search text without depending on a database or web interface.

This spec builds on the core behavior already defined in:

- `001_task_project_core.md`
- `002_tagging_core.md`
- `003_csv_import.md`

The goal is to create a predictable application-level listing workflow that can later be backed by SQLModel repositories, but can already be tested with fake or in-memory repositories.

---

## Concepts

### Task Listing

A task listing is a collection of tasks returned according to filter and sorting options.

The listing use case should not mutate tasks, projects, or tags.

### Task List Item

A task list item represents one task enriched with the project and tags needed to display or process it.

A task list item must include:

- `task`
- `project`
- `tags`

Tags should be returned using normalized tag names.

### Task Filter

A task filter describes which tasks should be included in the listing.

Filters are optional and composable. When multiple filters are provided, a task must match all of them.

### Task Sort

A task sort defines the order of returned tasks.

Sorting must be deterministic so that repeated listings return tasks in a stable order.

---

## Listing Scope

By default, task listing must exclude archived tasks.

Archived tasks should only be returned when explicitly requested.

This prevents completed or active workflows from being mixed with archived history by default.

---

## Supported Filters

### Status filter

The listing must support filtering by one or more task statuses.

Allowed statuses:

- `todo`
- `doing`
- `done`
- `archived`

Expected behavior:

- accepts status values using the same values defined in `001_task_project_core.md`
- returns only tasks whose status is included in the filter
- rejects invalid status values

### Project filter

The listing must support filtering by project.

Expected behavior:

- accepts a project id
- returns only tasks in that project
- returns an empty list if the project exists but has no matching tasks
- returns an empty list if the project does not exist

Project name filtering is out of scope for this spec.

### Tag filter

The listing must support filtering by tags.

Expected behavior:

- accepts one or more tag names
- normalizes tag names using `002_tagging_core.md`
- returns only tasks that have all requested tags
- returns an empty list if any requested tag does not exist
- ignores duplicate tag names in the filter input

For this spec, tag filtering uses **AND** semantics.

Example:

Filtering by:

```text
urgent,review
```

returns tasks that have both `urgent` and `review`.

### Priority filter

The listing must support filtering by one or more priorities.

Allowed priorities:

- `none`
- `low`
- `medium`
- `high`

Expected behavior:

- accepts priority values using the same values defined in `001_task_project_core.md`
- returns only tasks whose priority is included in the filter
- rejects invalid priority values

### Due date filter

The listing must support filtering by due date.

Expected behavior:

- `due_on` returns tasks due exactly on that date
- `due_before` returns tasks due before that date
- `due_after` returns tasks due after that date
- tasks without a due date are excluded when any due date filter is used
- due date filters compare dates only, not times

### Text search filter

The listing must support simple text search.

For this spec, text search means case-insensitive substring matching.

It is not exact matching, fuzzy search, stemming, ranking, operators, or full-text search.

Expected behavior:

- searches task title
- searches task description
- matches partial text
- compares case-insensitively
- ignores leading and trailing spaces in the search query
- returns all matching tasks when the query is not blank
- ignores the search filter when the query is missing or blank

---

## Sorting

### Default sort

By default, tasks must be sorted by:

1. `sort_order`, with tasks that have a sort order first
2. `created_at`
3. `title`
4. `id`

This keeps manual ordering possible while preserving deterministic output.

### Supported sort keys

The listing must support the following sort keys:

- `created_at`
- `updated_at`
- `due_date`
- `priority`
- `title`
- `sort_order`

### Sort direction

The listing must support:

- `asc`
- `desc`

Expected behavior:

- defaults to ascending order
- rejects invalid sort keys
- rejects invalid sort directions
- always uses `id` as a final tie-breaker

### Due date sorting

When sorting by due date:

- tasks with due dates come before tasks without due dates in ascending order
- tasks without due dates come after tasks with due dates in ascending order
- descending order reverses the due-date portion while still keeping deterministic output

---

## Required Use Cases

### List tasks

Given optional filters and sorting options, the system must return matching task list items.

Expected behavior:

- reads tasks from a repository
- applies filters in memory at the application level for this spec
- excludes archived tasks by default
- includes archived tasks only when requested
- enriches each task with its project
- enriches each task with attached tags
- returns tags in alphabetical order
- returns tasks in deterministic order

### Build task list item

Given a task, the system must build a task list item.

Expected behavior:

- includes the task
- includes the task project
- includes only tags attached to that task
- returns tags alphabetically

### Normalize task list filters

Given raw filter input, the system must normalize it before listing.

Expected behavior:

- normalizes statuses
- normalizes priorities
- normalizes tag names
- trims search query
- rejects invalid filter values
- ignores blank optional filter values

---

## Task List Result

A task listing must return a task list result.

The result must include:

- `items`
- `total_count`

### Task list item fields

Each task list item must include:

- `task`
- `project`
- `tags`

---

## Application-Level Test Scenarios

The agent should create application-level tests for the following behaviors.

These tests should use fake or in-memory repositories.

Do not use SQLModel, FastAPI, Jinja2, templates, HTTP, or a real database in these tests.

### Basic listing tests

- listing tasks returns all non-archived tasks by default
- listing tasks excludes archived tasks by default
- listing tasks can include archived tasks when requested
- listing tasks returns task list items
- task list items include the task
- task list items include the task project
- task list items include attached tags
- task list item tags are sorted alphabetically
- listing tasks reports total count
- listing tasks with no tasks returns an empty list

### Status filter tests

- filtering by one status returns only tasks with that status
- filtering by multiple statuses returns tasks matching any provided status
- filtering by archived status returns archived tasks
- filtering by invalid status fails

### Project filter tests

- filtering by project returns only tasks from that project
- filtering by project with no matching tasks returns an empty list
- filtering by missing project returns an empty list

### Tag filter tests

- filtering by one tag returns tasks with that tag
- filtering by multiple tags returns only tasks with all requested tags
- filtering by tag normalizes tag names
- filtering by duplicated tag names behaves like filtering once
- filtering by missing tag returns an empty list
- filtering by tag does not return tasks that have only some requested tags

### Priority filter tests

- filtering by one priority returns only tasks with that priority
- filtering by multiple priorities returns tasks matching any provided priority
- filtering by invalid priority fails

### Due date filter tests

- filtering by `due_on` returns tasks due on that date
- filtering by `due_before` returns tasks due before that date
- filtering by `due_after` returns tasks due after that date
- filtering by due date excludes tasks without due dates
- combining due date filters returns tasks matching all due date constraints

### Text search tests

- searching by title returns matching tasks
- searching by description returns matching tasks
- searching is case-insensitive
- searching trims the query
- blank search query is ignored
- searching with no matches returns an empty list

### Combined filter tests

- combining project and status filters returns tasks matching both
- combining tag and priority filters returns tasks matching both
- combining search and due date filters returns tasks matching both
- filters are applied with AND semantics across filter types

### Sorting tests

- default sorting uses sort order before created date
- default sorting places tasks without sort order after tasks with sort order
- sorting by title orders tasks alphabetically
- sorting by created date orders tasks by creation date
- sorting by updated date orders tasks by update date
- sorting by due date places dated tasks before undated tasks in ascending order
- sorting by priority orders tasks by priority rank
- descending sort reverses the selected sort order
- sorting uses task id as a final tie-breaker
- invalid sort key fails
- invalid sort direction fails

---

## Out of Scope

The following features must not be implemented in this spec:

- pagination
- saved filters
- custom views
- batch editing
- Pomodoro sessions
- reports
- CSV export
- frontend screens
- FastAPI routes
- SQLModel persistence
- Alembic migrations
- full-text search engine
- fuzzy search
- tag OR filters
- project name filters

These features will be handled in later specs.

---

## Expected Outcome

After this spec is implemented, the system should have a tested application core capable of:

- listing non-archived tasks by default
- including archived tasks when requested
- filtering tasks by status, project, tags, priority, due date, and text search
- combining filters predictably
- enriching task list rows with project and tags
- sorting task lists deterministically

This foundation must remain independent from the database and web interface.
