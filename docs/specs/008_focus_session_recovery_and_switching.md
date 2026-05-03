# 008 - Focus Session Recovery and Switching

## Purpose

Define higher-level focus-session workflow behavior around recovering active
sessions, discarding stale paused sessions, and switching from one task to
another while preserving accurate focus flow.

This spec builds on the behavior already defined in:

- `006_pomodoro_sessions.md`
- `007_task_pomodoro_estimates_and_progress.md`

The core Pomodoro session lifecycle remains intentionally small: start, pause,
resume, complete, interrupt, and inspect the active session. This spec describes
application workflows that coordinate those primitives when the user refreshes
the app, closes and reopens it, abandons a stale pause, or wants to keep using
the remaining focus time on another task.

The focus flow is primary. Task association is attribution. Switching tasks
during an active focus interval should preserve the user's focus momentum and
must not encourage ending focus early when meaningful planned focus time
remains.

This spec must remain independent from frontend screens, browser timers,
SQLModel persistence, background jobs, notifications, and operating-system app
lifecycle events.

---

## Concepts

### Focus Flow

The focus flow is the user's continuous Pomodoro-style sequence of focus and
break intervals.

Conceptually, a user may do:

- one focus interval
- one short break
- another focus interval
- another short break
- a focus interval that is paused and resumed
- one long break

At this conceptual level, the flow exists independently from tasks. Tasks
describe where focus time is attributed, not whether focus time exists.

### Focus Segment

A focus segment is the persisted record of focus time attributed to one task or
to no task.

For the current model, a `PomodoroSession` is allowed to serve as this persisted
focus segment. When the user switches tasks during one continuous focus
interval, the implementation may represent that continuous interval as multiple
back-to-back focus sessions:

- one ended session for the previous task
- one new session using the remaining planned minutes for the next task

This is an implementation strategy, not a product requirement to present the
experience as separate Pomodoros to the user.

### Pomodoro Completion Metrics

Counting focus-session records is not the same as counting completed Pomodoros.

If a 25-minute focus interval is represented as a 15-minute segment for task A
and a 10-minute segment for task B, task progress should attribute each segment
to its task. Pomodoro-level statistics should still be able to treat the 25
combined minutes as one full Pomodoro equivalent.

Expected behavior:

- task progress may sum focus minutes by task
- Pomodoro equivalents should be calculated from minutes, not raw session count
- reports must not assume that each focus session row is one full Pomodoro
- future reporting may group adjacent carry-over segments if it needs ritual
  Pomodoro counts rather than task attribution counts

### Recoverable Active Session

A recoverable active session is a persisted session that can still be presented
to the user as the current session after an application refresh, restart, or
state reload.

For this spec:

- a running session is recoverable
- a non-stale paused session is recoverable
- a stale paused session is not recoverable
- completed and interrupted sessions are not active and do not need recovery

### Stale Paused Session

A stale paused session is a paused session that has remained paused beyond the
allowed recovery threshold.

Default threshold:

- 1 hour

Expected behavior:

- a paused session becomes stale when `now - paused_at` is greater than 1 hour
- a paused session exactly 1 hour old is still recoverable
- a paused session without `paused_at` is invalid for recovery decisions
- the threshold may become configurable later, but starts as an application
  constant

### Discarded Session

A discarded session is a previously active session that the system has chosen
not to recover.

Discarding is different from interruption:

- interruption means the user explicitly abandons a session
- discard means the application refuses to treat stale paused state as a healthy
  ongoing session

For the first implementation, discarded stale paused sessions should be
persisted as interrupted sessions with a normalized interruption reason that
indicates stale pause discard.

Suggested reason:

```text
stale_pause_discarded
```

This preserves history, avoids silent deletion, unblocks new sessions, and keeps
task progress rules consistent with `007_task_pomodoro_estimates_and_progress.md`.

### Session Switch

A session switch is the workflow where the user ends the current focus session
for task A and optionally starts a new focus session for task B using the
remaining planned minutes from the first session.

The system must not reassign a session from task A to task B. Recorded focus
time belongs to the task associated with the session at the time it was ended.
However, this internal segmentation should preserve the user's sense of one
continuous focus interval when meaningful planned focus time remains.

---

## Recovery Rules

### Application close is not interruption

Closing the application, refreshing the browser, or restarting the server should
not automatically interrupt a running or paused session.

