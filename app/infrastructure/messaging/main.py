"""Messaging worker — starts RabbitMQ consumers.

Standalone usage::

    python -m app.infrastructure.messaging.main

Docker::

    docker compose --profile worker-only up -d
"""

import asyncio
import signal
from functools import partial

import aio_pika

from app.infrastructure.messaging.connection import get_connection
from app.infrastructure.messaging.consumer import process_message
from app.infrastructure.messaging.queues import get_queue_configs
from app.core.config import rabbitmq_logger, settings
from app.core.db import init_db, dispose_db


async def start_consumers(keep_alive: bool) -> aio_pika.RobustConnection | None:
    """Start message consumers for all configured queues.

    Args:
        keep_alive: If True, blocks forever. If False, returns the connection
                    so the caller can manage the lifecycle.
    """
    conn = await get_connection()
    channel = await conn.channel()
    await channel.set_qos(prefetch_count=10)

    queue_configs = get_queue_configs()
    for q in queue_configs:
        queue = await channel.declare_queue(q.name, durable=True)

        # Single retry queue setup
        if retry := q.retry_queue:
            await channel.declare_queue(
                retry,
                durable=True,
                arguments={
                    "x-message-ttl": q.retry_ttl,
                    "x-dead-letter-exchange": "",
                    "x-dead-letter-routing-key": q.name,
                },
            )

        # Multiple retry queues setup
        if retries := q.retry_queues:
            for rq in retries:
                await channel.declare_queue(
                    rq.name,
                    durable=True,
                    arguments={
                        "x-message-ttl": rq.ttl,
                        "x-dead-letter-exchange": "",
                        "x-dead-letter-routing-key": q.name,
                    },
                )

        # Dead-letter queue setup
        if dead := q.dead_letter_queue:
            await channel.declare_queue(dead, durable=True)

        # Register consumer
        await queue.consume(  # type: ignore[arg-type]
            partial(
                process_message,
                handler=q.handler,
                channel=channel,  # type: ignore[arg-type]
                retry_queue=q.retry_queue,
                retry_queues=(
                    [rq.model_dump() for rq in q.retry_queues]
                    if q.retry_queues
                    else None
                ),
                max_retries=q.max_retries,
                dead_letter_queue=q.dead_letter_queue,
            ),
            no_ack=False,
        )

    rabbitmq_logger.info("Consumers started. Waiting for messages...")

    if keep_alive:
        try:
            await asyncio.Future()
        finally:
            await conn.close()
    else:
        return conn


async def main() -> None:
    """Main entry point for standalone message consumer execution."""
    shutdown_event = asyncio.Event()
    conn: aio_pika.RobustConnection | None = None

    def handle_shutdown(signum, frame):
        rabbitmq_logger.info(f"Received signal {signum}, initiating shutdown...")
        shutdown_event.set()

    signal.signal(signal.SIGINT, handle_shutdown)
    signal.signal(signal.SIGTERM, handle_shutdown)

    rabbitmq_logger.info("Starting standalone message consumer...")

    try:
        await init_db()
        # TODO: Initialize additional services (Redis, email, etc.) as needed.

        conn = await start_consumers(keep_alive=False)
        rabbitmq_logger.info("Message consumers started. Waiting for messages...")
        await shutdown_event.wait()

    except Exception as e:
        rabbitmq_logger.exception(f"Messaging error: {e}")
        raise

    finally:
        rabbitmq_logger.info("Shutting down message consumer...")
        if conn:
            await conn.close()
        await dispose_db()
        rabbitmq_logger.info("Message consumer shutdown complete.")


if __name__ == "__main__":
    asyncio.run(main())
