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
import json
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
        # mcp 1.x yields (read, write, get_session_id); 2.x drops the session id.
        async with streamable_http_client(url, http_client=http_client) as streams:
            read, write = streams[0], streams[1]
            async with ClientSession(read, write) as session:
                await session.initialize()
                return await session.call_tool("list_inboxes", {"limit": 5})


def _is_error(result) -> bool:
    """mcp 2.x renamed the attribute to snake_case; the wire field is unchanged."""
    return bool(getattr(result, "is_error", getattr(result, "isError", False)))


def _text(result) -> str:
    return "".join(c.text for c in result.content if getattr(c, "type", None) == "text")


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

async def test_http_transport_serves_tool_calls(server):
    result = await _call_list_inboxes(server, "dse_alpha")

    assert not _is_error(result)
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

    assert _is_error(result)
    assert "Authorization" in _text(result) or "API key" in _text(result)


async def test_env_key_is_never_used_over_http(server, monkeypatch):
    """DSE_API_KEY belongs to whoever runs the server, not to the caller."""
    monkeypatch.setenv("DSE_API_KEY", "dse_operator_key")

    result = await _call_list_inboxes(server, None)

    assert _is_error(result)
    assert "dse_operator_key" not in _text(result)


def test_stdio_mode_still_uses_env_key(monkeypatch):
    """One process per caller, so the env var remains correct there."""
    monkeypatch.setattr(dse_mcp, "_http_mode", False)
    monkeypatch.setenv("DSE_API_KEY", "dse_stdio_key")

    assert dse_mcp._get_client().api_key == "dse_stdio_key"


def test_get_calendar_feed_returns_subscribe_urls(monkeypatch):
    """The feed URL was reachable only through the REST API: an agent on MCP
    could list and create events but never hand a person the subscription."""
    calls = []

    class _Cal:
        def feed(self, inbox_id):
            calls.append(inbox_id)
            return {"inbox_id": inbox_id, "email": "bot@deadsimplemail.com",
                    "feed_url": f"https://api.deadsimple.email/v1/inboxes/{inbox_id}/calendar.ics?token=t",
                    "webcal_url": f"webcal://api.deadsimple.email/v1/inboxes/{inbox_id}/calendar.ics?token=t"}

    class _Client:
        calendar = _Cal()

    monkeypatch.setattr(dse_mcp, "_get_client", lambda: _Client())
    out = json.loads(dse_mcp.get_calendar_feed("ib-1"))
    assert calls == ["ib-1"]
    assert out["webcal_url"].startswith("webcal://")
    assert out["feed_url"].startswith("https://")


class _Att:
    def __init__(self, attachment_id, filename, content_type, size, extracted_text=""):
        self.attachment_id, self.filename, self.content_type = attachment_id, filename, content_type
        self.size, self.extracted_text = size, extracted_text


class _Msg:
    def __init__(self, attachments):
        self.message_id, self.direction, self.from_name, self.from_email = "m1", "inbound", "", "a@b.c"
        self.to, self.cc, self.subject = ["x@y.z"], [], "Invoice"
        self.latest_reply = self.text_body = "see attached"
        self.html_body, self.created_at, self.received_at = "", "2026-09-30", ""
        self.injection_risk, self.attachments = "", attachments


def _attachment_client(monkeypatch, attachments, image_bytes=b""):
    class _Messages:
        def get(self, inbox_id, message_id):
            return _Msg(attachments)

    class _Link:
        url, expires_in = "https://files.example/signed", 3600

    class _Attachments:
        def get_url(self, inbox_id, message_id, attachment_id):
            return _Link()

    class _Client:
        messages, attachments = _Messages(), _Attachments()

    monkeypatch.setattr(dse_mcp, "_get_client", lambda: _Client())

    class _Resp:
        content = image_bytes

        def raise_for_status(self):
            pass

    import httpx
    monkeypatch.setattr(httpx, "get", lambda url, timeout=None: _Resp())


