# 006 - Pomodoro Sessions

## Purpose

Define the core behavior for creating and tracking Pomodoro-style focus sessions in Tomatempo.

Pomodoro sessions are the foundation for time tracking, focus flow, daily planning, reports, and statistics. The application must be able to start, complete, interrupt, and inspect focus sessions without depending on a database, web interface, browser timer, notifications, or background workers.

This spec builds on the behavior already defined in:

- `001_task_project_core.md`
- `004_task_listing_and_filters.md`
- `005_batch_task_editing.md`

The goal is to create a predictable application-level session workflow that can later be backed by SQLModel repositories and connected to a browser timer, but can already be tested with fake or in-memory repositories.

---

## Concepts

### Pomodoro Session

A Pomodoro session represents one timed focus or break interval.

For this spec, a session may be associated with a task, but task association is optional. This allows the user to track unplanned focus time or breaks that are not tied to a specific task.

### Session Type

A session type describes the kind of interval being tracked.

Allowed session types:

- `focus`
- `short_break`
- `long_break`

### Session Status

A session status describes the lifecycle state of a session.

Allowed session statuses:

- `planned`
- `running`
- `paused`
- `completed`
- `interrupted`

### Active Session

An active session is a session with status `running` or `paused`.

For this spec, there may be at most one active session at a time.

### Session Result

A completed or interrupted session should retain enough information to support later reports.

It should include:

- when the session started
- when the session ended
- planned duration
- actual duration
- whether it was completed or interrupted
- optional task association

Partial focus sessions are valid session results. If a focus session ends after 10 minutes, it should record 10 actual minutes for its associated task.

Task-level estimates and progress summaries are out of scope for this spec and will be handled in `007_task_pomodoro_estimates_and_progress.md`.

---

## Session Defaults

The system must provide default durations for session types.

Default durations:

- focus: 25 minutes
- short break: 5 minutes
- long break: 15 minutes

Expected behavior:

- starting a session without a custom duration uses the default for its session type
- starting a session with a custom duration uses the provided duration
- planned duration is stored in minutes
- planned duration must be a positive integer

---

## Task Association

### Focus sessions

A focus session may be associated with a task.

Expected behavior:

- accepts an optional task id
- rejects missing task ids
- rejects archived tasks
- allows focus sessions without a task

### Break sessions

Break sessions must not be associated with a task.

Expected behavior:

- rejects task ids for `short_break`
- rejects task ids for `long_break`

This keeps break time separate from task work for later reports.

---

## Session Lifecycle

### Start session

The system must support starting a new session.

Expected behavior:

- creates a session with status `running`
- sets `started_at`
- leaves `ended_at` as `None`
- stores session type
- stores planned duration in minutes
- stores optional task id for focus sessions
- rejects starting a session when another session is already running
- rejects invalid session type values
- rejects invalid planned duration values

### Complete session

The system must support completing a running session.

Expected behavior:

- accepts a running or paused session id
- sets status to `completed`
- sets `ended_at`
- calculates actual duration in minutes
- preserves planned duration
- rejects missing session ids
- rejects sessions that are not running or paused

Completing a session means the user finished the intended interval.

### Pause session

The system must support pausing a running session.

Expected behavior:

- accepts a running session id
- sets status to `paused`
- sets `paused_at`
- updates `updated_at`
- rejects missing session ids
- rejects sessions that are not running

Pausing a session means the user temporarily stopped the interval and intends to continue it later.

### Resume session

The system must support resuming a paused session.

Expected behavior:

- accepts a paused session id
- sets status to `running`
- adds the paused duration to accumulated pause time
- clears `paused_at`
- updates `updated_at`
- rejects missing session ids
- rejects sessions that are not paused

Resuming a session continues the same Pomodoro session rather than creating a new one.

### Interrupt session

The system must support interrupting a running or paused session.

Expected behavior:

- accepts a running or paused session id
- sets status to `interrupted`
- sets `ended_at`
- calculates actual duration in minutes
- stores an optional interruption reason
- trims the interruption reason
- stores `None` when the interruption reason is missing or blank
- rejects missing session ids
- rejects sessions that are not running or paused

Interrupting a session means the user explicitly abandons the interval instead of completing or continuing it.

Closing the application during a session should not automatically mean the session was interrupted. Running and paused sessions should be persistable so they can be recovered later.

