# Tomatempo

Tomatempo is a web-based time management application inspired by Pomodoro workflows, built with data ownership, CSV automation, and batch task operations in mind.

This repository currently contains the project foundation only: FastAPI, Jinja2, SQLModel, PostgreSQL, Alembic, Docker, and a Clean Architecture-oriented directory layout.

## Run locally with Docker

```bash
docker compose up --build
```

Then open:

```text
http://localhost
```

You should see:

```text
Tomatempo is running
```

## Migrations

Generate a migration:

```bash
docker compose run --rm app poetry run alembic revision --autogenerate -m "describe change"
```

Apply migrations:

```bash
docker compose run --rm app poetry run alembic upgrade head
```

## Quality checks

```bash
poetry run ruff check .
poetry run mypy src tests
poetry run pytest
```
