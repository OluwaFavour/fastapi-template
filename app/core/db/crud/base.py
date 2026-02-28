from datetime import datetime, timezone
from typing import (
    Any,
    TypeVar,
    Generic,
    Type,
    Sequence,
    Callable,
)
from uuid import UUID

from sqlalchemy import (
    SQLColumnExpression,
    UnaryExpression,
    and_,
    or_,
    update as sa_update,
    delete as sa_delete,
)
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.sql.expression import asc, desc
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.sql import Select, Delete, Update

from app.core.exceptions.types import DatabaseException

T = TypeVar("T")


class BaseDB(Generic[T]):
    def __init__(self, model: Type[T]):
        self.model = model

    async def get_by_id(
        self, session: AsyncSession, id: UUID, options: list[Any] = []
    ) -> T | None:
        """
        Retrieve a model instance by its primary key.

        Args:
            session: The async database session.
            id: The primary key value.
            options: SQLAlchemy loader options (e.g. selectinload).

        Returns:
            The model instance if found, otherwise None.

        Raises:
            DatabaseException: If a database error occurs.
        """
        try:
            stmt: Select = (
                select(self.model)
                .options(*options)
                .where(getattr(self.model, "id") == id)
            )
            result = await session.execute(stmt)
            return result.scalar_one_or_none()
        except SQLAlchemyError as e:
            raise DatabaseException(
                f"Error retrieving {self.model.__name__} with ID {id}: {str(e)}"
            ) from e

    async def get_all(
        self,
        session: AsyncSession,
        filters: list[Any] | None = None,
        order_by: list[Any] | None = None,
        last_values: tuple | None = None,
        limit: int | None = None,
        options: list[Any] = [],
    ) -> Sequence[T]:
        """
        Retrieve paginated and filtered results using keyset pagination.

        Args:
            session: Async SQLAlchemy session.
            filters: Additional filters to apply.
            order_by: Columns/expressions to order by (must be deterministic).
            last_values: Last seen values for keyset pagination.
            limit: Max number of records to return.
            options: SQLAlchemy loader options.

        Returns:
            A sequence of model instances.
        """
        try:
            stmt = select(self.model).options(*options)

            if filters:
                stmt = stmt.filter(*filters)

            if order_by and last_values:
                assert len(order_by) == len(last_values), "Cursor length mismatch"
                keyset_conditions = []

                for i, col in enumerate(order_by):
                    if isinstance(col, UnaryExpression) and col.modifier == desc:
                        is_desc = True
                        base_col = col.element
                    elif isinstance(col, UnaryExpression) and col.modifier == asc:
                        is_desc = False
                        base_col = col.element
                    else:
                        is_desc = False
                        base_col = col

                    condition = tuple(
                        (
                            order_by[j].element
                            if isinstance(order_by[j], UnaryExpression)
                            else order_by[j]
                        )
                        == last_values[j]
                        for j in range(i)
                    )
                    prefix_match = and_(*condition) if condition else True

                    cmp = (
                        base_col < last_values[i]
                        if is_desc
                        else base_col > last_values[i]
                    )

                    keyset_conditions.append(and_(prefix_match, cmp))

                stmt = stmt.filter(or_(*keyset_conditions))

            if order_by:
                stmt = stmt.order_by(*order_by)

            if limit:
                stmt = stmt.limit(limit)

            result = await session.execute(stmt)
            return result.scalars().all()

        except SQLAlchemyError as e:
            raise DatabaseException(
                f"Error retrieving all {self.model.__name__} records: {str(e)}"
            ) from e

    async def get_by_filters(
        self,
        session: AsyncSession,
        filters: dict,
        order_by: list[SQLColumnExpression] | None = None,
        options: list[Any] = [],
    ) -> Sequence[T]:
        """
        Retrieve records matching the given keyword filters.

        Args:
            session: The async database session.
            filters: Keyword filter conditions.
            order_by: Ordering expressions.
            options: SQLAlchemy loader options.

        Returns:
            A sequence of matching model instances.

        Raises:
            DatabaseException: If a database error occurs.
        """
        try:
            stmt = (
                select(self.model)
                .options(*options)
                .filter_by(**filters)
                .order_by(*order_by)
                if order_by
                else select(self.model).options(*options).filter_by(**filters)
            )
            result = await session.execute(stmt)
            return result.scalars().all()
        except (SQLAlchemyError, ValueError) as e:
            raise DatabaseException(
                f"Error retrieving {self.model.__name__} with filters {filters}: {str(e)}"
            ) from e

    async def get_one_by_filters(
        self, session: AsyncSession, filters: dict, options: list[Any] = []
    ) -> T | None:
        """
        Retrieve a single record matching the given keyword filters.

        Args:
            session: The async database session.
            filters: Keyword filter conditions.
            options: SQLAlchemy loader options.

        Returns:
            The model instance if found, otherwise None.
        """
        try:
            stmt = select(self.model).options(*options).filter_by(**filters)
            result = await session.execute(stmt)
            return result.scalars().first()
        except (SQLAlchemyError, ValueError) as e:
            raise DatabaseException(
                f"Error retrieving one {self.model.__name__} with filters {filters}: {str(e)}"
            ) from e

    async def get_by_conditions(
        self,
        session: AsyncSession,
        conditions: Sequence[SQLColumnExpression],
        options: list[Any] = [],
    ) -> Sequence[T]:
        """
        Retrieve records matching SQLAlchemy column expressions.

        Args:
            session: The async database session.
            conditions: SQLAlchemy expressions to filter the query.
            options: SQLAlchemy loader options.

        Returns:
            A sequence of matching model instances.
        """
        try:
            stmt = select(self.model).options(*options).where(and_(*conditions))
            result = await session.execute(stmt)
            return result.scalars().all()
        except (SQLAlchemyError, ValueError) as e:
            raise DatabaseException(
                f"Error retrieving {self.model.__name__} with conditions {conditions}: {str(e)}"
            ) from e

    async def get_one_by_conditions(
        self,
        session: AsyncSession,
        conditions: Sequence[SQLColumnExpression],
        options: list[Any] = [],
    ) -> T | None:
        """
        Retrieve a single record matching SQLAlchemy column expressions.

        Args:
            session: The async database session.
            conditions: SQLAlchemy expressions to filter the query.
            options: SQLAlchemy loader options.

        Returns:
            The model instance if found, otherwise None.
        """
        try:
            stmt = select(self.model).options(*options).where(and_(*conditions))
            result = await session.execute(stmt)
            return result.scalars().first()
        except (SQLAlchemyError, ValueError) as e:
            raise DatabaseException(
                f"Error retrieving one {self.model.__name__} with conditions {conditions}: {str(e)}"
            ) from e

    async def create(
        self,
        session: AsyncSession,
        data: dict,
        validate: Callable[[dict], dict] | None = None,
        commit_self: bool = True,
    ) -> T:
        """
        Create and persist a new model instance.

        Args:
            session: The async database session.
            data: Fields and values for the new instance.
            validate: Optional callable to validate/transform data before creation.
            commit_self: If True, commits; if False, only flushes.

        Returns:
            The newly created model instance.
        """
        try:
            if validate:
                data = validate(data)

            obj = self.model(**data)
            session.add(obj)

            if commit_self:
                await session.commit()
            else:
                await session.flush()

            await session.refresh(obj)
            return obj
        except (SQLAlchemyError, ValueError) as e:
            raise DatabaseException(
                f"Error creating {self.model.__name__}: {str(e)}"
            ) from e

    async def bulk_create(
        self, session: AsyncSession, objects: list[T], commit_self: bool = True
    ) -> list[T]:
        """
        Create multiple model instances in bulk.

        Args:
            session: The async database session.
            objects: Model instances to create.
            commit_self: If True, commits; if False, only flushes.

        Returns:
            The list of created model instances.
        """
        try:
            session.add_all(objects)

            if commit_self:
                await session.commit()
            else:
                await session.flush()

            for obj in objects:
                await session.refresh(obj)
            return objects
        except (SQLAlchemyError, ValueError) as e:
            raise DatabaseException(
                f"Error creating {self.model.__name__} instances: {str(e)}"
            ) from e

    async def update(
        self, session: AsyncSession, id: UUID, updates: dict, commit_self: bool = True
    ) -> T | None:
        """
        Update a record by its primary key.

        Args:
            session: The async database session.
            id: The primary key of the record.
            updates: Fields and new values.
            commit_self: If True, commits; if False, only flushes.

        Returns:
            The updated record, or None if not found.
        """
        try:
            stmt: Update = (
                sa_update(self.model)
                .where(self.model.id == id)  # type: ignore[attr-defined]
                .values(**updates)
                .returning(self.model)
            )
            result = await session.execute(stmt)

            if commit_self:
                await session.commit()
            else:
                await session.flush()

            return result.scalar_one_or_none()
        except SQLAlchemyError as e:
            raise DatabaseException(
                f"Error updating {self.model.__name__} with ID {id}: {str(e)}"
            ) from e

    async def update_by_filters(
        self,
        session: AsyncSession,
        filters: dict,
        updates: dict,
        commit_self: bool = True,
    ) -> int:
        """
        Update records matching keyword filters.

        Args:
            session: The async database session.
            filters: Keyword filter conditions.
            updates: Fields and new values.
            commit_self: If True, commits; if False, only flushes.

        Returns:
            The number of records updated.
        """
        try:
            stmt: Update = (
                sa_update(self.model)
                .where(and_(*[getattr(self.model, k) == v for k, v in filters.items()]))
                .values(**updates)
            )
            result = await session.execute(stmt)

            if commit_self:
                await session.commit()
            else:
                await session.flush()

            return result.rowcount  # type: ignore[attr-defined]
        except SQLAlchemyError as e:
            raise DatabaseException(
                f"Error updating {self.model.__name__} with filters {filters}: {str(e)}"
            ) from e

    async def update_by_conditions(
        self,
        session: AsyncSession,
        conditions: list[SQLColumnExpression],
        updates: dict,
        commit_self: bool = True,
    ) -> int:
        """
        Update records matching SQLAlchemy column expressions.

        Args:
            session: The async database session.
            conditions: SQLAlchemy expressions to filter.
            updates: Fields and new values.
            commit_self: If True, commits; if False, only flushes.

        Returns:
            The number of records updated.
        """
        try:
            stmt: Update = (
                sa_update(self.model).where(and_(*conditions)).values(**updates)
            )
            result = await session.execute(stmt)

            if commit_self:
                await session.commit()
            else:
                await session.flush()

            return result.rowcount  # type: ignore[attr-defined]
        except SQLAlchemyError as e:
            raise DatabaseException(
                f"Error updating {self.model.__name__} with conditions {conditions}: {str(e)}"
            ) from e

    async def delete(
        self, session: AsyncSession, id: UUID, commit_self: bool = True
    ) -> bool:
        """
        Hard-delete a record by its primary key.

        Args:
            session: The async database session.
            id: The primary key of the record.
            commit_self: If True, commits; if False, only flushes.

        Returns:
            True if the deletion was executed.
        """
        try:
            stmt: Delete = sa_delete(self.model).where(self.model.id == id)  # type: ignore[attr-defined]
            await session.execute(stmt)

            if commit_self:
                await session.commit()
            else:
                await session.flush()

            return True
        except (SQLAlchemyError, ValueError) as e:
            raise DatabaseException(
                f"Error deleting {self.model.__name__} with ID {id}: {str(e)}"
            ) from e

    async def delete_by_filters(
        self, session: AsyncSession, filters: dict, commit_self: bool = True
    ) -> int:
        """
        Hard-delete records matching keyword filters.

        Args:
            session: The async database session.
            filters: Keyword filter conditions.
            commit_self: If True, commits; if False, only flushes.

        Returns:
            The number of records deleted.
        """
        try:
            stmt: Delete = sa_delete(self.model).where(
                and_(*[getattr(self.model, k) == v for k, v in filters.items()])
            )
            result = await session.execute(stmt)

            if commit_self:
                await session.commit()
            else:
                await session.flush()

            return result.rowcount  # type: ignore[attr-defined]
        except SQLAlchemyError as e:
            raise DatabaseException(
                f"Error deleting {self.model.__name__} with filters {filters}: {str(e)}"
            ) from e

    async def get_or_create(
        self,
        session: AsyncSession,
        defaults: dict,
        filters: dict,
        commit_self: bool = True,
    ) -> tuple[T, bool]:
        """
        Retrieve an existing record or create a new one.

        Args:
            session: The async database session.
            defaults: Default values to use when creating.
            filters: Filter conditions to locate an existing record.
            commit_self: Whether to commit after creation.

        Returns:
            A tuple of (instance, created) where created is True if new.
        """
        try:
            stmt = select(self.model).filter_by(**filters)
            result = await session.execute(stmt)
            instance = result.scalar_one_or_none()

            if instance:
                return instance, False

            return (
                await self.create(
                    session, {**filters, **defaults}, commit_self=commit_self
                ),
                True,
            )
        except (SQLAlchemyError, ValueError) as e:
            raise DatabaseException(
                f"Error getting or creating {self.model.__name__}: {str(e)}"
            ) from e

    async def upsert(
        self,
        session: AsyncSession,
        data: dict[str, Any],
        unique_fields: list[str],
        exclude_from_update: list[str] | None = None,
        commit_self: bool = True,
    ) -> tuple[T, bool]:
        """
        Upsert a record using PostgreSQL's INSERT ... ON CONFLICT ... DO UPDATE.

        Args:
            session: Database session.
            data: All fields to set on the record.
            unique_fields: Fields forming the unique constraint for conflict detection.
            exclude_from_update: Fields to exclude from updates on conflict.
            commit_self: Whether to commit after the operation.

        Returns:
            A tuple of (instance, created).

        Raises:
            DatabaseException: If a database error occurs.
            ValueError: If a unique_field is missing from data.
        """
        for field in unique_fields:
            if field not in data:
                raise ValueError(
                    f"Unique field '{field}' must be present in data for upsert"
                )

        try:
            default_exclude = {"id", "created_at", *unique_fields}
            if exclude_from_update:
                default_exclude.update(exclude_from_update)

            insert_data = {k: v for k, v in data.items() if k != "id"}

            now = datetime.now(timezone.utc)
            if hasattr(self.model, "created_at") and "created_at" not in insert_data:
                insert_data["created_at"] = now
            if hasattr(self.model, "updated_at") and "updated_at" not in insert_data:
                insert_data["updated_at"] = now
            if hasattr(self.model, "is_deleted") and "is_deleted" not in insert_data:
                insert_data["is_deleted"] = False

            update_set = {
                k: v for k, v in insert_data.items() if k not in default_exclude
            }
            if hasattr(self.model, "updated_at"):
                update_set["updated_at"] = now

            stmt = (
                pg_insert(self.model)
                .values(**insert_data)
                .on_conflict_do_update(
                    index_elements=unique_fields,
                    set_=update_set,
                )
                .returning(self.model)
            )

            result = await session.execute(stmt)
            instance = result.scalar_one()

            if commit_self:
                await session.commit()
            else:
                await session.flush()

            await session.refresh(instance)

            created = False
            if hasattr(instance, "created_at") and hasattr(instance, "updated_at"):
                created_at = getattr(instance, "created_at")
                updated_at = getattr(instance, "updated_at")
                if created_at and updated_at:
                    created = created_at == updated_at

            return instance, created

        except SQLAlchemyError as e:
            raise DatabaseException(
                f"Error upserting {self.model.__name__}: {str(e)}"
            ) from e

    async def exists(self, session: AsyncSession, filters: dict) -> bool:
        """
        Check if a record matching the filters exists.

        Args:
            session: The async database session.
            filters: Keyword filter conditions.

        Returns:
            True if a matching record exists.
        """
        try:
            stmt = select(self.model).filter_by(**filters)
            result = await session.execute(stmt)
            return result.scalars().first() is not None
        except (SQLAlchemyError, ValueError) as e:
            raise DatabaseException(
                f"Error checking existence of {self.model.__name__} with filters {filters}: {str(e)}"
            ) from e

    async def soft_delete(
        self, session: AsyncSession, id: UUID, commit_self: bool = True
    ) -> T | None:
        """
        Soft-delete a record by setting ``is_deleted=True`` and ``deleted_at``.

        Args:
            session: The async database session.
            id: The primary key of the record.
            commit_self: If True, commits; if False, only flushes.

        Returns:
            The soft-deleted record, or None if not found.
        """
        try:
            now = datetime.now(timezone.utc)
            stmt: Update = (
                sa_update(self.model)
                .where(self.model.id == id)  # type: ignore[attr-defined]
                .values(is_deleted=True, deleted_at=now, updated_at=now)
                .returning(self.model)
            )
            result = await session.execute(stmt)

            if commit_self:
                await session.commit()
            else:
                await session.flush()

            return result.scalar_one_or_none()
        except SQLAlchemyError as e:
            raise DatabaseException(
                f"Error soft-deleting {self.model.__name__} with ID {id}: {str(e)}"
            ) from e

    async def soft_delete_by_filters(
        self, session: AsyncSession, filters: dict, commit_self: bool = True
    ) -> int:
        """
        Soft-delete records matching keyword filters.

        Args:
            session: The async database session.
            filters: Keyword filter conditions.
            commit_self: If True, commits; if False, only flushes.

        Returns:
            The number of records soft-deleted.
        """
        try:
            now = datetime.now(timezone.utc)
            stmt: Update = (
                sa_update(self.model)
                .where(and_(*[getattr(self.model, k) == v for k, v in filters.items()]))
                .values(is_deleted=True, deleted_at=now, updated_at=now)
            )
            result = await session.execute(stmt)

            if commit_self:
                await session.commit()
            else:
                await session.flush()

            return result.rowcount  # type: ignore[attr-defined]
        except SQLAlchemyError as e:
            raise DatabaseException(
                f"Error soft-deleting {self.model.__name__} with filters {filters}: {str(e)}"
            ) from e

    async def soft_delete_by_conditions(
        self,
        session: AsyncSession,
        conditions: list[SQLColumnExpression],
        commit_self: bool = True,
    ) -> int:
        """
        Soft-delete records matching SQLAlchemy column expressions.

        Args:
            session: The async database session.
            conditions: SQLAlchemy expressions to filter.
            commit_self: If True, commits; if False, only flushes.

        Returns:
            The number of records soft-deleted.
        """
        try:
            now = datetime.now(timezone.utc)
            stmt: Update = (
                sa_update(self.model)
                .where(and_(*conditions))
                .values(is_deleted=True, deleted_at=now, updated_at=now)
            )
            result = await session.execute(stmt)

            if commit_self:
                await session.commit()
            else:
                await session.flush()

            return result.rowcount  # type: ignore[attr-defined]
        except SQLAlchemyError as e:
            raise DatabaseException(
                f"Error soft-deleting {self.model.__name__} with conditions {conditions}: {str(e)}"
            ) from e

    async def permanently_delete_soft_deleted(
        self,
        session: AsyncSession,
        cutoff_date: datetime,
        commit_self: bool = True,
    ) -> int:
        """
        Hard-delete records that were soft-deleted before the cutoff date.

        Used for cleanup of soft-deleted records after a retention period.

        Args:
            session: The async database session.
            cutoff_date: Records soft-deleted before this date will be removed.
            commit_self: If True, commits; if False, only flushes.

        Returns:
            The number of records permanently deleted.
        """
        try:
            if not hasattr(self.model, "is_deleted") or not hasattr(
                self.model, "deleted_at"
            ):
                return 0

            is_deleted_col = getattr(self.model, "is_deleted")
            deleted_at_col = getattr(self.model, "deleted_at")

            stmt: Delete = sa_delete(self.model).where(
                and_(
                    is_deleted_col == True,  # noqa: E712
                    deleted_at_col < cutoff_date,
                )
            )
            result = await session.execute(stmt)

            if commit_self:
                await session.commit()
            else:
                await session.flush()

            return result.rowcount  # type: ignore[attr-defined]
        except SQLAlchemyError as e:
            raise DatabaseException(
                f"Error permanently deleting soft-deleted {self.model.__name__} records: {str(e)}"
            ) from e
