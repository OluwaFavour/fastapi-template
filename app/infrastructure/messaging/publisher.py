import json
from typing import Any

import aio_pika

from app.infrastructure.messaging.connection import get_connection


async def publish_event(
    queue_name: str, event: dict[str, Any], headers: dict[str, Any] = {}
) -> None:
    """Publish a persistent JSON event to the specified RabbitMQ queue."""
    connection = await get_connection()
    channel = await connection.channel()
    await channel.declare_queue(queue_name, durable=True)

    message = aio_pika.Message(
        body=json.dumps(event).encode(),
        headers=headers,
        content_type="application/json",
        delivery_mode=aio_pika.DeliveryMode.PERSISTENT,
    )

    await channel.default_exchange.publish(message, routing_key=queue_name)
