"""Tests for the Dead Simple Email SDK client."""

from __future__ import annotations

import json

import httpx
import pytest
import respx

from deadsimple import (
    AsyncDeadSimple,
    AuthenticationError,
    DeadSimple,
    NotFoundError,
    RateLimitError,
    ValidationError,
)
from deadsimple.types import Inbox, InboxList, MessageList, SendResult, Webhook
from deadsimple.webhooks import verify_signature

API_KEY = "dse_test_key"
BASE = "https://api.deadsimple.email"


def _wrap(data: dict | list | None = None) -> dict:
    """Wrap data in the standard API response envelope."""
    return {"data": data, "meta": {"timestamp": "2025-01-01T00:00:00Z", "request_id": "test"}}


# ── Client basics ─────────────────────────────────────────────────────────────


def test_missing_api_key():
    with pytest.raises(AuthenticationError, match="API key is required"):
        DeadSimple("")


def test_context_manager():
    with DeadSimple(API_KEY) as client:
        assert client._api_key == API_KEY


# ── Inboxes ───────────────────────────────────────────────────────────────────


@respx.mock
def test_create_inbox():
    inbox_data = {
        "inbox_id": "inb_123",
        "email": "abc@deadsimple.email",
        "local_part": "abc",
        "domain": "deadsimple.email",
        "display_name": "Test Bot",
        "tags": [],
        "status": "active",
        "message_count": 0,
        "created_at": "2025-01-01T00:00:00Z",
        "updated_at": "2025-01-01T00:00:00Z",
    }
    respx.post(f"{BASE}/v1/inboxes").mock(return_value=httpx.Response(201, json=_wrap(inbox_data)))

    client = DeadSimple(API_KEY)
    inbox = client.inboxes.create(display_name="Test Bot")
    assert isinstance(inbox, Inbox)
    assert inbox.inbox_id == "inb_123"
    assert inbox.email == "abc@deadsimple.email"
    assert inbox.display_name == "Test Bot"


@respx.mock
def test_list_inboxes():
    data = {"inboxes": [], "count": 0, "cursor": None}
    respx.get(f"{BASE}/v1/inboxes").mock(return_value=httpx.Response(200, json=_wrap(data)))

    client = DeadSimple(API_KEY)
    result = client.inboxes.list()
    assert isinstance(result, InboxList)
    assert result.count == 0


@respx.mock
def test_delete_inbox():
    respx.delete(f"{BASE}/v1/inboxes/inb_123").mock(return_value=httpx.Response(204))

    client = DeadSimple(API_KEY)
    client.inboxes.delete("inb_123")  # Should not raise


# ── Messages ──────────────────────────────────────────────────────────────────


@respx.mock
def test_send_message():
    send_data = {"message_id": "msg_456", "status": "sent"}
    respx.post(f"{BASE}/v1/inboxes/inb_123/messages").mock(return_value=httpx.Response(201, json=_wrap(send_data)))

    client = DeadSimple(API_KEY)
    result = client.messages.send(
        inbox_id="inb_123",
        to="user@example.com",
        subject="Test",
        text_body="Hello",
    )
    assert isinstance(result, SendResult)
    assert result.message_id == "msg_456"


@respx.mock
def test_send_to_string_coerced():
    """Passing `to` as a string should be coerced to a list."""
    send_data = {"message_id": "msg_789", "status": "sent"}
    route = respx.post(f"{BASE}/v1/inboxes/inb_123/messages").mock(
        return_value=httpx.Response(201, json=_wrap(send_data))
    )

    client = DeadSimple(API_KEY)
    client.messages.send(inbox_id="inb_123", to="single@example.com", subject="Test")
    body = json.loads(route.calls[0].request.content)
    assert body["to"] == ["single@example.com"]


@respx.mock
def test_list_messages():
    data = {"messages": [], "count": 0}
    respx.get(f"{BASE}/v1/inboxes/inb_123/messages").mock(return_value=httpx.Response(200, json=_wrap(data)))

    client = DeadSimple(API_KEY)
    result = client.messages.list("inb_123")
    assert isinstance(result, MessageList)


# ── Webhooks ──────────────────────────────────────────────────────────────────


@respx.mock
def test_create_webhook():
    wh_data = {
        "webhook_id": "wh_001",
        "url": "https://example.com/hook",
        "events": ["message.received"],
        "description": "",
        "is_active": True,
        "created_at": "2025-01-01T00:00:00Z",
        "signing_secret": "whsec_test",
    }
    respx.post(f"{BASE}/v1/webhooks").mock(return_value=httpx.Response(201, json=_wrap(wh_data)))

    client = DeadSimple(API_KEY)
    wh = client.webhooks.create(url="https://example.com/hook", events=["message.received"])
    assert isinstance(wh, Webhook)
    assert wh.signing_secret == "whsec_test"


# ── Error handling ────────────────────────────────────────────────────────────


