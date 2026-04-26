from enum import StrEnum


class TaskStatus(StrEnum):
    TODO = "todo"
    DOING = "doing"
    DONE = "done"
    ARCHIVED = "archived"


class TaskPriority(StrEnum):
    NONE = "none"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class PomodoroSessionType(StrEnum):
    FOCUS = "focus"
    SHORT_BREAK = "short_break"
    LONG_BREAK = "long_break"


class PomodoroSessionStatus(StrEnum):
    PLANNED = "planned"
    RUNNING = "running"
    PAUSED = "paused"
    COMPLETED = "completed"
    INTERRUPTED = "interrupted"
