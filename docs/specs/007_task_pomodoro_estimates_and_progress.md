# 007 - Task Pomodoro Estimates and Progress

## Purpose

Define the core behavior for estimating Pomodoro effort on tasks and calculating task progress from recorded Pomodoro sessions.

Tomatempo should let users plan how many Pomodoros a task is expected to take, then compare that estimate with actual focus time. Actual work must come from session history, not from mutable counters stored directly on tasks.

This spec builds on the behavior already defined in:

- `001_task_project_core.md`
- `006_pomodoro_sessions.md`

The goal is to create a predictable application-level workflow for task estimates and progress summaries that remains independent from the database, web interface, reports screen, CSV export, and browser timer.

---

## Concepts

### Estimated Pomodoros

Estimated Pomodoros represent how many full Pomodoro intervals the user expects a task to require.

This is planning data and belongs directly to the task.

Expected field:

- `estimated_pomodoros`

### Actual Focus Time

Actual focus time is the amount of focus work recorded for a task through Pomodoro sessions.

Actual focus time must be derived from `PomodoroSession` records.

It should not be stored as a mutable counter on the task.

### Pomodoro Equivalent

A Pomodoro equivalent is a normalized way to express actual focus minutes as Pomodoro units.

For this spec:

- 1 Pomodoro equivalent = 25 actual focus minutes
- partial Pomodoro equivalents are allowed

Examples:

- 25 actual focus minutes = `1.0`
- 10 actual focus minutes = `0.4`
- 50 actual focus minutes = `2.0`

### Task Progress Summary

A task progress summary describes planning and actual focus work for one task.

It should include:

- task
- estimated Pomodoros
- estimated minutes
- actual focus minutes
- actual Pomodoro equivalents
- remaining estimated minutes
- whether the estimate has been exceeded

---

## Estimate Field Rules

Tasks must support an optional estimated Pomodoro count.

Expected behavior:

- a task may have no estimate
- a task estimate may be set to a positive integer
- a task estimate may be cleared
- zero is not a valid estimate
- negative values are not valid estimates
- estimates represent full Pomodoros, not minutes

When a task has no estimate, progress can still be calculated from sessions, but estimated fields should reflect the missing estimate.

---

## Actual Focus Time Rules

Actual focus time must be calculated from Pomodoro sessions.

Only sessions that match all of the following should count:

- session type is `focus`
- session is associated with the task
- session has `actual_duration_minutes`
- session status is `completed` or `interrupted`

Expected behavior:

- completed focus sessions count
- interrupted focus sessions count
- partial focus sessions count
- focus sessions without a task do not count toward any task
- break sessions do not count toward task progress
- running sessions do not count
- paused sessions do not count
- planned sessions do not count
- sessions for other tasks do not count

This means a 10-minute completed or interrupted focus session contributes 10 actual focus minutes to its task.

Running and paused sessions may already contain elapsed focus time, but they are still active sessions. Their elapsed focus time should not count toward committed task progress in this spec.

A later workflow or interface may show active elapsed focus time separately as in-progress focus time.

---

## Estimate Calculations

### Estimated minutes

Estimated minutes should be calculated as:

```text
estimated_pomodoros * 25
```

Expected behavior:

- returns `None` when the task has no estimate
- returns an integer number of minutes when the task has an estimate

### Actual Pomodoro equivalents

Actual Pomodoro equivalents should be calculated as:

```text
actual_focus_minutes / 25
```

Expected behavior:

- supports partial values
- returns `0` when no sessions count
- rounds only for presentation, not in the application calculation

### Remaining estimated minutes

Remaining estimated minutes should be calculated as:

```text
estimated_minutes - actual_focus_minutes
```

Expected behavior:

- returns `None` when the task has no estimate
- returns `0` when actual focus minutes are equal to estimated minutes
- returns `0` when actual focus minutes exceed estimated minutes
- never returns a negative value

### Estimate exceeded

Estimate exceeded should indicate whether actual focus minutes went beyond estimated minutes.

Expected behavior:

- returns `False` when the task has no estimate
- returns `False` when actual focus minutes are less than or equal to estimated minutes
- returns `True` when actual focus minutes are greater than estimated minutes

---

## Required Use Cases

### Update task Pomodoro estimate

Given a task id and an estimated Pomodoro count, the system must update the task estimate.

Expected behavior:

- retrieves the task
- rejects missing tasks
- accepts positive integer estimates
- accepts `None` to clear the estimate
- rejects zero estimates
- rejects negative estimates
- updates the task `updated_at` when the estimate changes
- leaves the task unchanged when the estimate already matches
- returns the task

