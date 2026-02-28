# Copilot Instructions — FastAPI Project Style Guide

You are working on a **FastAPI project** that follows a strict layered architecture. Every file you create or modify must conform to these rules. When in doubt, look at the existing code in this repository as the canonical reference.

---

## Architecture Overview

```
app/
├── core/           # Shared kernel — no domain logic
├── apps/           # Domain modules (one folder per bounded context)
├── admin/          # SQLAdmin dashboard
├── infrastructure/ # External service integrations (messaging, scheduler)
└── main.py         # Composition root — wires all layers together
```

### Layer dependency rules (ENFORCED by import-linter)

```
core           → imports NOTHING from apps, admin, or infrastructure
apps/*         → imports ONLY from core
infrastructure → imports ONLY from core
admin          → imports from core and apps (never infrastructure)
main.py        → imports from ALL layers (it's the composition root)
```

**Violations will fail CI.** If you need shared types between apps, put them in `app/core/`.

---

## File Structure for a New App Module

When creating a new domain module, always use this exact structure:

```
app/apps/<app_name>/
├── __init__.py
├── db/
│   ├── models/
│   │   ├── __init__.py          # Re-exports all models
│   │   └── <entity>.py          # One model per file
│   └── crud/
│       ├── __init__.py          # Re-exports all CRUD singletons
│       └── <entity>.py          # BaseDB[T] subclass + singleton
├── schemas/
│   ├── __init__.py              # Re-exports all schemas
│   └── <entity>.py              # Pydantic v2 request/response models
└── routers/
    ├── __init__.py              # Re-exports all routers
    └── <entity>.py              # FastAPI APIRouter
```

After creating a new app:
1. Import its models in `app/main.py`: `import app.apps.<app_name>.db.models  # noqa: F401`
2. Mount its routers in `app/main.py`: `app.include_router(router, prefix="/api", tags=[...])`
3. Generate a migration: `python manage.py makemigrations "add <app_name> models"`

---

## ORM Models

All models inherit from `BaseModel` in `app/core/db/models/base.py`:

```python
from app.core.db.models.base import BaseModel
from sqlalchemy import String, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column

class MyEntity(BaseModel):
    __tablename__ = "my_entities"

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    owner_id: Mapped[UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
```

`BaseModel` provides: `id` (UUID pk), `is_deleted`, `deleted_at`, `created_at`, `updated_at`.

Rules:
- One model per file
- Use `Mapped[]` + `mapped_column()` (SQLAlchemy 2.0 style) — never use `Column()`
- Always set `__tablename__` explicitly
- Use `ForeignKey("table.column")` for relationships
- Re-export from the package `__init__.py`

---

## CRUD Layer

Every CRUD class inherits from `BaseDB[T]` and is instantiated as a **module-level singleton**:

```python
from app.core.db.crud.base import BaseDB
from app.apps.my_app.db.models import MyEntity

class MyEntityDB(BaseDB[MyEntity]):
    def __init__(self) -> None:
        super().__init__(model=MyEntity)

    # Add domain-specific queries as instance methods
    async def get_by_owner(self, session: AsyncSession, owner_id: UUID) -> list[MyEntity]:
        return await self.get_by_filters(session, {"owner_id": owner_id})

my_entity_db = MyEntityDB()
```

`BaseDB[T]` provides 20+ methods: `get_by_id`, `get_all` (keyset pagination), `get_by_filters`, `create`, `bulk_create`, `update`, `delete`, `soft_delete`, `upsert`, `get_or_create`, `exists`, etc.

Rules:
- Import the **singleton instance**, not the class: `from app.apps.my_app.db.crud import my_entity_db`
- Pass `commit_self=False` when inside a `session.begin()` block (let the transaction manager commit)
- Only use `commit_self=True` (default) for standalone operations

---

## Pydantic Schemas

```python
from pydantic import BaseModel, ConfigDict
from uuid import UUID
from datetime import datetime

class MyEntityCreate(BaseModel):
    name: str
    description: str | None = None

class MyEntityUpdate(BaseModel):
    name: str | None = None
    description: str | None = None

class MyEntityResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    description: str | None
    created_at: datetime
    updated_at: datetime
```

Rules:
- Always use Pydantic v2 (`model_config = ConfigDict(from_attributes=True)`)
- Separate Create, Update, and Response schemas
- Update schemas have all fields optional
- Response schemas include `id`, `created_at`, `updated_at`

---

## Routers

```python
from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_async_session, CurrentActiveUser
from app.core.exceptions.handlers import exception_schema
from app.core.exceptions.types import NotFoundException
from app.apps.my_app.db.crud import my_entity_db
from app.apps.my_app.schemas import MyEntityCreate, MyEntityResponse

router = APIRouter(prefix="/my-entities")

@router.post(
    "",
    response_model=MyEntityResponse,
    status_code=status.HTTP_201_CREATED,
    responses=exception_schema,
    summary="Create a new entity",
)
async def create_entity(
    body: MyEntityCreate,
    user: CurrentActiveUser,
    session: AsyncSession = Depends(get_async_session),
) -> MyEntityResponse:
    async with session.begin():
        entity = await my_entity_db.create(
            session,
            data={**body.model_dump(), "owner_id": user.id},
            commit_self=False,
        )
        return MyEntityResponse.model_validate(entity)
```