@respx.mock
def test_not_found_error():
    error_body = {"error": {"message": "Inbox not found", "code": "not_found"}}
    respx.get(f"{BASE}/v1/inboxes/bad_id").mock(return_value=httpx.Response(404, json=error_body))

    client = DeadSimple(API_KEY)
    with pytest.raises(NotFoundError, match="Inbox not found"):
        client.inboxes.get("bad_id")


@respx.mock
def test_validation_error():
    error_body = {"error": {"message": "Invalid email", "code": "validation", "details": [{"field": "to", "message": "invalid"}]}}
    respx.post(f"{BASE}/v1/inboxes/inb_123/messages").mock(return_value=httpx.Response(400, json=error_body))

    client = DeadSimple(API_KEY)
    with pytest.raises(ValidationError, match="Invalid email") as exc_info:
        client.messages.send(inbox_id="inb_123", to="bad", subject="Test")
    assert exc_info.value.details[0]["field"] == "to"


@respx.mock
def test_rate_limit_error():
    error_body = {"error": {"message": "Too many requests", "code": "rate_limit"}}
    respx.get(f"{BASE}/v1/inboxes").mock(
        return_value=httpx.Response(429, json=error_body, headers={"Retry-After": "30"})
    )

    client = DeadSimple(API_KEY)
    with pytest.raises(RateLimitError) as exc_info:
        client.inboxes.list()
    assert exc_info.value.retry_after == 30


@respx.mock
def test_auth_error():
    error_body = {"error": {"message": "Invalid API key", "code": "unauthorized"}}
    respx.get(f"{BASE}/v1/inboxes").mock(return_value=httpx.Response(401, json=error_body))

    client = DeadSimple(API_KEY)
    with pytest.raises(AuthenticationError, match="Invalid API key"):
        client.inboxes.list()


# ── Idempotency ───────────────────────────────────────────────────────────────


@respx.mock
def test_idempotency_key_sent():
    inbox_data = {
        "inbox_id": "inb_idem",
        "email": "x@deadsimple.email",
        "local_part": "x",
        "domain": "deadsimple.email",
        "display_name": "",
        "tags": [],
        "status": "active",
        "message_count": 0,
        "created_at": "2025-01-01T00:00:00Z",
        "updated_at": "2025-01-01T00:00:00Z",
    }
    route = respx.post(f"{BASE}/v1/inboxes").mock(return_value=httpx.Response(201, json=_wrap(inbox_data)))

    client = DeadSimple(API_KEY)
    client.inboxes.create(idempotency_key="unique-key-123")
    assert route.calls[0].request.headers["Idempotency-Key"] == "unique-key-123"


# ── Webhook verification ─────────────────────────────────────────────────────


def test_webhook_verify_valid():
    import hashlib
    import hmac
    import time

    secret = "whsec_test_secret"
    payload = b'{"event": "message.received"}'
    ts = int(time.time())
    sig = hmac.new(secret.encode(), f"{ts}.".encode() + payload, hashlib.sha256).hexdigest()
    header = f"t={ts},v1={sig}"

    assert verify_signature(payload, header, secret) is True


def test_webhook_verify_invalid_signature():
    import time

    ts = int(time.time())
    header = f"t={ts},v1=badsig"

    with pytest.raises(ValidationError, match="Signature mismatch"):
        verify_signature(b"payload", header, "secret")


def test_webhook_verify_expired():
    import hashlib
    import hmac

    secret = "whsec_test"
    payload = b"payload"
    ts = 1000000  # Very old
    sig = hmac.new(secret.encode(), f"{ts}.".encode() + payload, hashlib.sha256).hexdigest()
    header = f"t={ts},v1={sig}"

    with pytest.raises(ValidationError, match="expired"):
        verify_signature(payload, header, secret, tolerance=60)


# ── Async client ──────────────────────────────────────────────────────────────


@pytest.mark.anyio
@respx.mock
async def test_async_create_inbox():
    inbox_data = {
        "inbox_id": "inb_async",
        "email": "async@deadsimple.email",
        "local_part": "async",
        "domain": "deadsimple.email",
        "display_name": "Async Bot",
        "tags": [],
        "status": "active",
        "message_count": 0,
        "created_at": "2025-01-01T00:00:00Z",
        "updated_at": "2025-01-01T00:00:00Z",
    }
    respx.post(f"{BASE}/v1/inboxes").mock(return_value=httpx.Response(201, json=_wrap(inbox_data)))

    async with AsyncDeadSimple(API_KEY) as client:
        inbox = await client.inboxes.create(display_name="Async Bot")
        assert isinstance(inbox, Inbox)
        assert inbox.inbox_id == "inb_async"


@pytest.mark.anyio
@respx.mock
async def test_async_send_message():
    send_data = {"message_id": "msg_async", "status": "sent"}
    respx.post(f"{BASE}/v1/inboxes/inb_123/messages").mock(return_value=httpx.Response(201, json=_wrap(send_data)))

    async with AsyncDeadSimple(API_KEY) as client:
        result = await client.messages.send(inbox_id="inb_123", to="user@example.com", subject="Async Test")
        assert result.message_id == "msg_async"
