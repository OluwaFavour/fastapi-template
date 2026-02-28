from app.core.db.crud.base import BaseDB
from app.apps.example_app.db.models.item import Item


class ItemDB(BaseDB[Item]):
    """Item-specific database operations.

    Extend with custom queries as needed.
    """

    pass


item_db = ItemDB(Item)
