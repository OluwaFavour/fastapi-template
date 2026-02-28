# FastAPI Template

A production-ready FastAPI project template with a layered architecture, async SQLAlchemy, RabbitMQ messaging, APScheduler, SQLAdmin, and comprehensive tooling.

## Architecture

```
app/
├── core/                   # Shared kernel — no domain logic
│   ├── config.py           # Pydantic Settings (env vars)
│   ├── logger.py           # Structured logging + Sentry
│   ├── enums.py            # Shared enumerations
│   ├── utils.py            # Pure utility functions (JWT, OTP, hashing)
│   ├── db/
│   │   ├── config.py       # Async engine, sessionmaker, Base
│   │   ├── models/
│   │   │   ├── base.py     # Abstract BaseModel (UUID pk, soft-delete, timestamps)
│   │   │   └── user.py     # User model
│   │   └── crud/
│   │       ├── base.py     # Generic BaseDB[T] with 20+ CRUD methods
│   │       └── user.py     # UserDB singleton
│   ├── services/
│   │   ├── base.py         # SingletonService mixin
│   │   ├── event_publisher.py  # Publisher Protocol + registry
│   │   └── lifecycle.py    # Post-signup hook registry
│   ├── exceptions/
│   │   ├── types.py        # 15 typed exception classes
│   │   └── handlers.py     # FastAPI exception handlers + OpenAPI schemas
│   └── dependencies/
│       ├── db.py           # get_async_session
│       ├── auth.py         # JWT auth chain (current_user → active → verified)
│       └── internal.py     # Internal API key verification
│
├── apps/                   # Domain modules (one folder per bounded context)
│   └── example_app/
│       ├── db/models/      # App-specific ORM models
│       ├── db/crud/        # App-specific CRUD singletons
│       ├── schemas/        # Pydantic request/response schemas
│       └── routers/        # FastAPI routers
│
├── admin/                  # SQLAdmin dashboard
│   ├── auth.py             # HMAC-based admin authentication
│   ├── views.py            # ModelView definitions
│   └── setup.py            # init_admin(app) mounting
│
├── infrastructure/         # External service integrations
│   ├── messaging/          # RabbitMQ (aio-pika)
│   │   ├── connection.py   # Connection factory
│   │   ├── publisher.py    # publish_event()
│   │   ├── consumer.py     # Message processing with retry/DLQ
│   │   ├── queues.py       # Queue configuration models
│   │   └── main.py         # Consumer entry point
│   └── scheduler/          # APScheduler
│       ├── main.py         # Scheduler setup + initialization
│       └── jobs.py         # Scheduled job definitions
│
└── main.py                 # Composition root (lifespan, middleware, routers)
```

### Layer Rules

