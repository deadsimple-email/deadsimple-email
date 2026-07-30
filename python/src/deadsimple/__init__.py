"""Dead Simple Email — Python SDK for AI agents.

Usage::

    from deadsimple import DeadSimple

    client = DeadSimple("dse_your_api_key")
    inbox = client.inboxes.create(display_name="My Agent")
    client.messages.send(
        inbox_id=inbox.inbox_id,
        to="user@example.com",
        subject="Hello",
        text_body="Sent by an AI agent.",
    )

Async usage::

    from deadsimple import AsyncDeadSimple

    async with AsyncDeadSimple("dse_your_api_key") as client:
        inbox = await client.inboxes.create(display_name="My Agent")
"""

from deadsimple.client import AsyncDeadSimple, DeadSimple, WebSocketStream
from deadsimple.exceptions import (
    AuthenticationError,
    DeadSimpleError,
    NotFoundError,
    RateLimitError,
    ValidationError,
)
from deadsimple.types import WebhookEvent

__version__ = "0.1.1"
__all__ = [
    "DeadSimple",
    "AsyncDeadSimple",
    "WebSocketStream",
    "DeadSimpleError",
    "AuthenticationError",
    "NotFoundError",
    "RateLimitError",
    "ValidationError",
    "WebhookEvent",
]
