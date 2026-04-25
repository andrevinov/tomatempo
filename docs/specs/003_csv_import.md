# 003 - CSV Import

## Purpose

Define the core behavior for importing tasks from CSV data in Tomatempo.

CSV import is one of the main automation features of the application. It allows users to create tasks, assign projects, define priorities and due dates, and attach tags using a portable plain-text format.

This spec builds on the project, task, and tagging core already defined in:

- `001_task_project_core.md`
- `002_tagging_core.md`

The goal is to create a reliable application-level import workflow that remains independent from the database, web interface, file uploads, and frontend screens.

---

## Concepts

### CSV Import

A CSV import receives tabular data and turns each valid row into a task.

Each row represents one task to create or reuse.

The import process may also create or reuse related projects and tags.

### CSV Row

A CSV row is a dictionary-like record parsed from CSV headers.

Each row may include task fields, project information, and tags.

### Import Result

An import result summarizes what happened during an import.

It should tell the caller:

- how many rows were processed
- how many tasks were created
- how many rows were skipped
- which rows failed validation
- which tasks were created

The import process should not crash the entire import because one row is invalid.

---

## CSV Format

### Delimiter

The CSV import must use semicolon (`;`) as the column delimiter.

This allows task titles and descriptions to contain commas without requiring quotes in common cases.

Example:

```csv
title;project;tags
Buy rice, beans, and coffee;Personal;errands,shopping
```

### Required columns

The CSV import must support the following required column:

- `title`

### Optional columns

The CSV import must support the following optional columns:

- `description`
- `project`
- `priority`
- `due_date`
- `tags`

### Header rules

- CSV headers are required.
- Header names must be matched case-insensitively.
- Leading and trailing spaces in header names must be ignored.
- Unknown columns must be ignored.

Examples of equivalent headers:

- `title`
- ` Title `
- `TITLE`

These should all be treated as:

```text
title
```

### Empty CSV rules

- An empty CSV input must fail.
- A CSV input with headers but no rows must succeed with zero created tasks.

---

## Field Rules

### Title

The `title` column is required.

Expected behavior:

- trims leading and trailing spaces
- rejects empty or blank titles
- follows the task title rules from `001_task_project_core.md`

### Description

The `description` column is optional.

Expected behavior:

- trims leading and trailing spaces
- stores `None` when missing or blank

### Project

The `project` column is optional.

Expected behavior:

- trims leading and trailing spaces
- uses the provided project when present
- creates the project if it does not exist
- reuses the project if it already exists
- uses the default `Inbox` project when missing or blank

Project normalization and uniqueness must follow `001_task_project_core.md`.

### Priority

The `priority` column is optional.

Allowed values:

- `none`
- `low`
- `medium`
- `high`

Expected behavior:

- trims leading and trailing spaces
- compares values case-insensitively
- defaults to `none` when missing or blank
- rejects unknown values

### Due date

The `due_date` column is optional.

Expected format:

```text
YYYY-MM-DD
```

Expected behavior:

- trims leading and trailing spaces
- stores `None` when missing or blank
- parses valid ISO dates
- rejects invalid dates
- rejects date-times such as `2026-05-01T10:00:00`

The due date represents a day, not a time of day.

### Tags

The `tags` column is optional.

Tags in one cell must be separated by commas.

Examples:

```text
urgent,deep-work
urgent, deep work, #review
```

Expected behavior:

- stores no tags when missing or blank
- trims each tag item
- ignores blank tag items
- normalizes tag names using `002_tagging_core.md`
- creates missing tags
- reuses existing tags
- ignores duplicated tag names in the same row
- attaches each tag only once to the created task

---

## Duplicate Task Behavior

Task uniqueness must follow `001_task_project_core.md`.

For CSV import:

- duplicate tasks inside the same project must be skipped
- skipped duplicate rows must not fail the entire import
- duplicate rows must be reported in the import result
- the same task title may be imported into different projects

Examples inside the same project:

- `Prepare class`
- ` prepare class `
- `PREPARE CLASS`

These should be treated as the same task.

---

## Import Error Behavior

The import process should be row-tolerant.

Expected behavior:

- valid rows are imported
- invalid rows are not imported
- invalid rows are reported with row number and reason
- duplicate rows are skipped and reported
- one invalid row must not prevent later valid rows from being imported

