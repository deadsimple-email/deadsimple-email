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


@respx.mock
def test_create_webhook_sends_custom_headers():
    """Custom headers ride the request body and come back masked."""
    route = respx.post(f"{BASE}/v1/webhooks").mock(
        return_value=httpx.Response(201, json=_wrap({
            "webhook_id": "wh_002",
            "url": "https://example.com/hook",
            "events": ["message.received"],
            "description": "",
            "is_active": True,
            "created_at": "2025-01-01T00:00:00Z",
            "headers": {"Authorization": "***3456"},
        }))
    )

    client = DeadSimple(API_KEY)
    wh = client.webhooks.create(
        url="https://example.com/hook",
        events=["message.received"],
        headers={"Authorization": "Bearer tok_abcdef123456"},
    )

    sent = json.loads(route.calls[0].request.content)
    assert sent["headers"] == {"Authorization": "Bearer tok_abcdef123456"}
    assert wh.headers == {"Authorization": "***3456"}


@respx.mock
def test_create_webhook_omits_headers_when_unset():
    respx.post(f"{BASE}/v1/webhooks").mock(
        return_value=httpx.Response(201, json=_wrap({
            "webhook_id": "wh_003",
            "url": "https://example.com/hook",
            "events": ["message.received"],
            "description": "",
            "is_active": True,
            "created_at": "2025-01-01T00:00:00Z",
        }))
    )
    route = respx.routes[0]

    client = DeadSimple(API_KEY)
    wh = client.webhooks.create(url="https://example.com/hook", events=["message.received"])

    assert "headers" not in json.loads(route.calls[0].request.content)
    assert wh.headers == {}


@respx.mock
def test_get_and_set_webhook_headers():
    respx.get(f"{BASE}/v1/webhooks/wh_001/headers").mock(
        return_value=httpx.Response(200, json=_wrap(
            {"webhook_id": "wh_001", "headers": {"Authorization": "***3456"}}))
    )
    put = respx.put(f"{BASE}/v1/webhooks/wh_001/headers").mock(
        return_value=httpx.Response(200, json=_wrap(
            {"webhook_id": "wh_001", "headers": {"Authorization": "***9999"}}))
    )

    client = DeadSimple(API_KEY)
    assert client.webhooks.get_headers("wh_001") == {"Authorization": "***3456"}

    result = client.webhooks.set_headers("wh_001", {"Authorization": "Bearer rotated_9999"})
    assert json.loads(put.calls[0].request.content) == {
        "headers": {"Authorization": "Bearer rotated_9999"}
    }
    assert result == {"Authorization": "***9999"}


@respx.mock
def test_clearing_webhook_headers_sends_empty_map():
    put = respx.put(f"{BASE}/v1/webhooks/wh_001/headers").mock(
        return_value=httpx.Response(200, json=_wrap({"webhook_id": "wh_001", "headers": {}}))
    )

    client = DeadSimple(API_KEY)
    assert client.webhooks.set_headers("wh_001", {}) == {}
    assert json.loads(put.calls[0].request.content) == {"headers": {}}


@respx.mock
@pytest.mark.asyncio
async def test_async_webhook_headers():
    respx.post(f"{BASE}/v1/webhooks").mock(
        return_value=httpx.Response(201, json=_wrap({
            "webhook_id": "wh_004",
            "url": "https://example.com/hook",
            "events": ["message.received"],
            "description": "",
            "is_active": True,
            "created_at": "2025-01-01T00:00:00Z",
            "headers": {"Authorization": "***3456"},
        }))
    )
    put = respx.put(f"{BASE}/v1/webhooks/wh_004/headers").mock(
        return_value=httpx.Response(200, json=_wrap(
            {"webhook_id": "wh_004", "headers": {"X-Tenant": "***"}}))
    )

    async with AsyncDeadSimple(API_KEY) as client:
        wh = await client.webhooks.create(
            url="https://example.com/hook",
            events=["message.received"],
            headers={"Authorization": "Bearer tok_abcdef123456"},
        )
        assert wh.headers == {"Authorization": "***3456"}
        assert await client.webhooks.set_headers("wh_004", {"X-Tenant": "ksred"}) == {
            "X-Tenant": "***"
        }

    assert json.loads(put.calls[0].request.content) == {"headers": {"X-Tenant": "ksred"}}


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


# ── Outbound attachments / inline images ─────────────────────────────────────