### Get task Pomodoro progress

Given a task id, the system must return a progress summary for that task.

Expected behavior:

- retrieves the task
- rejects missing tasks
- reads Pomodoro sessions from a repository
- sums actual focus minutes for that task
- calculates estimated minutes
- calculates actual Pomodoro equivalents
- calculates remaining estimated minutes
- calculates whether the estimate has been exceeded
- returns a task progress summary

### List task Pomodoro progress

Given multiple task ids, the system must return progress summaries for those tasks.

Expected behavior:

- preserves the first-seen task id order
- ignores duplicate task ids after the first occurrence
- rejects empty task id selections
- rejects missing task ids
- returns one progress summary per selected task

This use case is intended for future task lists and dashboards.

---

## Task Progress Summary Fields

A task progress summary must include:

- `task`
- `estimated_pomodoros`
- `estimated_minutes`
- `actual_focus_minutes`
- `actual_pomodoro_equivalents`
- `remaining_estimated_minutes`
- `estimate_exceeded`

### Field rules

- `estimated_pomodoros` mirrors the task estimate
- `estimated_minutes` is `None` when the task has no estimate
- `actual_focus_minutes` is always an integer
- `actual_pomodoro_equivalents` may be fractional
- `remaining_estimated_minutes` is `None` when the task has no estimate
- `estimate_exceeded` is always a boolean

---

## Error Behavior

Pomodoro estimate and progress use cases should fail fast for invalid operation input.

Suggested error codes or exception categories:

- `missing_task`
- `invalid_estimate`
- `empty_selection`

The exact exception hierarchy can be decided during implementation, but tests should assert meaningful failure behavior.

---

## Application-Level Test Scenarios

The agent should create application-level tests for the following behaviors.

These tests should use fake or in-memory repositories.

Do not use SQLModel, FastAPI, Jinja2, templates, HTTP, browser timers, background workers, reports, CSV export, or a real database in these tests.

### Estimate update tests

- updating a task estimate stores the estimate on the task
- updating a task estimate updates task `updated_at`
- updating a task estimate returns the updated task
- updating a task estimate can clear the estimate
- updating a task estimate leaves the task unchanged when the estimate already matches
- updating a missing task fails
- updating a task estimate rejects zero
- updating a task estimate rejects negative values

### Actual focus minute tests

- completed focus sessions count toward actual focus minutes
- interrupted focus sessions count toward actual focus minutes
- partial focus sessions count toward actual focus minutes
- multiple sessions for the same task are summed
- sessions for other tasks do not count
- focus sessions without a task do not count
- short break sessions do not count
- long break sessions do not count
- running sessions do not count
- paused sessions do not count
- planned sessions do not count
- sessions without actual duration do not count

### Progress summary tests

- progress summary includes the task
- progress summary includes estimated Pomodoros
- progress summary calculates estimated minutes
- progress summary calculates actual focus minutes
- progress summary calculates actual Pomodoro equivalents
- progress summary returns zero actual Pomodoro equivalents when no sessions count
- progress summary calculates remaining estimated minutes
- progress summary never returns negative remaining estimated minutes
- progress summary marks estimate as exceeded when actual minutes exceed estimated minutes
- progress summary does not mark estimate as exceeded when actual minutes equal estimated minutes
- progress summary does not mark estimate as exceeded when the task has no estimate
- progress summary handles tasks without estimates
- progress summary rejects missing tasks

### List progress tests

- listing task progress returns one summary per selected task
- listing task progress preserves first-seen task id order
- listing task progress ignores duplicate task ids
- listing task progress rejects empty selections
- listing task progress rejects missing task ids
- listing task progress calculates each task independently

---

## Out of Scope

The following features must not be implemented in this spec:

- starting or ending Pomodoro sessions
- pausing or resuming sessions
- stale paused session recovery
- switching tasks during a Pomodoro
- carrying remaining minutes into a new session
- automatic estimate updates
- task completion based on progress
- reports and statistics screens
- CSV export
- browser countdown timer
- frontend screens
- FastAPI routes
- SQLModel persistence
- Alembic migrations
- background jobs

These features will be handled in later specs.

`008_focus_session_recovery_and_switching.md` will define stale-session recovery and task-switching workflows.

---

## Expected Outcome

After this spec is implemented, the system should have a tested application core capable of:

- storing optional estimated Pomodoro counts on tasks
- clearing task Pomodoro estimates
- calculating actual focus minutes from session history
- including partial focus sessions in progress
- comparing actual focus work against estimates
- returning progress summaries for one or more tasks

This foundation must remain independent from the database, web interface, reports, CSV export, and browser timer.