### Row numbers

Row numbers in import errors must refer to the CSV data row number, starting at `2` for the first row after the header.

Example:

```csv
title;project
Valid task;Work
;Work
Another task;Work
```

The blank title error should be reported as row `3`.

---

## Required Use Cases

### Import tasks from CSV text

Given a CSV text input, the system must import all valid rows.

Expected behavior:

- parses CSV headers
- normalizes supported header names
- ignores unknown columns
- creates tasks for valid rows
- creates or reuses projects
- creates or reuses tags
- attaches tags to created tasks
- applies priority and due date when provided
- returns an import result

### Import one CSV row

Given one parsed CSV row, the system must import that row as one task.

Expected behavior:

- validates required fields
- creates or reuses the row project
- creates the task
- attaches row tags
- returns the created task

### Parse tag cell

Given a tag cell string, the system must return normalized tag names.

Expected behavior:

- splits tags by comma
- trims each tag
- ignores blank items
- removes duplicates after normalization
- preserves first-seen order

---

## Import Result

An import result must include:

- `processed_rows`
- `created_count`
- `skipped_count`
- `errors`
- `created_tasks`

### Import error fields

Each import error must include:

- `row_number`
- `code`
- `message`

Suggested error codes:

- `empty_csv`
- `missing_required_header`
- `invalid_title`
- `invalid_priority`
- `invalid_due_date`
- `duplicate_task`

---

## Application-Level Test Scenarios

The agent should create application-level tests for the following behaviors.

These tests should use fake or in-memory repositories.

Do not use SQLModel, FastAPI, Jinja2, file uploads, or a real database in these tests.

### CSV parsing tests

- importing empty CSV text fails
- importing CSV text with headers and no rows succeeds with zero created tasks
- importing CSV uses semicolon as the column delimiter
- importing CSV allows commas inside task titles
- importing CSV with missing `title` header fails
- importing CSV ignores unknown columns
- importing CSV matches headers case-insensitively
- importing CSV trims header names

### Basic import tests

- importing one valid row creates one task
- importing multiple valid rows creates multiple tasks
- importing a row trims the task title
- importing a row stores description when provided
- importing a row stores `None` for blank description
- importing a row sets default priority to `none`
- importing a row sets provided priority
- importing a row parses due date
- importing a row stores `None` for blank due date

### Project import tests

- importing a row with project creates the project when missing
- importing a row with existing project reuses it
- importing a row without project uses `Inbox`
- importing a row with blank project uses `Inbox`
- importing rows with equivalent project names does not create duplicate projects

### Tag import tests

- importing a row with tags creates missing tags
- importing a row with tags reuses existing tags
- importing a row attaches tags to the created task
- importing a row normalizes tag names
- importing a row ignores duplicate tag names
- importing a row with blank tags creates no task-tag relationships
- parsing a tag cell splits tags by comma
- parsing a tag cell ignores blank tag items
- parsing a tag cell preserves first-seen order after normalization

### Duplicate import tests

- importing a duplicate task in the same project skips the duplicate row
- importing duplicate task titles in different projects creates both tasks
- importing duplicate rows reports duplicate task errors
- importing duplicate rows continues importing later valid rows

### Validation tests

- importing a row with blank title reports an invalid title error
- importing a row with invalid priority reports an invalid priority error
- importing a row with invalid due date reports an invalid due date error
- importing a row with date-time due date reports an invalid due date error
- importing invalid rows does not create tasks for those rows
- importing invalid rows still imports later valid rows
- import errors include row numbers based on CSV data rows

### Import result tests

- import result reports processed row count
- import result reports created task count
- import result reports skipped row count
- import result includes created tasks
- import result includes validation errors

---

## Out of Scope

The following features must not be implemented in this spec:

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
- file upload handling
- SQLModel persistence
- Alembic migrations
- background jobs

These features will be handled in later specs.

---

## Expected Outcome

After this spec is implemented, the system should have a tested application core capable of:

- importing tasks from CSV text
- creating and reusing projects during import
- creating and reusing tags during import
- attaching tags to imported tasks
- applying descriptions, priorities, and due dates
- skipping duplicate task rows
- collecting row-level import errors
- returning a useful import summary

This foundation must remain independent from the database and web interface.
