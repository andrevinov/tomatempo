# 001 - Task and Project Core

## Purpose

Define the core behavior for projects and tasks in Tomatempo.

This spec establishes the minimum domain model required before implementing CSV import, tagging, batch editing, Pomodoro sessions, and reports.

The goal is not to implement a full productivity system yet, but to create a solid foundation for managing tasks grouped by projects.

---

## Concepts

### Project

A project is a container for tasks.

A project represents an area of work, study, responsibility, or personal organization.

Examples:

- `Inbox`
- `Work`
- `English Classes`
- `Verité`
- `Tomatempo`
- `Personal`

### Task

A task represents something the user wants to do, track, postpone, complete, or associate with focus sessions.

A task always belongs to one project.

---

## Project Rules

### Project fields

A project must have:

- `id`
- `name`
- `created_at`
- `updated_at`

A project may have:

- `description`
- `is_archived`

### Project name rules

- A project name is required.
- A project name must not be empty or blank.
- Project names must be unique.
- Project name uniqueness is case-insensitive.
- Leading and trailing spaces must be ignored when validating uniqueness.
- The stored project name should be normalized by trimming leading and trailing spaces.

Examples:

- `Tomatempo`
- ` Tomatempo `
- `tomatempo`

These should be treated as the same project name for uniqueness purposes.

### Default project

The system must support a default project named `Inbox`.

When a task is created without an explicit project, it should be assigned to `Inbox`.

If `Inbox` does not exist yet, it must be created automatically when needed.

---

## Task Rules

### Task fields

A task must have:

- `id`
- `project_id`
- `title`
- `status`
- `created_at`
- `updated_at`

A task may have:

- `description`
- `priority`
- `due_date`
- `completed_at`
- `archived_at`
- `sort_order`

### Task title rules

- A task title is required.
- A task title must not be empty or blank.
- The stored task title should be normalized by trimming leading and trailing spaces.

### Task status

A task must have one of the following statuses:

- `todo`
- `doing`
- `done`
- `archived`

Default status:

- `todo`

Status behavior:

- A newly created task starts as `todo`.
- A task marked as completed must have status `done`.
- A completed task must have `completed_at`.
- A task moved out of `done` must clear `completed_at`.
- An archived task must have status `archived`.
- An archived task must have `archived_at`.

### Task priority

A task may have a priority.

Allowed priorities:

- `none`
- `low`
- `medium`
- `high`

Default priority:

- `none`

### Task due date

A task may have a due date.

The due date represents the day the task is expected to be done.

The due date does not imply a specific time of day.

---

## Task Uniqueness

The system should avoid accidental duplicate tasks inside the same project.

For this core spec, task uniqueness is defined by:

- same normalized task title
- same project

Task title comparison must be case-insensitive and must ignore leading/trailing spaces.

Examples inside the same project:

- `Prepare class`
- ` prepare class `
- `PREPARE CLASS`

These should be treated as the same task for duplicate detection.

The same task title may exist in different projects.

---

## Required Use Cases

### Create project

Given a valid project name, the system must create a project.

Expected behavior:

- trims the project name
- rejects empty names
- rejects duplicated names using case-insensitive comparison
- stores creation and update timestamps

### Get or create project by name

Given a project name, the system must return the existing project if it already exists.

If it does not exist, the system must create it.

Expected behavior:

- trims the project name
- compares names case-insensitively
- does not create duplicates

### Create task

Given a valid task title and a project, the system must create a task.

Expected behavior:

- trims the task title
- rejects empty titles
- assigns status `todo` by default
- assigns priority `none` by default
- stores creation and update timestamps
- assigns the task to the given project

### Create task without project

Given a valid task title and no explicit project, the system must create the task inside the default `Inbox` project.

Expected behavior:

- creates `Inbox` if it does not exist
- reuses `Inbox` if it already exists
- does not create duplicate `Inbox` projects

### Complete task

Given an existing task, the system must mark it as completed.

Expected behavior:

- sets status to `done`
- sets `completed_at`
- updates `updated_at`

### Reopen task

Given a completed task, the system must reopen it.

Expected behavior:

- sets status to `todo`
- clears `completed_at`
- updates `updated_at`

### Archive task

Given an existing task, the system must archive it.

Expected behavior:

- sets status to `archived`
- sets `archived_at`
- updates `updated_at`

### Update task basic fields

Given an existing task, the system must allow updating:

- title
- description
- project
- priority
- due date

Expected behavior:

- validates title if title is changed
- validates priority if priority is changed
- updates `updated_at`
- preserves `created_at`

---

## Application-Level Test Scenarios

The agent should create application-level tests for the following behaviors.

These tests should use fake or in-memory repositories.

Do not use SQLModel, FastAPI, or a real database in these tests.

### Project tests

- creating a project with a valid name succeeds
- creating a project trims leading and trailing spaces
- creating a project with an empty name fails
- creating a project with a blank name fails
- creating a duplicated project name fails
- project name uniqueness is case-insensitive
- getting or creating an existing project does not create a duplicate
- getting or creating a missing project creates it

### Default project tests

- creating a task without a project creates `Inbox` automatically
- creating multiple tasks without a project reuses the same `Inbox`
- `Inbox` uniqueness is case-insensitive

### Task creation tests

- creating a task with valid data succeeds
- creating a task trims leading and trailing spaces from the title
- creating a task with an empty title fails
- creating a task with a blank title fails
- a new task starts with status `todo`
- a new task starts with priority `none`
- a new task belongs to the selected project

### Task duplicate tests

- creating the same task twice in the same project is rejected
- task duplicate detection is case-insensitive
- task duplicate detection ignores leading and trailing spaces
- the same task title can exist in different projects

### Task status tests

- completing a task sets status to `done`
- completing a task sets `completed_at`
- reopening a completed task sets status to `todo`
- reopening a completed task clears `completed_at`
- archiving a task sets status to `archived`
- archiving a task sets `archived_at`

### Task update tests

- updating a task title succeeds with a valid title
- updating a task title trims leading and trailing spaces
- updating a task title to an empty value fails
- updating a task priority succeeds with an allowed priority
- updating a task due date succeeds
- updating a task preserves `created_at`
- updating a task changes `updated_at`

---

## Out of Scope

The following features must not be implemented in this spec:

- tags
- CSV import
- CSV export
- batch editing
- Pomodoro sessions
- reports
- recurring tasks
- reminders
- notifications
- user accounts
- authentication
- permissions
- frontend screens
- FastAPI routes
- SQLModel persistence
- Alembic migrations

These features will be handled in later specs.

---

## Expected Outcome

After this spec is implemented, the system should have a tested application core capable of:

- creating projects
- avoiding duplicate projects
- creating tasks
- assigning tasks to projects
- using `Inbox` as a default project
- avoiding duplicate tasks inside the same project
- completing, reopening, and archiving tasks
- updating basic task fields

This foundation must remain independent from the database and web interface.