def test_read_message_exposes_attachment_ids_and_text(monkeypatch):
    """read_message used to keep only filename and size, so an agent on MCP
    could see an attachment existed and never read it."""
    _attachment_client(monkeypatch, [_Att("a1", "invoice.pdf", "application/pdf", 900, "Total due: 120")])
    out = json.loads(dse_mcp.read_message("ib", "m1"))
    att = out["attachments"][0]
    assert att["attachment_id"] == "a1"
    assert att["text_preview"] == "Total due: 120"
    assert "read_with" not in att  # whole text already in the preview


def test_read_attachment_returns_document_text(monkeypatch):
    _attachment_client(monkeypatch, [_Att("a1", "big.pdf", "application/pdf", 900, "x" * 5000)])
    out = json.loads(dse_mcp.read_attachment("ib", "m1", "a1"))
    assert len(out["text"]) == 5000


def test_read_attachment_returns_images_as_images(monkeypatch):
    Image = dse_mcp.Image
    png = b"\x89PNG\r\n\x1a\nfake"
    _attachment_client(monkeypatch, [_Att("a2", "photo.png", "image/png", str(len(png)))], image_bytes=png)
    out = dse_mcp.read_attachment("ib", "m1", "a2")
    assert isinstance(out[1], Image) and out[1].data == png


def test_read_attachment_links_what_it_cannot_read(monkeypatch):
    _attachment_client(monkeypatch, [_Att("a3", "archive.zip", "application/zip", 50)])
    out = json.loads(dse_mcp.read_attachment("ib", "m1", "a3"))
    assert out["download_url"] == "https://files.example/signed"


def test_scheduled_email_tools(monkeypatch):
    calls = []

    class _Messages:
        def list_scheduled(self, inbox_id):
            calls.append(("list", inbox_id))
            return [{"message_id": "m1", "send_at": "2026-10-02T09:00:00Z"}]

        def cancel_scheduled(self, inbox_id, message_id):
            calls.append(("cancel", inbox_id, message_id))
            return {"message_id": message_id, "status": "cancelled"}

    class _Client:
        messages = _Messages()

    monkeypatch.setattr(dse_mcp, "_get_client", lambda: _Client())
    assert json.loads(dse_mcp.list_scheduled_emails("ib"))[0]["message_id"] == "m1"
    assert json.loads(dse_mcp.cancel_scheduled_email("ib", "m1"))["status"] == "cancelled"
    assert calls == [("list", "ib"), ("cancel", "ib", "m1")]


def test_create_inbox_can_target_a_custom_domain(monkeypatch):
    """The tool took no domain, so an agent on MCP could only ever create inboxes
    on the shared domain, never on the account's own verified domain."""
    from deadsimple.types import DomainList, Inbox

    calls = []

    class _Inboxes:
        def create(self, **kw):
            calls.append(kw)
            return Inbox.from_dict({"inbox_id": "ib", "email": "grok@ai.example.com",
                                    "display_name": "Grok", "status": "active",
                                    "local_part": "grok", "domain": "ai.example.com", "tags": [],
                                    "message_count": 0, "created_at": "t", "updated_at": "t"})

    class _Domains:
        def list(self):
            return DomainList.from_dict({"count": 1, "domains": [{
                "domain_id": "d1", "domain": "ai.example.com", "status": "active",
                "dns_records": [], "created_at": "2026-10-01T00:00:00Z"}]})

    class _Client:
        inboxes = _Inboxes()
        domains = _Domains()

    monkeypatch.setattr(dse_mcp, "_get_client", lambda: _Client())
    assert json.loads(dse_mcp.list_domains()) == [
        {"domain_id": "d1", "domain": "ai.example.com", "status": "active"}]
    out = json.loads(dse_mcp.create_inbox(display_name="Grok", local_part=" grok ", domain="ai.example.com"))
    assert out["email"] == "grok@ai.example.com"
    assert calls[-1]["domain"] == "ai.example.com" and calls[-1]["local_part"] == "grok"

    dse_mcp.create_inbox(display_name="Shared")
    assert calls[-1]["domain"] == "" and calls[-1]["local_part"] == ""


