# AGENTS.md

## Project Overview

Tomatempo is a web-based time management application inspired by Pomodoro workflows, focused on data ownership, CSV-based automation, batch task operations, and clean extensibility.

The project uses Python, FastAPI, Jinja2, SQLModel, Alembic, and pytest.

All code, comments, docstrings, commit messages suggested by agents, test names, and technical documentation must be written in English.

---

## Architecture

This project follows Clean Architecture principles.

The main folders are:

### `src/tomatempo/domain/`

Contains the core business concepts of the application.

This layer should contain entities, value objects, domain rules, and domain services. It must not depend on FastAPI, SQLModel, Alembic, databases, HTTP, templates, or external frameworks.

### `src/tomatempo/application/`

Contains application use cases and ports.

This layer orchestrates business actions, such as importing tasks from CSV, applying tags in batch, creating projects, or registering Pomodoro sessions. It may define repository interfaces/protocols, but it must not know how persistence is implemented.

### `src/tomatempo/infrastructure/`

Contains technical implementations.

This includes SQLModel models, database sessions, concrete repositories, Alembic integration, CSV readers/writers, and other external integrations. This layer may depend on frameworks and libraries.

### `src/tomatempo/interface/`

Contains user-facing entry points.

This includes FastAPI routes, Jinja2 templates, request parsing, response rendering, and web-specific behavior. Business logic must not live here. Routes should call application use cases.

### `tests/`

Contains the automated test suite.

Tests should be organized by layer whenever possible:

- `tests/domain/`
- `tests/application/`
- `tests/infrastructure/`
- `tests/interface/`

---

## Testing

This project uses `pytest`.

Tests are part of the system contract and must be treated as first-class development artifacts.

Prefer writing tests before production code.

For each new feature:

1. Read the relevant spec in `docs/specs/`.
2. Create or update tests that express the expected behavior.
3. Do not implement production code until the tests clearly define the behavior.
4. Prefer application-level tests first, using fake or in-memory repositories when possible.
5. After tests are approved, implement the simplest production code that passes them.
6. Refactor only after behavior is covered by tests.

---

## Revised Tests Policy

The user may manually mark reviewed tests with the pytest mark:

```python
@pytest.mark.revised
````

A test marked with `revised` is considered reviewed and protected.

Once a test is marked as `revised`, agents must NEVER modify it during normal production-code implementation.

Agents may only modify tests marked as `revised` when the user explicitly authorizes it in the current conversation with this exact phrase:

```text
You are authorized to edit the revised test file.
```

Even with permission granted, follow the rules given by the user about what could be changed on these files.

If an agent believes that a `revised` test must be changed in order to make the system work, but the user has not explicitly authorized changes to revised tests, the agent must:

1. Leave the revised test unchanged.
2. Inform the user that a revised test appears to require modification.
3. Explain why the change seems necessary.
4. Wait for explicit authorization before changing it.

Do not bypass this rule.

Do not silently rewrite, weaken, remove, skip, xfail, or loosen assertions from tests marked as `revised`.

---

## Test Modification Rules

Existing tests should be preserved whenever possible.

Do not modify old tests unless strictly necessary.

If modifying any non-revised test, explain why the change was required.

Never change tests merely to make implementation easier.

Never delete tests without explicit justification.

---

## Validation Commands

Before considering a task complete, run the validation suite when applicable:

```bash
pytest
ruff check .
mypy .
```

If some command is not configured yet, report that clearly instead of pretending it passed.

---

## Development Workflow

Tests are the contract between the user and the agent. Once approved, production code must adapt to the tests, not the other way around.

For each new feature, the user and the agent should follow this cycle:

1. **[User or mostly User]** Read, create, or refine a small spec in `docs/specs/`.
2. **[Agent]** Create tests that express the expected behavior described by the spec.
3. **[User]** Review the generated tests and decide whether they correctly represent the intended behavior.
4. **[Agent]** Adjust tests only when requested by the user during the test-review phase.
5. **[User]** Approve the tests and mark reviewed tests with `@pytest.mark.revised` before production code is implemented.
6. **[Agent]** Do not implement production code until the relevant tests have been approved.
7. **[Agent]** Implement the simplest production code that passes the approved tests.
8. **[Agent]** Run the validation commands.
9. **[Agent]** Fix implementation errors without weakening, deleting, skipping, or bypassing approved tests.
10. **[User and Agent]** Review the resulting design and refactor only after tests pass.
11. **[Agent]** Keep changes small and focused on the current spec.

---

## Code Style

All code must be written in English.

All comments must be written in English.

All docstrings must be written in English.

All test function names must be written in English.

Use clear names that describe behavior, not implementation details.

Prefer simple, explicit code over clever abstractions.

Avoid overengineering.

---

## Clean Architecture Rules

Domain code must not depend on infrastructure code.

Application code must not depend on FastAPI, SQLModel, Alembic, or Jinja2.

Infrastructure may depend on domain and application layers.

Interface may depend on application use cases.

Business rules must not be implemented inside FastAPI routes, templates, SQLModel models, or Alembic migrations.

Repository interfaces should live in the application layer.

Repository implementations should live in the infrastructure layer.

---

## Database and Migrations

Use SQLModel for persistence models.

Use Alembic for database migrations.

Do not change the database schema without creating or updating the corresponding migration.

Keep database models separate from domain entities unless there is a strong reason not to.

---

## Agent Behavior

Keep changes focused.

Do not rewrite unrelated files.

Do not introduce new dependencies without justification.

Do not perform large architectural changes without explaining the reason.

When uncertain, prefer asking or reporting the uncertainty rather than making silent assumptions.

The goal is not to generate large amounts of code quickly. The goal is to evolve the system safely through clear specs, strong tests, and small implementation steps.
