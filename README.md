# Queueboard

Queueboard is a lightweight shared work queue for small teams. It gives incoming work a clear
place to land, keeps priority and status visible, and records activity without turning a simple
workflow into a full project-management system.

## What is included

- A server-rendered web interface for creating and managing work items
- A typed REST API with interactive OpenAPI documentation
- PostgreSQL persistence managed through Alembic migrations
- A Celery worker that records asynchronous activity events through Redis
- A Docker Compose environment for consistent local development
- Pytest, Ruff, and mypy validation in GitLab CI

## Run with Docker

Docker Compose is the fastest way to start the complete stack:

```bash
docker compose up --build
```

Once the services are healthy, open:

- Queueboard: <http://localhost:8000>
- Interactive API docs: <http://localhost:8000/docs>
- Health check: <http://localhost:8000/health>

PostgreSQL data is kept in the `queueboard-data` Docker volume. Stop the services with
`docker compose down`.

## Local Python development

Queueboard uses [uv](https://docs.astral.sh/uv/) and Python 3.12 or newer.

```bash
uv sync
uv run alembic upgrade head
uv run uvicorn queueboard.main:app --reload
```

Without a `.env` file, local processes use the SQLite database at `tmp/queueboard.db`. A Redis
broker is still required to process background activity. To use PostgreSQL locally, copy
`.env.example` and change the `db` and `redis` hostnames to `localhost`.

Start the worker in a second terminal:

```bash
uv run celery -A queueboard.celery_app:celery_app worker --loglevel=INFO
```

## API

| Method | Path | Purpose |
| --- | --- | --- |
| `GET` | `/api/work-items` | List work items, optionally filtered by status |
| `POST` | `/api/work-items` | Create a work item |
| `GET` | `/api/work-items/{id}` | Read a work item and its activity |
| `PATCH` | `/api/work-items/{id}` | Update selected fields |
| `DELETE` | `/api/work-items/{id}` | Delete a work item |

The generated schema at `/openapi.json` is the canonical API contract.

## Validation

Run the same checks used by CI:

```bash
make check
```

Individual commands are available as `make lint`, `make typecheck`, and `make test`.

## Database migrations

After changing SQLAlchemy models, generate and inspect a migration:

```bash
uv run alembic revision --autogenerate -m "describe the schema change"
uv run alembic upgrade head
```

Commit model and migration changes together.

## Configuration

| Variable | Default | Description |
| --- | --- | --- |
| `APP_ENV` | `development` | Environment label reported by the health endpoint |
| `BUILD_REVISION` | `dev` | Source revision reported by the health endpoint |
| `DATABASE_URL` | `sqlite:///./tmp/queueboard.db` | SQLAlchemy database URL |
| `CELERY_BROKER_URL` | `redis://localhost:6379/0` | Celery broker |
| `CELERY_RESULT_BACKEND` | `redis://localhost:6379/1` | Celery result backend |
| `CELERY_TASK_ALWAYS_EAGER` | `false` | Execute jobs inline; intended for tests only |

## License

Queueboard is available under the [MIT License](LICENSE).
