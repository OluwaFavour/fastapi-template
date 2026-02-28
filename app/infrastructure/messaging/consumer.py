import json
from typing import Callable, Any

import aio_pika

from app.core.config import rabbitmq_logger


async def process_message(
    message: aio_pika.IncomingMessage,
    handler: Callable[[dict[str, Any]], Any],
    channel: aio_pika.Channel,
    retry_queue: str | None = None,
    retry_queues: list[dict[str, Any]] | None = None,
    max_retries: int | None = None,
    dead_letter_queue: str | None = None,
) -> None:
    """Process a RabbitMQ message with retry and dead-letter support.

    Args:
        message: Incoming RabbitMQ message.
        handler: Async function to handle the message payload.
        channel: Channel for publishing retries/dead-letters.
        retry_queue: Single retry queue name (if applicable).
        retry_queues: List of retry queue configs [{name, ttl}] for staged retries.
        max_retries: Max attempts for single retry queue.
        dead_letter_queue: Queue for unrecoverable messages.
    """
    async with message.process(ignore_processed=True):
        try:
            event = json.loads(message.body.decode())
            await handler(event)
        except Exception as e:
            rabbitmq_logger.error(f"Error in handler: {e}")
            headers = dict(message.headers or {})
            attempt = int(headers.get("x-retry-attempt", 0))  # type: ignore[arg-type]
            next_queue: str | None = None

            # Multiple retry queues logic
            if retry_queues:
                if attempt < len(retry_queues):
                    next_queue = retry_queues[attempt]["name"]
                    rabbitmq_logger.info(f"Retrying message via {next_queue}")
            # Single retry queue logic
            elif retry_queue:
                if not max_retries or attempt < max_retries:
                    next_queue = retry_queue
                    rabbitmq_logger.info(f"Retrying message via {next_queue}")

            if next_queue:
                headers["x-retry-attempt"] = attempt + 1
                await channel.default_exchange.publish(
                    aio_pika.Message(
                        body=message.body,
                        delivery_mode=aio_pika.DeliveryMode.PERSISTENT,
                        headers=headers,
                    ),
                    routing_key=next_queue,
                )

            # Dead-letter logic
            elif dead_letter_queue:
                headers["x-error-message"] = str(e)
                if dead_letter_queue.endswith("_dead"):
                    headers["x-original-queue"] = dead_letter_queue[: -len("_dead")]

                await channel.default_exchange.publish(
                    aio_pika.Message(body=message.body, headers=headers),
                    routing_key=dead_letter_queue,
                )
                rabbitmq_logger.warning(f"Message dead-lettered to {dead_letter_queue}")

            await message.reject(requeue=False)
