"""
Remote (Streamable HTTP) MCP transport.

The point of these tests is one property: when a single MCP server process
serves many callers over HTTP, each tool call must run with the credentials of
the caller that made *that* request. A regression here does not look like a
crash — it looks like one customer quietly reading another customer's inboxes.

Run:
    cd sdk/python && source .venv/bin/activate
    pytest tests/test_mcp_http.py -v
"""
from __future__ import annotations

import asyncio
import socket
import threading
from contextlib import closing

import httpx
import pytest
import uvicorn

from mcp import ClientSession
from mcp.client.streamable_http import streamable_http_client

import deadsimple.mcp as dse_mcp


# ---------------------------------------------------------------------------
# A fake SDK client that records which API key it was constructed with
# ---------------------------------------------------------------------------

class _FakeInboxes:
    def __init__(self, api_key: str):
        self._api_key = api_key

    def list(self, limit: int = 20, **kwargs):
        # Echo the key back through the tool result so the test can assert on it.
        class _Result:
            inboxes = [
                type("Inbox", (), {
                    "inbox_id": "inbox-for-" + self._api_key,
                    "email": f"{self._api_key}@box1.deadsimple.email",
                    "display_name": self._api_key,
                    "status": "active",
                    "created_at": "2026-07-27T00:00:00Z",
                    "tags": [],
                    "message_count": 0,
                })()
            ]
            next_cursor = None
            has_more = False
        return _Result()


class _FakeClient:
    def __init__(self, api_key: str, *args, **kwargs):
        self.api_key = api_key
        self.inboxes = _FakeInboxes(api_key)


@pytest.fixture(autouse=True)
def fake_sdk(monkeypatch):
    monkeypatch.setattr(dse_mcp, "DeadSimple", _FakeClient)
    dse_mcp._client_for.cache_clear()
    yield
    dse_mcp._client_for.cache_clear()


# ---------------------------------------------------------------------------
# A real uvicorn server on a real port — the task-dispatch behaviour we depend
# on cannot be verified by calling the ASGI app in-process.
# ---------------------------------------------------------------------------

def _free_port() -> int:
    with closing(socket.socket()) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


@pytest.fixture(scope="session")
def server():
    # Session-scoped on purpose: FastMCP's StreamableHTTPSessionManager refuses
    # to .run() twice on the same instance, and `mcp` is a module-level
    # singleton. One process therefore serves exactly one app — which is also
    # how it runs in production.
    port = _free_port()
    app = dse_mcp.http_app("streamable-http")
    config = uvicorn.Config(app, host="127.0.0.1", port=port, log_level="error")
    srv = uvicorn.Server(config)

    thread = threading.Thread(target=srv.run, daemon=True)
    thread.start()

    for _ in range(100):
        if srv.started:
            break
        threading.Event().wait(0.05)
    else:
        pytest.fail("uvicorn did not start")

    yield f"http://127.0.0.1:{port}/mcp"

    srv.should_exit = True
    thread.join(timeout=10)
    dse_mcp._http_mode = False


async def _call_list_inboxes(url: str, api_key: str | None):
    headers = {"Authorization": f"Bearer {api_key}"} if api_key else {}
    async with httpx.AsyncClient(headers=headers, timeout=30) as http_client:
        async with streamable_http_client(url, http_client=http_client) as (read, write, _):
            async with ClientSession(read, write) as session:
                await session.initialize()
                return await session.call_tool("list_inboxes", {"limit": 5})


def _text(result) -> str:
    return "".join(c.text for c in result.content if getattr(c, "type", None) == "text")


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

async def test_http_transport_serves_tool_calls(server):
    result = await _call_list_inboxes(server, "dse_alpha")

    assert not result.isError
    assert "dse_alpha" in _text(result)


async def test_two_callers_are_isolated(server):
    """The regression that matters: caller B must never see caller A's key."""
    alpha = _text(await _call_list_inboxes(server, "dse_alpha"))
    beta = _text(await _call_list_inboxes(server, "dse_beta"))

    assert "dse_alpha" in alpha and "dse_beta" not in alpha
    assert "dse_beta" in beta and "dse_alpha" not in beta


async def test_concurrent_callers_are_isolated(server):
    """Interleaved in-flight requests must not bleed credentials into each other."""
    keys = [f"dse_key{i}" for i in range(8)]
    results = await asyncio.gather(*(_call_list_inboxes(server, k) for k in keys))

    for key, result in zip(keys, results):
        body = _text(result)
        assert key in body
        for other in keys:
            if other != key:
                assert other not in body


async def test_missing_authorization_is_rejected(server):
    result = await _call_list_inboxes(server, None)

    assert result.isError
    assert "Authorization" in _text(result) or "API key" in _text(result)


async def test_env_key_is_never_used_over_http(server, monkeypatch):
    """DSE_API_KEY belongs to whoever runs the server, not to the caller."""
    monkeypatch.setenv("DSE_API_KEY", "dse_operator_key")

    result = await _call_list_inboxes(server, None)

    assert result.isError
    assert "dse_operator_key" not in _text(result)


def test_stdio_mode_still_uses_env_key(monkeypatch):
    """One process per caller, so the env var remains correct there."""
    monkeypatch.setattr(dse_mcp, "_http_mode", False)
    monkeypatch.setenv("DSE_API_KEY", "dse_stdio_key")

    assert dse_mcp._get_client().api_key == "dse_stdio_key"
