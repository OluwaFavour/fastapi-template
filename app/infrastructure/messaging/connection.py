import aio_pika

from app.core.config import settings

_connection: aio_pika.RobustConnection | None = None


async def get_connection() -> aio_pika.RobustConnection:
    """Get or create a robust connection to RabbitMQ."""
    global _connection
    if _connection is None or _connection.is_closed:
        _connection = await aio_pika.connect_robust(settings.RABBITMQ_URL)  # type: ignore[assignment]
    return _connection  # type: ignore[return-value]