def test_send_and_reply_pass_html_body_through(monkeypatch):
    """send_email took only a plain-text body, so an agent formatting its mail
    put HTML there and the recipient saw raw tags."""
    calls = []

    class _R:
        message_id, status = "m1", "sent"

    class _Messages:
        def send(self, **kw):
            calls.append(("send", kw)); return _R()

        def reply(self, inbox_id, message_id, **kw):
            calls.append(("reply", kw)); return _R()

    class _Client:
        messages = _Messages()

    monkeypatch.setattr(dse_mcp, "_get_client", lambda: _Client())
    dse_mcp.send_email("ib", "a@example.com", "Hi", "Hi both", html_body="<p>Hi both</p>")
    dse_mcp.reply_to_message("ib", "m0", "Thanks", html_body="<p>Thanks</p>")
    assert calls[0][1]["text_body"] == "Hi both" and calls[0][1]["html_body"] == "<p>Hi both</p>"
    assert calls[1][1]["html_body"] == "<p>Thanks</p>"


class _UploadClient:
    """Records attachment uploads and sends, as the MCP tools drive them."""

    def __init__(self):
        self.uploads, self.sends = [], []
        outer = self

        class _Attachments:
            def upload(self, source, *, filename=None, content_type=None, inline=False):
                outer.uploads.append((source, filename, content_type, inline))
                ref = {"attachment_id": f"att_{len(outer.uploads)}"}
                if inline:
                    ref["inline"] = True
                return ref

            def create_upload(self, filename, content_type=""):
                outer.uploads.append(("staged", filename, content_type, False))
                return {"attachment_id": "0f1e2d3c-4b5a-6978-8a9b-0c1d2e3f4a5b",
                        "upload_url": "https://s3.example/put", "content_type": content_type,
                        "expires_in": 900, "max_bytes": 1}

        class _R:
            message_id, status = "m1", "sent"

        class _Messages:
            def send(self, **kw):
                outer.sends.append(kw); return _R()

            def reply(self, inbox_id, message_id, **kw):
                outer.sends.append(kw); return _R()

            def forward(self, inbox_id, message_id, **kw):
                outer.sends.append(kw); return _R()

        self.attachments = _Attachments()
        self.messages = _Messages()


def test_hosted_server_never_reads_its_own_files(monkeypatch):
    """Over HTTP a local path is a file on the server. /proc/self/environ would
    have mailed the caller the Lambda's AWS credentials."""
    client = _UploadClient()
    monkeypatch.setattr(dse_mcp, "_get_client", lambda: client)
    monkeypatch.setattr(dse_mcp, "_http_mode", True)
    for path in ("/proc/self/environ", "/var/task/lambda_handler.py", "notes.txt", "~/.aws/credentials"):
        for call in (lambda: dse_mcp.send_email("ib", "a@example.com", "s", "b", attachments=[path]),
                     lambda: dse_mcp.send_email("ib", "a@example.com", "s", "b", images=[path]),
                     lambda: dse_mcp.reply_to_message("ib", "m0", "b", attachments=path),
                     lambda: dse_mcp.forward_message("ib", "m0", "a@example.com", images=[path])):
            out = json.loads(call())
            assert out["status"] == "not_sent" and out["uploads"][0]["path"] == path
    assert client.sends == []
    # Nothing read: the only "uploads" are staged URLs handed back for the agent to PUT to.
    assert {u[0] for u in client.uploads} == {"staged"}


def test_refusal_hands_back_a_runnable_upload_command(monkeypatch):
    """Grok tried a sandbox path, ignored the advice to call another tool, and
    put the customer's photo on a public file host. Give it the command instead."""
    client = _UploadClient()
    monkeypatch.setattr(dse_mcp, "_get_client", lambda: client)
    monkeypatch.setattr(dse_mcp, "_http_mode", True)
    path = "/workspace/attachments/chat camera_upload.jpg"
    # Not an error: Grok shows tool errors in red to the customer.
    out = json.loads(dse_mcp.send_email("ib", "a@example.com", "Photo", "Here",
                                        images=[path, "https://x.example/b.jpg"]))
    assert out["status"] == "not_sent" and "send_email again" in out["next_step"]
    assert client.uploads == [("staged", "chat camera_upload.jpg", "image/jpeg", False)]
    up = out["uploads"][0]
    assert up["attachment_id"] == "0f1e2d3c-4b5a-6978-8a9b-0c1d2e3f4a5b"
    assert "--data-binary @'/workspace/attachments/chat camera_upload.jpg' https://s3.example/put" in up["command"]
    assert client.sends == []
    # The retry with the id goes through as a plain string.
    dse_mcp.send_email("ib", "a@example.com", "Photo", "Here",
                       images=["0f1e2d3c-4b5a-6978-8a9b-0c1d2e3f4a5b"])
    assert client.sends[0]["images"] == [{"attachment_id": "0f1e2d3c-4b5a-6978-8a9b-0c1d2e3f4a5b"}]


