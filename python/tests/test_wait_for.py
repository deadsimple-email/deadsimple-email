"""Tests for messages.wait_for and extracted verification data."""
from __future__ import annotations

import httpx
import respx

from deadsimple import DeadSimple

API_KEY = "dse_test_key"
BASE = "https://api.deadsimple.email"


def _wrap(data):
    return {"data": data, "meta": {"timestamp": "2025-01-01T00:00:00Z", "request_id": "test"}}


def _msg(mid, subject="Verify", frm="noreply@acme.com"):
    return {
        "message_id": mid, "inbox_id": "inb_1", "thread_id": "t1", "direction": "inbound",
        "from_email": frm, "from_name": "", "to": ["a@x.com"], "cc": [], "subject": subject,
        "labels": [], "status": "received", "snippet": "", "attachments": [],
        "is_spam": False, "spam_score": 0, "created_at": "2026-07-08T00:00:00Z", "received_at": "",
    }


@respx.mock
def test_wait_for_returns_new_message_with_extracted():
    list_route = respx.get(url__regex=rf"{BASE}/v1/inboxes/inb_1/messages(\?.*)?$")
    list_route.side_effect = [
        httpx.Response(200, json=_wrap({"messages": [_msg("m1")], "count": 1})),           # baseline
        httpx.Response(200, json=_wrap({"messages": [_msg("m2"), _msg("m1")], "count": 2})),  # m2 is new
    ]
    full = {**_msg("m2"), "text_body": "Your code is 123456",
            "extracted": {"verification_code": "123456", "magic_link_url": "https://acme.com/v?t=abc"}}
    respx.get(url__regex=rf"{BASE}/v1/inboxes/inb_1/messages/m2$").mock(
        return_value=httpx.Response(200, json=_wrap(full)))

    with DeadSimple(API_KEY) as c:
        msg = c.messages.wait_for("inb_1", timeout=5, poll_interval=0)

    assert msg is not None
    assert msg.message_id == "m2"
    assert msg.extracted["verification_code"] == "123456"
    assert msg.extracted["magic_link_url"] == "https://acme.com/v?t=abc"


@respx.mock
def test_wait_for_times_out_when_no_new_message():
    respx.get(url__regex=rf"{BASE}/v1/inboxes/inb_1/messages(\?.*)?$").mock(
        return_value=httpx.Response(200, json=_wrap({"messages": [_msg("m1")], "count": 1})))

    with DeadSimple(API_KEY) as c:
        msg = c.messages.wait_for("inb_1", timeout=0.05, poll_interval=0)

    assert msg is None


@respx.mock
def test_wait_for_filters_by_sender():
    list_route = respx.get(url__regex=rf"{BASE}/v1/inboxes/inb_1/messages(\?.*)?$")
    list_route.side_effect = [
        httpx.Response(200, json=_wrap({"messages": [], "count": 0})),                       # baseline empty
        # a new email arrives but from the wrong sender -> ignored
        httpx.Response(200, json=_wrap({"messages": [_msg("spam", frm="other@evil.com")], "count": 1})),
        # then the wanted one arrives
        httpx.Response(200, json=_wrap({"messages": [_msg("m9", frm="noreply@acme.com"), _msg("spam", frm="other@evil.com")], "count": 2})),
    ]
    respx.get(url__regex=rf"{BASE}/v1/inboxes/inb_1/messages/m9$").mock(
        return_value=httpx.Response(200, json=_wrap(_msg("m9"))))

    with DeadSimple(API_KEY) as c:
        msg = c.messages.wait_for("inb_1", from_contains="acme.com", timeout=5, poll_interval=0)

    assert msg is not None
    assert msg.message_id == "m9"
