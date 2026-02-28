"""Queue configuration for message consumers.

Define your queues, retry policies, and handlers here.

Example entry::

    {
        "name": "email_notifications",
        "handler": handle_email_notification,
        "retry_queue": "email_notifications_retry",
        "retry_ttl": 30_000,  # 30 seconds
        "max_retries": 3,
        "dead_letter_queue": "email_notifications_dead",
    }
"""

from functools import lru_cache
from typing import Annotated, Any, Callable

from pydantic import BaseModel, Field, model_validator


class RetryQueue(BaseModel):
    name: Annotated[str, Field(description="Name of the retry queue")]
    ttl: Annotated[int, Field(gt=0, description="Time to live in milliseconds")]


class QueueConfig(BaseModel):
    name: Annotated[str, Field(description="Name of the main queue")]
    handler: Annotated[
        Callable[[dict[str, Any]], Any],
        Field(description="Function to handle messages from the queue"),
    ]
    retry_queue: Annotated[
        str | None, Field(description="Name of the retry queue (if single retry)")
    ] = None
    retry_queues: Annotated[
        list[RetryQueue] | None,
        Field(description="List of retry queues with TTLs (if multiple retries)"),
    ] = None
    retry_ttl: Annotated[
        int | None,
        Field(gt=0, description="Time to live in ms for single retry queue"),
    ] = None
    max_retries: Annotated[
        int | None,
        Field(gt=0, description="Maximum number of retries for single retry queue"),
    ] = None
    dead_letter_queue: Annotated[
        str | None, Field(description="Name of the dead letter queue")
    ] = None

    @model_validator(mode="before")
    @classmethod
    def check_retry_configuration(cls, values: dict[str, Any]) -> dict[str, Any]:
        retry_queue = values.get("retry_queue")
        retry_queues = values.get("retry_queues")
        retry_ttl = values.get("retry_ttl")

        if retry_queue and retry_queues:
            raise ValueError(
                "Specify either 'retry_queue' or 'retry_queues', not both."
            )
        if retry_queue and not retry_ttl:
            raise ValueError("'retry_ttl' must be set when using 'retry_queue'.")
        if retry_queues is not None and len(retry_queues) == 0:
            raise ValueError("'retry_queues' must contain at least one entry.")
        return values


# ---- Define your queue configs here ----
# Example (uncomment and adapt):
#
# async def handle_example(event: dict[str, Any]) -> None:
#     """Handle an example event."""
#     print(f"Received event: {event}")
#
# QUEUE_CONFIG: list[dict[str, Any]] = [
#     {
#         "name": "example_queue",
#         "handler": handle_example,
#         "retry_queue": "example_queue_retry",
#         "retry_ttl": 30_000,
#         "max_retries": 3,
#         "dead_letter_queue": "example_queue_dead",
#     },
# ]

QUEUE_CONFIG: list[dict[str, Any]] = []


@lru_cache
def get_queue_configs() -> tuple[QueueConfig, ...]:
    """Parse and validate queue configurations (cached)."""
    return tuple(QueueConfig(**config) for config in QUEUE_CONFIG)