Persisting session state is for resilience and history. It should not imply that very old paused sessions are still healthy focus sessions. Recovery behavior for stale sessions can be defined in a later spec if needed.

### Discard planned session

Planned sessions are included in the status model for future scheduling behavior.

Creating, editing, or discarding planned sessions is out of scope for this spec.

---

## Time Rules

The application layer must receive time from the caller or an injected clock rather than reading browser state.

Expected behavior:

- `started_at` must be timezone-aware
- `ended_at` must be timezone-aware
- `paused_at` must be timezone-aware when present
- completing or interrupting a session requires `ended_at` to be after `started_at`
- actual duration is calculated from `started_at` and `ended_at`, excluding accumulated paused time
- actual duration is stored as whole minutes
- actual duration rounds down partial minutes
- actual duration must never be negative

For example:

- 25 minutes and 59 seconds stores `25`
- 30 seconds stores `0`

---

## Active Session Rules

The system must prevent overlapping active sessions.

Expected behavior:

- starting a session fails if any running or paused session already exists
- completing the active session allows a new session to start
- interrupting the active session allows a new session to start
- resuming a paused session continues the existing active session
- completed and interrupted sessions do not count as active

---

## Task Status Integration

Starting a focus session for a task should move the task into active work.

Expected behavior:

- when starting a focus session for a task with status `todo`, update the task status to `doing`
- update the task `updated_at` when changing status to `doing`
- leave tasks with status `doing` unchanged
- leave tasks with status `done` unchanged
- reject archived tasks

Completing or interrupting a session must not automatically complete, reopen, or archive the task.

Task completion remains controlled by the task and batch task editing use cases.

Switching from one task to another during a Pomodoro should be represented by ending the current task's session and starting a new session for the next task. A later spec will define the workflow for carrying remaining minutes into the new session.

---

## Required Use Cases

### Start Pomodoro session

Given a session type, optional task id, optional planned duration, and start time, the system must create a running session.

Expected behavior:

- validates session type
- validates task association rules
- validates planned duration
- rejects overlapping running sessions
- updates task status from `todo` to `doing` for task-linked focus sessions
- saves the session
- returns the created session

### Complete Pomodoro session

Given a running or paused session id and end time, the system must complete the session.

Expected behavior:

- retrieves the session
- validates that it is running
- validates end time
- sets completion fields
- saves the session
- returns the completed session

### Pause Pomodoro session

Given a running session id and pause time, the system must pause the session.

Expected behavior:

- retrieves the session
- validates that it is running
- validates pause time
- sets pause fields
- saves the session
- returns the paused session

### Resume Pomodoro session

Given a paused session id and resume time, the system must resume the session.

Expected behavior:

- retrieves the session
- validates that it is paused
- validates resume time
- accumulates paused duration
- clears pause fields
- saves the session
- returns the running session

### Interrupt Pomodoro session

Given a running or paused session id, end time, and optional reason, the system must interrupt the session.

Expected behavior:

- retrieves the session
- validates that it is running
- validates end time
- normalizes the interruption reason
- sets interruption fields
- saves the session
- returns the interrupted session

### Get active Pomodoro session

The system must support retrieving the current active session.

Expected behavior:

- returns the running or paused session when one exists
- returns `None` when no active session exists

---

## Pomodoro Session Fields

A Pomodoro session must include:

- `id`
- `type`
- `status`
- `planned_duration_minutes`
- `actual_duration_minutes`
- `task_id`
- `started_at`
- `paused_at`
- `accumulated_pause_seconds`
- `ended_at`
- `interruption_reason`
- `created_at`
- `updated_at`

### Field rules

- `task_id` may be `None`
- `actual_duration_minutes` is `None` while the session is running or paused
- `ended_at` is `None` while the session is running or paused
- `paused_at` is set only while the session is paused
- `accumulated_pause_seconds` starts at `0`
- `interruption_reason` is only used for interrupted sessions
- `created_at` is set when the session is created
- `updated_at` changes when the session is paused, resumed, completed, or interrupted

---

## Error Behavior

Pomodoro session use cases should fail fast for invalid operation input.

Suggested error codes or exception categories:

