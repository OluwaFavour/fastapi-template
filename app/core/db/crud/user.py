"""Example CRUD class for User model. Add your domain CRUD classes here."""

from app.core.db.crud.base import BaseDB
from app.core.db.models.user import User


class UserDB(BaseDB[User]):
    """User-specific database operations.

    Extend with custom queries as needed, e.g.::

        async def get_by_email(self, session, email):
            return await self.get_one_by_filters(session, {"email": email})
    """

    pass


# Module-level singleton — import this in your services/routers.
user_db = UserDB(User)