Expected behavior:

- running sessions remain running until a use case changes them
- paused sessions remain paused until a use case changes them
- active session state can be recovered after reload
- no session result should be created solely because the application process or
  browser page was closed

This keeps accidental app lifecycle events separate from user intent.

### Get recoverable active session

The system should expose a workflow for reading the current active session while
applying stale paused-session rules.

Expected behavior:

- accepts the current time as a timezone-aware datetime
- rejects naive current times
- returns `None` when no active session exists
- returns a running session when one exists
- returns a paused session when it is not stale
- discards a stale paused session
- returns `None` after discarding a stale paused session

This use case is intended for application startup, browser refresh, and any
interface that needs to restore the current timer state.

### Discard stale paused session

When a paused session is stale, the system should stop treating it as active.

Expected behavior:

- only paused sessions can be discarded as stale
- stale detection uses `paused_at`, not `updated_at`
- the session is saved with status `interrupted`
- `ended_at` is set to the discard time
- `paused_at` is cleared
- `actual_duration_minutes` is calculated using the normal duration rules
- accumulated paused time includes the stale paused interval up to discard time
- interruption reason is set to `stale_pause_discarded`
- the discarded session no longer blocks starting a new session

The actual duration should represent focus time before the pause, not the time
the application was closed or waiting during the stale pause.

Example:

- focus session starts at 09:00
- user pauses at 09:10
- user returns at 11:00
- paused interval is stale
- session is discarded at 11:00
- actual duration is 10 minutes
- session status becomes `interrupted`

### Running sessions are recoverable

Running sessions should not be considered stale by this spec.

Expected behavior:

- a running session is returned by recovery even if it started a long time ago
- recovery does not update the running session
- deciding whether an old running session should be interrupted, completed, or
  kept is a user workflow outside this stale paused-session rule

This avoids silently changing state when the application cannot know whether the
user kept working while the app was closed.

---

## Remaining Planned Minutes

### Calculation

Remaining planned minutes are calculated from one focus session:

```text
planned_duration_minutes - actual_duration_minutes
```

Expected behavior:

- uses the session's stored planned duration
- uses the actual duration calculated when the session is completed or
  interrupted
- excludes paused time because actual duration already excludes pauses
- returns `0` when actual duration equals planned duration
- returns `0` when actual duration exceeds planned duration
- never returns a negative value

### Meaningful remaining time

Remaining time should only be offered for carry-over when it is meaningful.

Expected behavior:

- remaining minutes greater than `0` are meaningful
- remaining minutes equal to `0` are not meaningful
- sessions without `actual_duration_minutes` do not produce carry-over minutes
- break sessions do not produce task-switch carry-over minutes

This prevents creating zero-minute sessions and keeps carry-over focused on
partial focus sessions.

---

## Task-Switching Workflow

Task switching exists to maximize usable focus time. When the user finishes or
abandons a task before the planned focus interval is over, the preferred
workflow is to continue focusing on another task instead of stopping focus early.

The application layer should therefore make it possible to carry remaining focus
minutes forward. The interface may still let the user stop, but the application
workflow should not make stopping the only easy path.

### End current focus session for switching

When the user wants to stop working on task A and continue with task B, the
system should end the current focus session for task A first.

Expected behavior:

- accepts the active focus session id
- accepts an end time
- rejects missing sessions
- rejects sessions that are not running or paused
- rejects break sessions
- completes or interrupts the current focus session according to user intent
- records actual focus minutes for the current session
- calculates remaining planned minutes after ending the current session
- returns the ended session and remaining planned minutes

User intent should be explicit:

- completing means the current interval or task work is considered finished
- interrupting means the current interval was intentionally abandoned

The application may later expose this as buttons such as "finish and switch" or
"interrupt and switch", but interface labels are out of scope for this spec.

### Start next focus session with remaining minutes

After ending the current session, the user may start a new focus session for
another task using the remaining planned minutes.

Expected behavior:

- accepts a target task id
- accepts a start time
- accepts positive remaining planned minutes
- starts a new focus session associated with the target task
- uses the remaining minutes as `planned_duration_minutes`
- applies the existing task association rules from `006_pomodoro_sessions.md`
- moves a target task from `todo` to `doing` using the existing start-session
  behavior
- rejects missing target tasks
- rejects archived target tasks
- rejects zero or negative remaining minutes