These are enforced by [import-linter](https://github.com/seddonym/import-linter) contracts in `pyproject.toml`:

| Rule | Description |
|------|-------------|
| **Core is independent** | `app.core` never imports from `apps`, `admin`, or `infrastructure` |
| **Apps depend only on core** | `app.apps.*` imports only from `app.core` |
| **Admin depends on core + apps** | `app.admin` imports from core and apps, never infrastructure |
| **Infrastructure depends on core** | `app.infrastructure` imports only from `app.core` |
| **No circular app imports** | App modules cannot import from each other |
| **Tests can import anything** | Test code has unrestricted access |
| **main.py is the composition root** | Only `app.main` wires all layers together |

## Quick Start

### 1. Use this template

Click **"Use this template"** on GitHub, or clone and re-init:

```bash
git clone https://github.com/YOUR_USERNAME/fastapi-template.git my-project
cd my-project
rm -rf .git && git init
```

### 2. Rename the project

Run the setup script to replace all placeholder names:

```bash
python setup_project.py
```

This will prompt for your project name and update all references.

### 3. Environment setup

```bash
# Create virtual environment
python -m venv .venv
source .venv/bin/activate  # Linux/Mac
# .venv\Scripts\activate   # Windows

# Install dependencies
pip install -r requirements.txt -r requirements-dev.txt

# Copy environment variables
cp .env.example .env
# Edit .env with your actual values
```

### 4. Database setup

```bash
# Start PostgreSQL (via Docker)
docker compose up db -d

# Run migrations
python manage.py migrate
```

### 5. Run the server

```bash
python manage.py runserver
```

Visit: http://localhost:8000/docs

## CLI Commands (`manage.py`)

| Command | Description |
|---------|-------------|
| `runserver` | Start uvicorn (reload in debug, production otherwise) |
| `makemigrations [comment]` | Generate Alembic migration |
| `migrate` | Apply migrations to head |
| `showmigrations` | Show migration history |
| `clearalembic` | Reset Alembic version table |
| `createextensions [ext...]` | Ensure PostgreSQL extensions exist |
| `generateopenapi` | Export OpenAPI schema to `openapi.json` |
| `worker` | Run RabbitMQ message consumer |
| `scheduler` | Run APScheduler standalone |
| `precommit [--fix] [--skip-tests]` | Run full lint/test pipeline |

## Docker

### Full stack

```bash
docker compose --profile full up --build
```

### API only (no worker/scheduler)

```bash
docker compose --profile api-only up --build
```

### Profiles

| Profile | Services |
|---------|----------|
| `full` | db + redis + rabbitmq + api + worker + scheduler |
| `api-only` | db + redis + api |
| `worker-only` | db + redis + rabbitmq + worker |
| `scheduler-only` | db + redis + scheduler |

## Testing

```bash
# Run all tests
pytest

# With coverage
pytest --cov=app --cov-report=html

# Quick run
pytest -x -q --tb=short
```

Tests use a real PostgreSQL database with Alembic migrations applied once per session. Each test runs in a rolled-back transaction for isolation.

## Code Quality

```bash
# Full check (same as CI)
python manage.py precommit

# Auto-fix formatting
python manage.py precommit --fix

# Individual tools
black app/ tests/
ruff check app/ tests/
pyright app/
lint-imports
```

## Adding a New App Module

1. Create the folder structure:

```
app/apps/my_app/
├── __init__.py
├── db/
│   ├── models/
│   │   ├── __init__.py
│   │   └── my_model.py
│   └── crud/
│       ├── __init__.py
│       └── my_model.py
├── schemas/
│   ├── __init__.py
│   └── my_model.py
└── routers/
    ├── __init__.py
    └── my_model.py
```

2. Register the model import in `app/main.py`:

```python
import app.apps.my_app.db.models  # noqa: F401
```

3. Mount the router in `app/main.py`:

```python
from app.apps.my_app.routers import my_router
app.include_router(my_router, prefix="/api", tags=["MyApp"])
```

4. Add admin views in `app/admin/views.py` if needed.

5. Generate and run the migration:

```bash
python manage.py makemigrations "add my_app models"
python manage.py migrate
```

## Adding Infrastructure Services

To add a new external service (e.g., email provider, cloud storage):

1. Create a service class in `app/infrastructure/` following the `SingletonService` pattern.
2. Initialize it in the `lifespan` function in `app/main.py`.
3. If it publishes events, register it with `register_publisher()`.
4. If it needs post-signup behavior, use `register_post_signup_hook()`.

## Stack

| Component | Technology |
|-----------|-----------|
| Framework | FastAPI |
| ORM | SQLAlchemy 2.0 (async) |
| Database | PostgreSQL + asyncpg |
| Migrations | Alembic |
| Auth | JWT (PyJWT) + bcrypt |
| Messaging | RabbitMQ (aio-pika) |
| Scheduler | APScheduler |
| Admin | SQLAdmin |
| Monitoring | Sentry |
| Linting | Ruff + Black + Pyright |
| Architecture | import-linter |
| Testing | pytest + pytest-asyncio |
| CI/CD | GitHub Actions |
| Deploy | Docker (multi-stage) |

## License

MIT