Rules:
- Use `responses=exception_schema` on every endpoint for consistent error docs
- **Writes**: wrap in `async with session.begin()`, pass `commit_self=False`
- **Reads**: call CRUD directly, no transaction block needed
- Use dependency-injected auth: `CurrentActiveUser`, `CurrentVerifiedUser`, `OptionalUser`
- Return Pydantic response models, never raw ORM objects

---

## Services

### SingletonService (stateful, initialised at startup)

```python
from app.core.services.base import SingletonService

class MyService(SingletonService):
    @classmethod
    def init(cls, api_key: str) -> None:
        cls._api_key = api_key
        cls._initialized = True

    @classmethod
    def do_work(cls) -> str:
        if not cls._initialized:
            raise RuntimeError("MyService not initialised")
        return cls._api_key
```

Initialise in the `lifespan` function in `app/main.py`.

### Event publishing (RabbitMQ)

Application code **never imports from `app.infrastructure.messaging` directly**. Use the publisher abstraction:

```python
from app.core.services.event_publisher import get_publisher

await get_publisher()("queue_name", {"key": "value"})
```

The concrete `publish_event` function is registered at startup via `register_publisher()`.

---

## Exception Handling

Use typed exceptions from `app.core.exceptions.types`:

```python
from app.core.exceptions.types import NotFoundException, ConflictException

# Raise with a message
raise NotFoundException("Item not found")

# Raise with details
raise ConflictException("Email already registered", details={"email": email})
```

Available exceptions: `AppException`, `AuthenticationException`, `ForbiddenException`, `NotFoundException`, `ConflictException`, `BadRequestException`, `DatabaseException`, `PaymentRequiredException`, `RateLimitExceededException`, `OTPExpiredException`, `OTPInvalidException`, `TooManyAttemptsException`, `OAuthException`, `NotImplementedException`.

Never use `HTTPException` directly — always use the typed exceptions.

---

## Dependencies (Auth)

```python
from app.core.dependencies import (
    CurrentUser,            # Any authenticated user
    CurrentActiveUser,      # Authenticated + is_active=True
    CurrentVerifiedUser,    # Authenticated + active + is_verified=True
    OptionalUser,           # None if no token, User if valid token
    InternalAPIKeyDep,      # X-Internal-API-Key header validation
)
```

Use these as type annotations in router parameters — they are `Annotated` types with `Depends()` built in.

---

## Logging

**Never create ad-hoc loggers.** Always import from `app.core.config`:

```python
from app.core.config import app_logger, auth_logger, request_logger  # etc.

auth_logger.info(f"Login attempt: email={email}")
auth_logger.error(f"Login failed: email={email}, error={e}")
```

Use f-string interpolation with `key=value` pairs. Pick the correct severity:
- `info` — happy-path milestones
- `warning` — recoverable issues
- `error` — failures (always include the exception)

If no existing logger fits, add a new one in `app/core/config.py` using `setup_logger()`.

---

## Import Rules

1. **All imports at module level.** No inline imports inside functions unless there's a documented circular dependency.
2. **Three groups**, separated by blank lines: stdlib → third-party → local (`app.*`)
3. **Register ORM models early** in `app/main.py` before any CRUD/dependency import
4. **Re-export from `__init__.py`** — every package should have clean re-exports

---

## Transaction Pattern

```python
# Writes — always use session.begin()
async with session.begin():
    entity = await entity_db.create(session, data=data, commit_self=False)
    await related_db.create(session, data=related_data, commit_self=False)
    # Auto-commits on success, auto-rolls back on exception

# Reads — no transaction block needed
entities = await entity_db.get_all(session)

# Infrastructure code (jobs, consumers) — create own session
from app.core.db import AsyncSessionLocal
async with AsyncSessionLocal.begin() as session:
    await entity_db.update(session, entity_id, data, commit_self=False)
```

---

## Testing

- Use `pytest` + `pytest-asyncio`
- Tests run against a real PostgreSQL database (Alembic migrations applied once per session)
- Each test runs in a rolled-back transaction for isolation
- Use fixtures from `tests/conftest.py`: `db_session`, `client`, `test_user`, `auth_headers`
- Group tests in classes: `class TestCreateItem:` / `class TestListItems:`
- Name methods: `test_<what>_<condition>_<expected>`

---

## Orchestration Rule

Every function is either an **orchestrator** or an **actor** — never both.

- **Orchestrator**: Coordinates multiple steps by delegating. Contains no low-level logic.
- **Actor**: Performs a single focused task. Does not coordinate other actors.

If a function does both, extract the low-level work into a private helper.

---

## Checklist for Any Change

- [ ] Follows the layer dependency rules (no upward imports)
- [ ] Uses `BaseDB[T]` for CRUD, not raw SQLAlchemy queries
- [ ] Uses typed exceptions, not `HTTPException`
- [ ] Uses domain-specific loggers from `app.core.config`
- [ ] All imports at module level
- [ ] Writes use `session.begin()` + `commit_self=False`
- [ ] Has tests
- [ ] Passes `python manage.py precommit`
