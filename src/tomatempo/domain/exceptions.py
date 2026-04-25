class TomatempoDomainError(Exception):
    """Base exception for domain rule violations."""


class InvalidProjectNameError(TomatempoDomainError):
    """Raised when a project name is empty or blank."""


class DuplicateProjectNameError(TomatempoDomainError):
    """Raised when a project name already exists."""


class InvalidTaskTitleError(TomatempoDomainError):
    """Raised when a task title is empty or blank."""


class DuplicateTaskTitleError(TomatempoDomainError):
    """Raised when a task title already exists in the same project."""


class InvalidTaskPriorityError(TomatempoDomainError):
    """Raised when a task priority is not allowed."""


class InvalidTagNameError(TomatempoDomainError):
    """Raised when a tag name is empty or blank."""


class DuplicateTagNameError(TomatempoDomainError):
    """Raised when a tag name already exists."""