@respx.mock
def test_send_uploads_images_and_marks_them_inline(tmp_path):
    """images= should upload out-of-band and render in the body."""
    img = tmp_path / "door.jpg"
    img.write_bytes(b"\xff\xd8\xff\xe0jpegbytes")

    respx.post(f"{BASE}/v1/attachments").mock(return_value=httpx.Response(
        201, json=_wrap({"attachment_id": "att_1", "upload_url": "https://s3.example/put"})))
    put = respx.put("https://s3.example/put").mock(return_value=httpx.Response(200))
    send = respx.post(f"{BASE}/v1/inboxes/inb_1/messages").mock(
        return_value=httpx.Response(201, json=_wrap(
            {"message_id": "m1", "status": "sent", "to": ["a@b.com"], "subject": "s"})))

    client = DeadSimple(API_KEY)
    client.messages.send(inbox_id="inb_1", to="a@b.com", subject="Photos",
                         text_body="see below", images=[str(img)])

    assert put.called, "bytes must go to storage, not through the send request"
    body = json.loads(send.calls[0].request.content)
    assert body["attachments"] == [{"attachment_id": "att_1", "inline": True}]


@respx.mock
def test_send_attachments_are_not_inline(tmp_path):
    doc = tmp_path / "quote.pdf"
    doc.write_bytes(b"%PDF-1.4")
    respx.post(f"{BASE}/v1/attachments").mock(return_value=httpx.Response(
        201, json=_wrap({"attachment_id": "att_2", "upload_url": "https://s3.example/put2"})))
    respx.put("https://s3.example/put2").mock(return_value=httpx.Response(200))
    send = respx.post(f"{BASE}/v1/inboxes/inb_1/messages").mock(
        return_value=httpx.Response(201, json=_wrap(
            {"message_id": "m2", "status": "sent", "to": ["a@b.com"], "subject": "s"})))

    DeadSimple(API_KEY).messages.send(inbox_id="inb_1", to="a@b.com", subject="Quote",
                                      text_body="attached", attachments=[str(doc)])
    body = json.loads(send.calls[0].request.content)
    assert body["attachments"] == [{"attachment_id": "att_2"}]


@respx.mock
def test_send_without_attachments_sends_no_key():
    send = respx.post(f"{BASE}/v1/inboxes/inb_1/messages").mock(
        return_value=httpx.Response(201, json=_wrap(
            {"message_id": "m3", "status": "sent", "to": ["a@b.com"], "subject": "s"})))
    DeadSimple(API_KEY).messages.send(inbox_id="inb_1", to="a@b.com", subject="s", text_body="t")
    assert "attachments" not in json.loads(send.calls[0].request.content)


def test_url_fetch_refuses_internal_addresses():
    """The same helper runs inside the hosted MCP, where URLs are agent-supplied."""
    from deadsimple.client import _fetch_url_bytes
    from deadsimple.exceptions import ValidationError

    for url in ("http://169.254.169.254/latest/meta-data/",
                "http://localhost:8080/admin",
                "http://127.0.0.1/secrets"):
        with pytest.raises(ValidationError):
            _fetch_url_bytes(url)


def test_missing_file_gives_a_clear_error():
    from deadsimple.client import _read_source
    from deadsimple.exceptions import ValidationError
    with pytest.raises(ValidationError) as exc:
        _read_source("/nope/does-not-exist.jpg")
    assert "not a readable file" in str(exc.value)


@respx.mock
def test_reply_supports_images(tmp_path):
    """He asked for images on reply, not just send."""
    img = tmp_path / "p.jpg"
    img.write_bytes(b"\xff\xd8\xffjpeg")
    respx.post(f"{BASE}/v1/attachments").mock(return_value=httpx.Response(
        201, json=_wrap({"attachment_id": "att_r", "upload_url": "https://s3.example/r"})))
    respx.put("https://s3.example/r").mock(return_value=httpx.Response(200))
    reply = respx.post(f"{BASE}/v1/inboxes/inb_1/messages/m_1/reply").mock(
        return_value=httpx.Response(201, json=_wrap({"message_id": "m2", "status": "sent"})))

    DeadSimple(API_KEY).messages.reply("inb_1", "m_1", text_body="see photo",
                                       images=[str(img)])
    body = json.loads(reply.calls[0].request.content)
    assert body["attachments"] == [{"attachment_id": "att_r", "inline": True}]