The new session is independent from the previous session as a persistence
record. It has its own id, task id, start time, status, planned duration, and
eventual actual duration.

At the product level, this should still behave like a continuation of the
current focus interval when it is started from carry-over minutes. The user does
not need to experience the switch as having completed two separate Pomodoros.

### Optional carry-over

Carrying remaining time should be optional.

Expected behavior:

- the system should be able to return remaining planned minutes without
  automatically starting a new session
- the user may choose to start a regular full Pomodoro instead of using the
  remaining minutes
- if no meaningful remaining minutes exist, the carry-over option should not be
  offered by application workflows

The application layer should expose enough information for the interface to make
this choice explicit.

### Task ownership of actual minutes

Actual minutes must remain attached to the session where they were recorded.

Expected behavior:

- task A keeps the actual minutes from the ended session
- task B receives no actual minutes until its own new session is completed or
  interrupted
- the original session is not reassigned to task B
- task progress summaries continue to derive actual minutes from completed or
  interrupted focus sessions
- Pomodoro-level reports should not count the task A segment and task B segment
  as two full Pomodoros merely because they are stored as two sessions

Example:

- user starts a 25-minute focus session for task A at 09:00
- user finishes task A at 09:15
- session for task A is completed with 15 actual minutes
- remaining planned minutes are 10
- user starts a new 10-minute focus session for task B at 09:15
- task A progress includes 15 actual minutes
- task B progress includes 0 actual minutes until the new session ends
- Pomodoro-equivalent reporting may treat the combined 25 focus minutes as one
  Pomodoro equivalent

---

## Reporting Guidance

This spec does not implement reports, but it must protect future report design
from misleading assumptions.

Expected behavior:

- task reports should attribute actual focus minutes to the task associated with
  each focus segment
- task progress can use Pomodoro equivalents derived from minutes
- flow reports should not count focus-session records as full Pomodoros without
  considering duration
- a future report that needs complete Pomodoro cycles may group adjacent
  carry-over focus segments or calculate equivalents from total focus minutes
- break sessions remain separate from focus segments and should not be attached
  to tasks

This keeps the current persistence model practical while preserving the
conceptual model where the user is doing a Pomodoro flow, not merely doing a
task.

---

## Required Use Cases

### Recover active Pomodoro session

Given the current time, the system must return the recoverable active session or
discard stale paused state.

Expected behavior:

- retrieves the active session from the repository
- validates the current time
- returns `None` when there is no active session
- returns running sessions unchanged
- returns non-stale paused sessions unchanged
- discards stale paused sessions
- returns `None` after stale discard

### Discard stale paused Pomodoro session

Given a paused session and the current time, the system must discard the session
when it is stale.

Expected behavior:

- rejects missing sessions
- rejects non-paused sessions
- rejects paused sessions without `paused_at`
- rejects naive current times
- rejects discard times before or equal to `paused_at`
- rejects non-stale paused sessions
- saves the stale session as interrupted
- calculates actual duration excluding all paused time
- clears `paused_at`
- returns the discarded session

This use case may be private application logic behind recovery, but tests should
still cover the behavior at the application layer.

### End focus session for task switch

Given an active focus session, an end time, and an ending mode, the system must
end the current session and report carry-over information.

Expected behavior:

- accepts ending mode `complete` or `interrupt`
- rejects invalid ending modes
- rejects missing sessions
- rejects inactive sessions
- rejects break sessions
- calculates actual duration using existing session lifecycle rules
- calculates remaining planned minutes
- returns the ended session
- returns remaining planned minutes
- indicates whether the remaining minutes are meaningful

### Start carried-over focus session

Given a target task and remaining planned minutes, the system must start a new
focus session with that shortened planned duration.

Expected behavior:

- starts a focus session for the target task
- stores the provided remaining minutes as planned duration
- rejects missing or archived tasks through normal start-session rules
- rejects zero or negative remaining minutes
- rejects starting when another active session exists
- returns the new session

This can reuse the existing start-session behavior, but the shorter duration
must be explicit and testable.

---

## Error Behavior

Focus recovery and switching use cases should fail fast for invalid operation
input.

Suggested error codes or exception categories:

- `naive_datetime`
- `missing_session`
- `invalid_session_state`
- `missing_paused_at`
- `non_stale_paused_session`
- `invalid_switch_mode`
- `invalid_remaining_minutes`
- `missing_task`
- `archived_task`
- `active_session_exists`

