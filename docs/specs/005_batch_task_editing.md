# 005 - Batch Task Editing

## Purpose

Define the core behavior for applying changes to multiple tasks at once in Tomatempo.

Batch task editing is one of the main productivity features of the application. It allows users to select many tasks and update shared fields, move tasks between projects, attach or remove tags, mark tasks as done, reopen tasks, or archive tasks in one operation.

This spec builds on the behavior already defined in:

- `001_task_project_core.md`
- `002_tagging_core.md`
- `003_csv_import.md`
- `004_task_listing_and_filters.md`

The goal is to create a predictable application-level workflow for batch operations that remains independent from the database, web interface, HTTP forms, and frontend screens.

---

## Concepts

### Batch Task Editing

Batch task editing applies one requested operation to multiple tasks.

Each task should be processed independently so one invalid or missing task does not prevent other valid tasks from being edited.

### Batch Selection

A batch selection describes which tasks should be edited.

For this spec, batch operations must support selecting tasks by explicit task ids.

Filter-based batch selection is out of scope for this spec. It may be added later by combining batch editing with task listing filters.

### Batch Operation

A batch operation describes the action to apply to all selected tasks.

Examples:

- update priority
- update due date
- move to another project
- attach tags
- remove tags
- replace tags
- complete tasks
- reopen tasks
- archive tasks

### Batch Result

A batch result summarizes what happened during a batch operation.

It should tell the caller:

- how many task ids were requested
- how many tasks were changed
- how many tasks were unchanged
- which tasks were changed
- which task ids failed

The batch operation should not crash the entire operation because one task id is missing or invalid.

---

## Selection Rules

### Explicit task ids

Batch editing must accept one or more task ids.

Expected behavior:

- preserves the first-seen order of task ids
- ignores duplicate task ids after the first occurrence
- rejects an empty task id selection
- reports missing task ids as item-level errors
- continues processing existing task ids when some ids are missing

### Archived tasks

Archived tasks must not be edited by default.

Expected behavior:

- skips archived tasks by default
- reports archived tasks as item-level errors by default
- allows archived tasks to be edited only when explicitly requested

This prevents accidental changes to archived history.

---

## Supported Batch Operations

### Update priority

The system must support updating the priority of selected tasks.

Allowed priorities:

- `none`
- `low`
- `medium`
- `high`

Expected behavior:

- accepts priority values using the same values defined in `001_task_project_core.md`
- updates the priority for each selected task
- rejects invalid priority values
- leaves a task unchanged when it already has the requested priority

### Update due date

The system must support updating the due date of selected tasks.

Expected behavior:

- accepts a date value
- stores the date on each selected task
- allows clearing the due date by passing `None`
- leaves a task unchanged when it already has the requested due date

The due date represents a day, not a time of day.

### Move to project

The system must support moving selected tasks to another project.

Expected behavior:

- accepts a target project id
- moves each selected task to the target project
- rejects the operation if the target project does not exist
- leaves a task unchanged when it already belongs to the target project
- preserves task title uniqueness inside the target project
- reports a task-level error when moving a task would create a duplicate title in the target project
- continues moving other valid tasks

Project creation by name is out of scope for this operation.

### Attach tags

The system must support attaching tags to selected tasks.

Expected behavior:

- accepts one or more tag names
- normalizes tag names using `002_tagging_core.md`
- creates missing tags
- reuses existing tags
- attaches each tag to each selected task
- ignores duplicate tag names in the operation input
- leaves a task unchanged when it already has all requested tags

### Remove tags

The system must support removing tags from selected tasks.

Expected behavior:

- accepts one or more tag names
- normalizes tag names using `002_tagging_core.md`
- removes existing tag relationships from each selected task
- ignores tag names that do not exist
- leaves a task unchanged when none of the requested tags are attached
- does not delete tag records

### Replace tags

The system must support replacing all tags on selected tasks.

Expected behavior:

- accepts zero or more tag names
- normalizes tag names using `002_tagging_core.md`
- creates missing tags
- reuses existing tags
- replaces the full tag set for each selected task
- clears all tags when the provided tag list is empty
- ignores duplicate tag names in the operation input
- leaves a task unchanged when its tag set is already equal to the requested tag set

### Complete tasks

The system must support marking selected tasks as done.

Expected behavior:

- sets status to `done`
- sets `completed_at`
- updates `updated_at`
- leaves already done tasks unchanged

### Reopen tasks

The system must support reopening selected tasks.

Expected behavior:

- sets status to `todo`
- clears `completed_at`
- updates `updated_at`
- leaves already todo tasks unchanged

### Archive tasks

The system must support archiving selected tasks.

Expected behavior:

- sets status to `archived`
- sets `archived_at`
- updates `updated_at`
- leaves already archived tasks unchanged when archived editing is explicitly allowed

---

## Change Detection

Batch editing must distinguish changed tasks from unchanged tasks.

Expected behavior:

- a task is changed only when persisted state is different after the operation
- unchanged tasks are counted separately
- unchanged tasks are not reported as errors
- changed tasks are returned in the result

### Updated timestamp

Any successful batch operation that changes a task or its task-tag relationships must update the task `updated_at`.

This applies to:

- priority changes
- due date changes
- project moves
- tag attachments
- tag removals
- tag replacements
- status changes

Expected behavior:

- changed tasks receive a new `updated_at`
- unchanged tasks preserve their previous `updated_at`
- task-tag relationship changes also update the task `updated_at`
- failed task edits do not update the task `updated_at`

