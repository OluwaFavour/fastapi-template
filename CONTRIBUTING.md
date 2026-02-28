# Contributing

This guide covers the project conventions and workflow for this codebase.

## Table of Contents

- [Getting Started](#getting-started)
- [Branch Naming](#branch-naming)
- [Commit Messages](#commit-messages)
- [Development Workflow](#development-workflow)
- [Code Style](#code-style)
- [Pre-commit Checks](#pre-commit-checks)
- [Testing Requirements](#testing-requirements)
- [Project Conventions](#project-conventions)
  - [Service pattern](#service-pattern)
  - [CRUD pattern](#crud-pattern)
  - [Router pattern](#router-pattern)
  - [Import rules](#import-rules)
  - [Enum naming](#enum-naming)
  - [Logging](#logging)
  - [Orchestration vs. responsibility](#orchestration-vs-responsibility)
  - [OpenAPI endpoint documentation](#openapi-endpoint-documentation)
  - [Background job pattern](#background-job-pattern)

---

## Getting Started

1. Clone and set up the development environment:

   ```bash
   git clone <repo-url>
   cd <project-name>
   python -m venv .venv
   source .venv/bin/activate   # Linux/macOS
   .\.venv\Scripts\Activate.ps1  # Windows

   pip install -r requirements.txt
   pip install -r requirements-dev.txt
   ```

2. Start infrastructure services:

   ```bash
   docker compose up db redis -d
   ```

3. Run migrations:

   ```bash
   python manage.py migrate
   ```

4. Verify everything works:

   ```bash
   pytest tests/ -x -q --tb=short
   ```

---

## Branch Naming

| Prefix | Purpose | Example |
| -------- | --------- | --------- |
| `feature/` | New features | `feature/user-profiles` |
| `fix/` | Bug fixes | `fix/auth-token-refresh` |
| `refactor/` | Code restructuring | `refactor/crud-pagination` |
| `docs/` | Documentation only | `docs/add-architecture-diagram` |
| `test/` | Test additions / fixes | `test/webhook-edge-cases` |
| `chore/` | Tooling, CI, deps | `chore/upgrade-sqlalchemy` |

---

## Commit Messages

Use the **Conventional Commits** format:

```text
<type>(<scope>): <short description>

[optional body]

[optional footer(s)]
```

### Types

| Type | When to use |
| ------ | ------------- |
| `feat` | A new feature |
| `fix` | A bug fix |
| `refactor` | Code change that neither fixes a bug nor adds a feature |
| `test` | Adding or updating tests |
| `docs` | Documentation only changes |
| `chore` | Build process, CI, dependencies |
| `perf` | Performance improvement |
| `style` | Formatting (no code change) |

### Rules

- Use **imperative mood**: "add feature" not "added feature"
- Keep the first line under **72 characters**
- Reference GitHub issues in the footer: `Closes #6`

---

## Development Workflow

1. Create your branch from `main` (or `dev` if you use a dev branch)
2. Make changes — write code, write tests
3. Run checks before committing: `python manage.py precommit`
4. Commit with a descriptive message
5. Push and open a PR

---

## Code Style

### Formatting — Black

[Black](https://black.readthedocs.io/) with default settings (line length 88).

```bash
black app/ tests/
```

### Linting — Ruff

[Ruff](https://docs.astral.sh/ruff/) handles import sorting and linting.

```bash
ruff check app/ tests/
```

### Type Checking — Pyright

[Pyright](https://microsoft.github.io/pyright/) for static type analysis. All new code should include type hints.

```bash
pyright app/
```

---

## Pre-commit Checks

```bash
python manage.py precommit
```

Runs Black → Ruff → Pyright → Import Linter → Pytest in sequence, stopping on the first failure.

```bash
# Auto-fix formatting
python manage.py precommit --fix

# Skip tests
python manage.py precommit --skip-tests
```

---

## Testing Requirements

- **All new features must have tests.** No exceptions.
- **Bug fixes should include a regression test.**
- **Don't break existing tests.**

### Test file naming

| Source file | Test file |
| ------------- | ----------- |
| `app/apps/example_app/routers/item.py` | `tests/apps/example_app/test_item_router.py` |
| `app/infrastructure/messaging/consumer.py` | `tests/infrastructure/messaging/test_consumer.py` |

### Test class naming

Group tests by endpoint or function:

```python
class TestCreateItem:
    """Tests for POST /api/items"""

class TestListItems:
    """Tests for GET /api/items"""
```

### Test method naming

Use `test_<what>_<condition>_<expected>`:

```python
def test_create_item_with_valid_data_returns_201(self):
def test_create_item_without_auth_returns_401(self):
def test_create_item_with_duplicate_title_returns_409(self):
```

---

## Project Conventions

### Service pattern

Services initialised once at startup inherit from `SingletonService` and expose a `classmethod` `init()` called in the lifespan:

```python
from app.core.services.base import SingletonService

class MyService(SingletonService):
    @classmethod
    def init(cls, config: str) -> None:
        cls._config = config
        cls._initialized = True

    @classmethod
    def do_something(cls) -> str:
        if not cls._initialized:
            raise RuntimeError("MyService not initialised")
        return cls._config
```

`SingletonService` provides `_initialized`, `is_initialized()`, and `_reset()` (for test teardown) automatically.

### CRUD pattern

Database operations go in `db/crud/` modules. Each CRUD class inherits from `BaseDB[T]`, a generic base that provides `get_by_id`, `get_all`, `create`, `update`, `delete`, and other common operations. Subclasses add domain-specific queries as **instance methods**:

```python
from app.core.db.crud.base import BaseDB
from app.apps.example_app.db.models import Item

class ItemDB(BaseDB[Item]):
    def __init__(self) -> None:
        super().__init__(model=Item)

    async def get_by_owner(
        self, session: AsyncSession, owner_id: UUID
    ) -> list[Item]:
        ...

# Module-level singleton used throughout the app
item_db = ItemDB()
```

Consumers import the pre-created instance (e.g. `from app.apps.example_app.db.crud import item_db`).

### Router pattern

Routers follow FastAPI conventions. Each endpoint function should:

1. Extract dependencies (auth, session, access guards)
2. Delegate to a **service** for writes/business logic, or call a **CRUD instance** directly for simple reads
3. Return a Pydantic response model

All database mutations use the **`async with session.begin()`** pattern — the block auto-commits on success and auto-rolls back on exception. Service and CRUD calls inside the block pass `commit_self=False` to defer the commit to the transaction manager:

```python
# Write — delegate to a service inside a transaction block
@router.post("/items")
async def create_item(
    body: ItemCreate,
    user: CurrentActiveUser,
    session: AsyncSession = Depends(get_async_session),
) -> ItemResponse:
    async with session.begin():
        item = await item_db.create(
            session, data={**body.model_dump(), "owner_id": user.id}, commit_self=False
        )
        return ItemResponse.model_validate(item)

# Read — CRUD directly is fine (no transaction block needed)
@router.get("/items")
async def list_items(
    session: AsyncSession = Depends(get_async_session),
) -> list[ItemResponse]:
    items = await item_db.get_all(session)
    return [ItemResponse.model_validate(i) for i in items]
```

Infrastructure code (scheduler jobs, message handlers) that doesn't receive a session via dependency injection creates its own transactional session:

```python
async with AsyncSessionLocal.begin() as session:
    await user_db.permanently_delete_soft_deleted(
        session, cutoff_date, commit_self=False
    )
```

### Import rules

**Ordering** — three groups, separated by a blank line:

1. Standard library
2. Third-party packages
3. Local imports (`app.*`)

Ruff handles sorting automatically.

**All imports must be at module level.** Inline (deferred) imports inside functions, methods, or conditional blocks are **not allowed**.

The only acceptable exception is a **genuine circular import** that cannot be resolved by restructuring:

```python
# ✅ Correct — module-level imports
from app.core.config import app_logger
from app.infrastructure.messaging.publisher import publish_event

async def handle_event():
    await publish_event(queue, payload)

# ❌ Wrong — inline import with no circular-dependency justification
async def handle_event():
    from app.infrastructure.messaging.publisher import publish_event  # bad
    await publish_event(queue, payload)
```

The import-linter contracts in `pyproject.toml` enforce architectural boundaries:

```text
admin          → core, apps
infrastructure → core
apps           → core only
core           → nothing above it
```

| Contract | Rule |
| -------- | ---- |
| Core → Apps | Forbidden |
| Core → Infrastructure | Forbidden |
| Core → Admin | Forbidden |
| Apps → Infrastructure | Forbidden |
| Apps → Admin | Forbidden |
| Infrastructure → Admin | Forbidden |
| Admin → Infrastructure | Forbidden |

### Enum naming

All enums are in `app/core/enums.py`. Values use UPPER_SNAKE_CASE:

```python
class UserRole(str, Enum):
    ADMIN = "admin"
    USER = "user"
```

### Logging

The project uses a **centralised logging system** — never create ad-hoc loggers.

`app/core/logger.py` defines `setup_logger()`, which creates a `logging.Logger` with:

- **`RotatingFileHandler`** — writes to `logs/<component>.log` (5 MB, 3 backups)
- **`StreamHandler`** — mirrors to console
- **Sentry tag** — optional component label for filtering in Sentry

`app/core/config.py` instantiates domain-specific loggers:

| Logger | Use for |
| ------ | ------- |
| `app_logger` | Application lifecycle, startup/shutdown |
| `database_logger` | DB connections, migrations |
| `request_logger` | HTTP request handling in routers |
| `rabbitmq_logger` | RabbitMQ connections, consumers |
| `scheduler_logger` | APScheduler jobs |
| `auth_logger` | Authentication, OAuth, OTP |
| `redis_logger` | Redis connections, caching |

#### Logging rules

1. **Always import an existing logger** from `app.core.config`. Never use `logging.getLogger(__name__)`.
2. **Use f-string interpolation** with structured `key=value` pairs for context.
3. **Pick the correct severity:**
   - `debug` — verbose diagnostics (disabled in production)
   - `info` — happy-path milestones
   - `warning` — recoverable issues
   - `error` — failures that need attention (include the exception)
4. **Log at boundaries** — on entry, on success, and on error.
5. If none of the loggers fit, **add a new one** in `app/core/config.py`.

```python
# ✅ Correct
from app.core.config import auth_logger

async def send_otp(email: str) -> None:
    auth_logger.info(f"Sending OTP: email={email}")
    try:
        await send_email(email, code)
        auth_logger.info(f"OTP sent: email={email}")
    except Exception as e:
        auth_logger.error(f"OTP failed: email={email}, error={e}")
        raise

# ❌ Wrong
import logging
logger = logging.getLogger(__name__)
```

### Orchestration vs. responsibility

Every function or method should be either an **orchestrator** or an **actor** — never both.

| Role | Responsibility | Examples |
| ---- | -------------- | -------- |
| **Orchestrator** | Coordinates multiple steps by delegating to actors. Contains no low-level logic. | Router endpoints, service coordination methods |
| **Actor** | Performs a single, focused piece of work. Does not coordinate other actors. | CRUD methods, private helpers, publisher calls |

**If a function is doing its own low-level work _and_ coordinating other calls, split it** — extract the low-level work into a private helper (actor) and keep the parent as a pure orchestrator.

```python
# ✅ Orchestrator delegates, actors do focused work
async def create_workspace(self, session, user):
    slug, name = self._generate_identity(user)  # actor
    workspace = await workspace_db.create(session, ...)  # actor
    await member_db.create(session, ...)  # actor
    return workspace

def _generate_identity(self, user):  # actor — does ONE thing
    base = user.full_name or user.email.split("@")[0]
    return slugify(base), f"{base}'s Workspace"
```

### OpenAPI endpoint documentation

Every endpoint must have comprehensive OpenAPI documentation:

| Decorator param | Purpose | Guidelines |
| --------------- | ------- | ---------- |
| `summary` | Short label in docs UI | Imperative phrase, ≤ 10 words |
| `description` | Full Markdown documentation | Include Authorization, Request/Response tables, Errors |
| `responses` | Custom non-200 examples | Add when default error model isn't descriptive enough |

### Background job pattern

Offload non-critical work to RabbitMQ via the event publisher abstraction:

```python
from app.core.services.event_publisher import get_publisher

await get_publisher()("otp_emails", {"email": user.email, "otp": code})
```

The concrete publisher is registered at startup in `app/main.py`. Application code should never import directly from `app.infrastructure.messaging` — use `get_publisher()` instead.

Prefer queuing external service calls (email, notifications) via RabbitMQ when the response is not needed by the caller.