The exact exception hierarchy can be decided during implementation, but tests
should assert meaningful failure behavior.

---

## Application-Level Test Scenarios

The agent should create application-level tests for the following behaviors.

These tests should use fake or in-memory repositories.

Do not use SQLModel, FastAPI, Jinja2, templates, HTTP, browser timers,
notifications, background workers, reports, CSV export, or a real database in
these tests.

### Recovery tests

- recovering active session returns `None` when no active session exists
- recovering active session returns a running session
- recovering active session returns a non-stale paused session
- recovering active session rejects a naive current time
- recovering active session discards a stale paused session
- recovering active session returns `None` after discarding a stale paused
  session
- recovering a running session does not update the session
- recovering a non-stale paused session does not update the session

### Stale paused-session tests

- paused session is stale when paused for more than 1 hour
- paused session is not stale when paused for exactly 1 hour
- paused session is not stale when paused for less than 1 hour
- stale detection uses `paused_at`
- discarding stale paused session marks it as interrupted
- discarding stale paused session sets `ended_at` to the discard time
- discarding stale paused session clears `paused_at`
- discarding stale paused session stores `stale_pause_discarded` as reason
- discarding stale paused session excludes paused time from actual duration
- discarded stale paused session no longer blocks starting a new session
- discarding a missing session fails
- discarding a running session fails
- discarding a completed session fails
- discarding an interrupted session fails
- discarding a paused session without `paused_at` fails
- discarding a non-stale paused session fails
- discarding with a naive current time fails
- discarding with a current time before or equal to `paused_at` fails

### Remaining planned-minute tests

- remaining planned minutes subtract actual duration from planned duration
- remaining planned minutes return `0` when actual duration equals planned
  duration
- remaining planned minutes return `0` when actual duration exceeds planned
  duration
- remaining planned minutes never return a negative value
- sessions without actual duration do not produce meaningful carry-over
- break sessions do not produce meaningful task-switch carry-over

### Task-switch ending tests

- ending a running focus session for switch completes it when mode is `complete`
- ending a running focus session for switch interrupts it when mode is
  `interrupt`
- ending a paused focus session for switch excludes paused time
- ending a focus session for switch returns the ended session
- ending a focus session for switch returns remaining planned minutes
- ending a focus session for switch marks positive remaining minutes as
  meaningful
- ending a focus session for switch marks zero remaining minutes as not
  meaningful
- ending a missing session for switch fails
- ending an inactive session for switch fails
- ending a break session for switch fails
- ending a session for switch with an invalid mode fails
- ending a session for switch with a naive end time fails

### Carry-over start tests

- starting carried-over focus session creates a running focus session
- starting carried-over focus session associates the target task
- starting carried-over focus session stores remaining minutes as planned
  duration
- starting carried-over focus session moves a `todo` target task to `doing`
- starting carried-over focus session leaves `doing` target task status unchanged
- starting carried-over focus session leaves `done` target task status unchanged
- starting carried-over focus session rejects missing target task
- starting carried-over focus session rejects archived target task
- starting carried-over focus session rejects zero remaining minutes
- starting carried-over focus session rejects negative remaining minutes
- starting carried-over focus session rejects starting while another session is
  active

### Task ownership tests

- switching tasks does not reassign the original session to the target task
- switching tasks may represent one continuous focus interval as multiple
  back-to-back focus sessions
- task A progress includes the actual minutes from the ended session
- task B progress excludes carried-over session minutes until that session ends
- task B progress includes its own actual minutes after the carried-over session
  is completed
- completing task A before switching is not required by the switching workflow
- Pomodoro equivalents across switched task segments are calculated from total
  focus minutes, not from the number of focus-session records

---

## Out of Scope

The following are intentionally out of scope for this spec:

- frontend prompts, modals, labels, or timer display behavior
- browser local storage or page visibility behavior
- automatic background cleanup jobs
- SQLModel persistence details
- Alembic migrations
- notification scheduling
- reports and charts
- introducing a dedicated focus-flow or Pomodoro-cycle aggregate
- CSV import or export
- planned-session scheduling behavior
- configurable stale thresholds in user settings
- deciding whether very old running sessions should be automatically stale

These can be defined in later specs when those layers are introduced.