def test_stdio_still_attaches_local_paths(monkeypatch):
    client = _UploadClient()
    monkeypatch.setattr(dse_mcp, "_get_client", lambda: client)
    monkeypatch.setattr(dse_mcp, "_http_mode", False)
    dse_mcp.send_email("ib", "a@example.com", "s", "b", attachments=["/tmp/report.pdf"])
    assert client.sends[0]["attachments"] == ["/tmp/report.pdf"]


def test_data_uri_attaches_a_file_the_agent_made(monkeypatch):
    """Grok built a .docx in its sandbox and had no way to hand it over, so it
    put it in the customer's Google Drive instead."""
    import base64
    client = _UploadClient()
    monkeypatch.setattr(dse_mcp, "_get_client", lambda: client)
    monkeypatch.setattr(dse_mcp, "_http_mode", True)
    docx = b"PK\x03\x04 fake docx, bytes"
    mime = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    uri = f"data:{mime};name=Fathom%20Blog.docx;base64,{base64.b64encode(docx).decode()}"
    png = "data:image/png;base64," + base64.b64encode(b"\x89PNG").decode()

    dse_mcp.send_email("ib", "a@example.com", "Blog", "Attached", attachments=[uri], images=[png])
    assert (docx, "Fathom Blog.docx", mime, False) in client.uploads
    assert (b"\x89PNG", "attachment.png", "image/png", True) in client.uploads
    sent = client.sends[0]
    assert len(sent["attachments"]) == 1 and "inline" not in sent["attachments"][0]
    assert len(sent["images"]) == 1 and sent["images"][0]["inline"] is True

    # A model that flattens the list into a string must not have the URI split on commas.
    dse_mcp.reply_to_message("ib", "m0", "Again", attachments=uri)
    assert client.uploads[2][0] == docx


def test_upload_url_flow_and_attachment_ids(monkeypatch):
    client = _UploadClient()
    monkeypatch.setattr(dse_mcp, "_get_client", lambda: client)
    monkeypatch.setattr(dse_mcp, "_http_mode", True)
    staged = json.loads(dse_mcp.create_attachment_upload("Report.docx"))
    assert staged["upload_url"] == "https://s3.example/put"
    assert client.uploads[0][2] == ("application/vnd.openxmlformats-officedocument"
                                    ".wordprocessingml.document")
    dse_mcp.send_email("ib", "a@example.com", "s", "b",
                       attachments=[staged["attachment_id"], "https://example.com/a.pdf"])
    assert client.sends[0]["attachments"] == [
        {"attachment_id": staged["attachment_id"]}, "https://example.com/a.pdf"]


def test_bad_data_uri_says_why():
    with pytest.raises(ValueError, match="comma"):
        dse_mcp._decode_data_uri("data:text/plain;base64")


def test_office_types_are_named_without_system_mime_tables(monkeypatch):
    import mimetypes
    monkeypatch.setattr(mimetypes, "guess_type", lambda *a, **k: (None, None))
    monkeypatch.setattr(mimetypes, "guess_extension", lambda *a, **k: None)
    assert dse_mcp._guess_type("Blog.docx").endswith("wordprocessingml.document")
    mime = dse_mcp._guess_type("Sheet.xlsx")
    assert dse_mcp._decode_data_uri(f"data:{mime};base64,AA==")[1] == "attachment.xlsx"