---

## Error Behavior

Batch editing should be item-tolerant.

Expected behavior:

- valid tasks are edited
- missing task ids are reported as errors
- archived tasks are reported as errors unless archived editing is explicitly allowed
- duplicate-title conflicts during project moves are reported as errors
- invalid operation input rejects the operation before any task is changed
- item-level errors do not prevent later valid tasks from being edited

### Error codes

Suggested error codes:

- `empty_selection`
- `missing_task`
- `archived_task`
- `invalid_priority`
- `invalid_tag_name`
- `missing_project`
- `duplicate_task_title`
- `unsupported_operation`

---

## Required Use Cases

### Batch edit tasks

Given task ids and one batch operation, the system must apply the operation to each selected task.

Expected behavior:

- normalizes and validates operation input before editing tasks
- de-duplicates task ids while preserving first-seen order
- retrieves each task from the task repository
- skips or reports missing tasks
- skips or reports archived tasks unless explicitly allowed
- saves changed tasks
- returns a batch result

### Normalize batch task selection

Given raw task ids, the system must return a normalized selection.

Expected behavior:

- rejects empty selections
- removes duplicate ids
- preserves first-seen order

### Normalize batch operation

Given raw operation input, the system must validate and normalize it before editing tasks.

Expected behavior:

- validates operation type
- normalizes priority values
- validates target project existence for move operations
- normalizes tag names for tag operations
- rejects blank tag names
- rejects invalid operation values

---

## Batch Result

A batch result must include:

- `requested_count`
- `changed_count`
- `unchanged_count`
- `error_count`
- `changed_tasks`
- `errors`

### Batch error fields

Each batch error must include:

- `task_id`
- `code`
- `message`

For selection-level or operation-level errors that do not belong to a specific task, `task_id` may be `None`.

---

## Application-Level Test Scenarios

The agent should create application-level tests for the following behaviors.

These tests should use fake or in-memory repositories.

Do not use SQLModel, FastAPI, Jinja2, templates, HTTP, forms, or a real database in these tests.

### Selection tests

- batch editing rejects an empty task selection
- batch editing de-duplicates task ids
- batch editing preserves first-seen task id order
- batch editing reports missing task ids
- batch editing continues after missing task ids
- batch editing skips archived tasks by default
- batch editing can include archived tasks when explicitly allowed

### Priority update tests

- batch updating priority changes selected tasks
- batch updating priority reports changed count
- batch updating priority leaves tasks unchanged when priority already matches
- batch updating priority rejects invalid priority
- batch updating priority does not modify unselected tasks

### Due date update tests

- batch updating due date changes selected tasks
- batch updating due date can clear due dates
- batch updating due date leaves tasks unchanged when due date already matches
- batch updating due date does not modify unselected tasks

### Move project tests

- batch moving tasks moves selected tasks to the target project
- batch moving tasks rejects a missing target project
- batch moving tasks leaves tasks unchanged when already in the target project
- batch moving tasks reports duplicate title conflicts in the target project
- batch moving tasks continues after duplicate title conflicts
- batch moving tasks does not modify unselected tasks

### Attach tag tests

- batch attaching tags creates missing tags
- batch attaching tags reuses existing tags
- batch attaching tags attaches tags to each selected task
- batch attaching tags normalizes tag names
- batch attaching tags ignores duplicate tag names
- batch attaching tags leaves tasks unchanged when all tags are already attached
- batch attaching tags does not modify unselected tasks

### Remove tag tests

- batch removing tags removes matching task-tag relationships
- batch removing tags ignores missing tag names
- batch removing tags leaves tasks unchanged when no requested tags are attached
- batch removing tags does not delete tag records
- batch removing tags does not modify unselected tasks

### Replace tag tests

- batch replacing tags replaces each selected task tag set
- batch replacing tags creates missing tags
- batch replacing tags reuses existing tags
- batch replacing tags normalizes tag names
- batch replacing tags clears tags when given an empty tag list
- batch replacing tags leaves tasks unchanged when tag sets already match
- batch replacing tags does not modify unselected tasks

### Status operation tests

- batch completing tasks marks selected tasks as done
- batch completing tasks sets completed timestamp
- batch completing tasks leaves already done tasks unchanged
- batch reopening tasks marks selected tasks as todo
- batch reopening tasks clears completed timestamp
- batch reopening tasks leaves already todo tasks unchanged
- batch archiving tasks marks selected tasks as archived
- batch archiving tasks sets archived timestamp
- batch archiving tasks leaves already archived tasks unchanged when archived editing is allowed
- status operations do not modify unselected tasks

### Result tests

- batch result reports requested count
- batch result reports changed count
- batch result reports unchanged count
- batch result reports error count
- batch result includes changed tasks
- batch result includes item-level errors
- changed tasks are returned in selected task order

---

## Out of Scope

The following features must not be implemented in this spec:

- filter-based batch selection
- pagination
- undo history
- audit logs
- optimistic locking
- transactions spanning a real database session
- CSV import
- CSV export
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
- background jobs

These features will be handled in later specs.

---

## Expected Outcome

After this spec is implemented, the system should have a tested application core capable of:

- applying one operation to multiple selected tasks
- safely handling missing or archived tasks
- updating priorities, due dates, projects, tags, and statuses in batch
- reporting changed, unchanged, and failed task edits
- preserving deterministic task processing order

This foundation must remain independent from the database and web interface.