- `invalid_session_type`
- `invalid_session_status`
- `invalid_duration`
- `invalid_time_range`
- `active_session_exists`
- `missing_session`
- `missing_task`
- `archived_task`
- `task_not_allowed_for_break`

The exact exception hierarchy can be decided during implementation, but tests should assert meaningful failure behavior.

---

## Application-Level Test Scenarios

The agent should create application-level tests for the following behaviors.

These tests should use fake or in-memory repositories.

Do not use SQLModel, FastAPI, Jinja2, templates, HTTP, browser timers, background workers, or a real database in these tests.

### Start session tests

- starting a focus session creates a running session
- starting a focus session sets `started_at`
- starting a focus session stores planned duration
- starting a focus session uses the default focus duration
- starting a short break uses the default short break duration
- starting a long break uses the default long break duration
- starting a session accepts a custom planned duration
- starting a session rejects invalid session type values
- starting a session rejects zero or negative planned duration
- starting a session rejects naive `started_at`

### Task association tests

- starting a focus session can associate a task
- starting a focus session can run without a task
- starting a focus session rejects a missing task
- starting a focus session rejects an archived task
- starting a short break rejects task association
- starting a long break rejects task association
- starting a focus session for a todo task changes the task status to doing
- starting a focus session for a todo task updates task `updated_at`
- starting a focus session for a doing task leaves the task unchanged
- starting a focus session for a done task leaves the task unchanged

### Active session tests

- starting a session fails when another session is running
- starting a session fails when another session is paused
- completed sessions do not block starting a new session
- interrupted sessions do not block starting a new session
- getting active session returns the running session
- getting active session returns the paused session
- getting active session returns `None` when no active session exists

### Pause and resume tests

- pausing a running session marks it as paused
- pausing a running session sets `paused_at`
- pausing a running session updates `updated_at`
- pausing a missing session fails
- pausing a non-running session fails
- pausing a session rejects naive `paused_at`
- resuming a paused session marks it as running
- resuming a paused session clears `paused_at`
- resuming a paused session accumulates paused duration
- resuming a paused session updates `updated_at`
- resuming a missing session fails
- resuming a non-paused session fails
- resuming a session rejects naive resume time
- resuming a session rejects resume times before or equal to `paused_at`

### Complete session tests

- completing a running session marks it as completed
- completing a paused session marks it as completed
- completing a running session sets `ended_at`
- completing a running session calculates actual duration in minutes
- completing a paused session excludes paused time from actual duration
- completing a running session rounds actual duration down to whole minutes
- completing a running session updates `updated_at`
- completing a missing session fails
- completing a session that is not running or paused fails
- completing a session rejects naive `ended_at`
- completing a session rejects end times before or equal to start time
- completing a session does not automatically complete the associated task

### Interrupt session tests

- interrupting a running session marks it as interrupted
- interrupting a paused session marks it as interrupted
- interrupting a running session sets `ended_at`
- interrupting a running session calculates actual duration in minutes
- interrupting a paused session excludes paused time from actual duration
- interrupting a running session stores the interruption reason
- interrupting a running session trims the interruption reason
- interrupting a running session stores `None` for blank reason
- interrupting a running session updates `updated_at`
- interrupting a missing session fails
- interrupting a session that is not running or paused fails
- interrupting a session rejects naive `ended_at`
- interrupting a session rejects end times before or equal to start time
- interrupting a session does not automatically modify the associated task status

### Session field tests

- running sessions have no `ended_at`
- running sessions have no actual duration
- running sessions have no interruption reason
- running sessions have no `paused_at`
- paused sessions have `paused_at`
- paused sessions have no `ended_at`
- paused sessions have no actual duration
- completed sessions preserve planned duration
- interrupted sessions preserve planned duration
- session ids are generated
- session `created_at` is set
- session `updated_at` is set

---

## Out of Scope

The following features must not be implemented in this spec:

- browser countdown timer
- live ticking state
- planned session scheduling
- recurring Pomodoro cycles
- automatic long-break selection
- automatic task completion
- daily focus flow
- reports and statistics
- CSV export
- reminders
- notifications
- sounds
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

- starting focus and break sessions
- enforcing one active session at a time
- associating focus sessions with tasks
- moving todo tasks to doing when focus starts
- completing and interrupting running sessions
- calculating actual duration
- retrieving the active session

This foundation must remain independent from the database, web interface, and browser timer.