def test_google_drive_share_link_is_rewritten():
    """A /view link serves an HTML viewer, not the file."""
    from deadsimple.client import _direct_download_url
    assert _direct_download_url("https://drive.google.com/file/d/ABC123/view?usp=sharing") == \
        "https://drive.google.com/uc?export=download&id=ABC123"
    assert _direct_download_url("https://drive.google.com/open?id=XYZ") == \
        "https://drive.google.com/uc?export=download&id=XYZ"
    assert _direct_download_url("https://example.com/a.jpg") == "https://example.com/a.jpg"


@respx.mock
def test_html_response_is_not_attached_as_an_image():
    """A Drive link without link-sharing returns a login page; say so."""
    from deadsimple.client import _fetch_url_bytes
    from deadsimple.exceptions import ValidationError

    respx.get("https://drive.google.com/uc?export=download&id=ABC").mock(
        return_value=httpx.Response(200, html="<html>Sign in</html>"))
    with pytest.raises(ValidationError) as exc:
        _fetch_url_bytes("https://drive.google.com/file/d/ABC/view", expect_image=True)
    assert "anyone with the link" in str(exc.value)


@respx.mock
def test_real_image_url_passes_the_check():
    from deadsimple.client import _fetch_url_bytes
    respx.get("https://example.com/photo.jpg").mock(
        return_value=httpx.Response(200, content=b"\xff\xd8\xffdata",
                                    headers={"content-type": "image/jpeg"}))
    data, name, ctype = _fetch_url_bytes("https://example.com/photo.jpg", expect_image=True)
    assert ctype == "image/jpeg" and name == "photo.jpg"


# ── Calendar invites ─────────────────────────────────────────────────────────
# An attached .ics is a file, not an invitation. These cover the argument
# reaching the API and the uid coming back, which is what a later reschedule
# or cancellation is matched on.


@respx.mock
def test_send_passes_the_calendar_invite_through():
    send = respx.post(f"{BASE}/v1/inboxes/inb_1/messages").mock(
        return_value=httpx.Response(201, json=_wrap(
            {"message_id": "m4", "status": "sent", "calendar_uid": "u1@deadsimple.email"})))

    result = DeadSimple(API_KEY).messages.send(
        inbox_id="inb_1", to="t@x.com", subject="Roof inspection",
        text_body="Tuesday at 3.",
        calendar_invite={"title": "Roof inspection", "start": "2026-09-15T15:00:00Z",
                         "duration_minutes": 45},
    )

    body = json.loads(send.calls[0].request.content)
    assert body["calendar_invite"]["title"] == "Roof inspection"
    assert body["calendar_invite"]["start"] == "2026-09-15T15:00:00Z"
    # Without the uid the agent cannot change the meeting it just booked.
    assert result.calendar_uid == "u1@deadsimple.email"


@respx.mock
def test_send_without_an_invite_sends_no_key():
    send = respx.post(f"{BASE}/v1/inboxes/inb_1/messages").mock(
        return_value=httpx.Response(201, json=_wrap({"message_id": "m5", "status": "sent"})))
    DeadSimple(API_KEY).messages.send(inbox_id="inb_1", to="a@b.com", subject="s", text_body="t")
    assert "calendar_invite" not in json.loads(send.calls[0].request.content)
    

@respx.mock
def test_reply_can_carry_an_invite():
    """Agreeing a time mid-thread and inviting is one message, not two."""
    reply = respx.post(f"{BASE}/v1/inboxes/inb_1/messages/m1/reply").mock(
        return_value=httpx.Response(201, json=_wrap(
            {"message_id": "m6", "status": "sent", "calendar_uid": "u2@deadsimple.email"})))

    DeadSimple(API_KEY).messages.reply(
        inbox_id="inb_1", message_id="m1", text_body="Tuesday works.",
        calendar_invite={"title": "Site visit", "start": "2026-09-15T15:00:00Z"},
    )
    assert json.loads(reply.calls[0].request.content)["calendar_invite"]["title"] == "Site visit"


@respx.mock
def test_send_result_without_a_uid_is_empty_not_missing():
    respx.post(f"{BASE}/v1/inboxes/inb_1/messages").mock(
        return_value=httpx.Response(201, json=_wrap({"message_id": "m7", "status": "sent"})))
    result = DeadSimple(API_KEY).messages.send(inbox_id="inb_1", to="a@b.com",
                                               subject="s", text_body="t")
    assert result.calendar_uid == ""
