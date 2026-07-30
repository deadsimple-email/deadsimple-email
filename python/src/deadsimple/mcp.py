"""Dead Simple Email MCP server.

Run directly:
    python -m deadsimple.mcp

Claude Desktop / Cursor / Windsurf config:
    {
        "mcpServers": {
            "deadsimple": {
                "command": "python",
                "args": ["-m", "deadsimple.mcp"],
                "env": { "DSE_API_KEY": "dse_your_api_key" }
            }
        }
    }

Google Agent Development Kit (ADK):
    from google.adk.tools.mcp_tool import MCPToolset
    tools = MCPToolset(
        connection_params=StdioServerParameters(
            command="python",
            args=["-m", "deadsimple.mcp"],
            env={"DSE_API_KEY": "dse_your_api_key"},
        )
    )

Remote (Streamable HTTP) — for hosting one server for many callers:
    python -m deadsimple.mcp --transport streamable-http --port 8000

    Each caller then supplies its OWN key per request:
        Authorization: Bearer dse_your_api_key
    and connects to http://host:8000/mcp

    In HTTP mode DSE_API_KEY is ignored entirely — see _get_client below.
"""

from __future__ import annotations

import json
import os
from contextvars import ContextVar
from functools import lru_cache

from mcp.server.fastmcp import FastMCP
from mcp.types import ToolAnnotations

from deadsimple.client import DeadSimple

mcp = FastMCP(
    "Dead Simple Email",
    instructions=(
        "Email API for AI agents — create inboxes, send/receive email, manage threads "
        "and webhooks. For signup/2FA flows: create_inbox, use its address to register, "
        "then wait_for_email or get_verification_code to receive the OTP/magic link."
    ),
    website_url="https://deadsimple.email",
    stateless_http=True,
)

# Set per HTTP request by _ApiKeyMiddleware. Empty in stdio mode.
_request_api_key: ContextVar[str] = ContextVar("dse_request_api_key", default="")

# True once the process is serving HTTP, where a single server handles many
# callers. Gating on this is what stops one caller's request from being served
# with another caller's (or the operator's) credentials.
_http_mode = False


@lru_cache(maxsize=256)
def _client_for(api_key: str) -> DeadSimple:
    """Reuse one client per API key rather than rebuilding per call."""
    return DeadSimple(api_key)


def _get_client() -> DeadSimple:
    """Resolve the caller's client.

    HTTP mode: strictly per-request, from the Authorization header. There is no
    environment fallback here on purpose — falling back would silently serve one
    caller with whatever key the operator happened to export, exposing another
    tenant's inboxes.

    stdio mode: one process per caller, so the DSE_API_KEY env var is correct.
    """
    if _http_mode:
        api_key = _request_api_key.get()
        if not api_key:
            raise RuntimeError(
                "Missing API key. Send 'Authorization: Bearer dse_...' with each request. "
                "Get a key instantly at POST https://api.deadsimple.email/v1/auth/agent-signup"
            )
        return _client_for(api_key)

    api_key = os.environ.get("DSE_API_KEY", "")
    if not api_key:
        raise RuntimeError("DSE_API_KEY environment variable is required")
    return _client_for(api_key)


# ── Inbox tools ───────────────────────────────────────────────────────────────


@mcp.tool(
    title="Create Inbox",
    annotations=ToolAnnotations(
        title="Create Inbox",
        readOnlyHint=False,
        destructiveHint=False,
        idempotentHint=False,
        openWorldHint=True,
    ),
)
def create_inbox(display_name: str = "", tags: str = "") -> str:
    """Create a new email inbox. Returns the inbox details including the email address.

    Args:
        display_name: Friendly name for the inbox (e.g. "Support Bot")
        tags: Comma-separated tags (e.g. "support,production")
    """
    client = _get_client()
    tag_list = [t.strip() for t in tags.split(",") if t.strip()] if tags else None
    inbox = client.inboxes.create(display_name=display_name, tags=tag_list)
    return json.dumps({
        "inbox_id": inbox.inbox_id,
        "email": inbox.email,
        "display_name": inbox.display_name,
        "status": inbox.status,
    }, indent=2)


@mcp.tool(
    title="List Inboxes",
    annotations=ToolAnnotations(
        title="List Inboxes",
        readOnlyHint=True,
        destructiveHint=False,
        idempotentHint=True,
        openWorldHint=True,
    ),
)
def list_inboxes(limit: int = 20) -> str:
    """List all email inboxes in the account.

    Args:
        limit: Maximum number of inboxes to return (default 20)
    """
    client = _get_client()
    result = client.inboxes.list(limit=limit)
    return json.dumps([{
        "inbox_id": i.inbox_id,
        "email": i.email,
        "display_name": i.display_name,
        "message_count": i.message_count,
        "status": i.status,
    } for i in result.inboxes], indent=2)


@mcp.tool(
    title="Delete Inbox",
    annotations=ToolAnnotations(
        title="Delete Inbox",
        readOnlyHint=False,
        destructiveHint=True,
        idempotentHint=True,
        openWorldHint=True,
    ),
)
def delete_inbox(inbox_id: str) -> str:
    """Delete an inbox and all its messages.

    Args:
        inbox_id: The inbox ID to delete
    """
    client = _get_client()
    client.inboxes.delete(inbox_id)
    return f"Inbox {inbox_id} deleted."


# ── Message tools ─────────────────────────────────────────────────────────────


@mcp.tool(
    title="Send Email",
    annotations=ToolAnnotations(
        title="Send Email",
        readOnlyHint=False,
        destructiveHint=False,
        idempotentHint=False,
        openWorldHint=True,
    ),
)
def send_email(inbox_id: str, to: str, subject: str, body: str, cc: str = "", bcc: str = "") -> str:
    """Send an email from an inbox.

    Args:
        inbox_id: The inbox to send from
        to: Recipient email address (comma-separated for multiple)
        subject: Email subject line
        body: Email body (plain text)
        cc: CC recipients (comma-separated, optional)
        bcc: BCC recipients (comma-separated, optional)
    """
    client = _get_client()
    to_list = [t.strip() for t in to.split(",") if t.strip()]
    cc_list = [c.strip() for c in cc.split(",") if c.strip()] if cc else None
    bcc_list = [b.strip() for b in bcc.split(",") if b.strip()] if bcc else None
    result = client.messages.send(
        inbox_id=inbox_id,
        to=to_list,
        subject=subject,
        text_body=body,
        cc=cc_list,
        bcc=bcc_list,
    )
    return json.dumps({"message_id": result.message_id, "status": result.status}, indent=2)


@mcp.tool(
    title="List Messages",
    annotations=ToolAnnotations(
        title="List Messages",
        readOnlyHint=True,
        destructiveHint=False,
        idempotentHint=True,
        openWorldHint=True,
    ),
)
def read_messages(inbox_id: str, limit: int = 10) -> str:
    """Read recent messages in an inbox.

    Args:
        inbox_id: The inbox to read from
        limit: Maximum number of messages to return (default 10)
    """
    client = _get_client()
    result = client.messages.list(inbox_id, limit=limit)
    return json.dumps([{
        "message_id": m.message_id,
        "direction": m.direction,
        "from": m.from_email,
        "to": m.to,
        "subject": m.subject,
        "snippet": m.snippet,
        "date": m.created_at or m.received_at,
    } for m in result.messages], indent=2)


@mcp.tool(
    title="Read Message",
    annotations=ToolAnnotations(
        title="Read Message",
        readOnlyHint=True,
        destructiveHint=False,
        idempotentHint=True,
        openWorldHint=True,
    ),
)
def read_message(inbox_id: str, message_id: str) -> str:
    """Read a single message with full body content.

    Args:
        inbox_id: The inbox containing the message
        message_id: The message ID to read
    """
    client = _get_client()
    msg = client.messages.get(inbox_id, message_id)
    return json.dumps({
        "message_id": msg.message_id,
        "direction": msg.direction,
        "from": f"{msg.from_name} <{msg.from_email}>" if msg.from_name else msg.from_email,
        "to": msg.to,
        "cc": msg.cc,
        "subject": msg.subject,
        "body": msg.latest_reply or msg.text_body or msg.html_body,
        "full_body": msg.text_body,
        "attachments": [{"filename": a.filename, "size": a.size} for a in msg.attachments],
        "date": msg.created_at or msg.received_at,
    }, indent=2)


@mcp.tool(
    title="Reply to Message",
    annotations=ToolAnnotations(
        title="Reply to Message",
        readOnlyHint=False,
        destructiveHint=False,
        idempotentHint=False,
        openWorldHint=True,
    ),
)
def reply_to_message(inbox_id: str, message_id: str, body: str) -> str:
    """Reply to a message. Threading headers are set automatically.

    Args:
        inbox_id: The inbox containing the message
        message_id: The message ID to reply to
        body: Reply body (plain text)
    """
    client = _get_client()
    result = client.messages.reply(inbox_id, message_id, text_body=body)
    return json.dumps({"message_id": result.message_id, "status": result.status}, indent=2)


@mcp.tool(
    title="Forward Message",
    annotations=ToolAnnotations(
        title="Forward Message",
        readOnlyHint=False,
        destructiveHint=False,
        idempotentHint=False,
        openWorldHint=True,
    ),
)
def forward_message(inbox_id: str, message_id: str, to: str, body: str = "") -> str:
    """Forward a message to new recipients.

    Args:
        inbox_id: The inbox containing the message
        message_id: The message ID to forward
        to: Recipient email address (comma-separated for multiple)
        body: Optional additional text to include
    """
    client = _get_client()
    to_list = [t.strip() for t in to.split(",") if t.strip()]
    result = client.messages.forward(inbox_id, message_id, to=to_list, text_body=body)
    return json.dumps({"message_id": result.message_id, "status": result.status}, indent=2)


# ── Signup / verification tools ───────────────────────────────────────────────


def _message_summary(msg) -> dict:
    return {
        "message_id": msg.message_id,
        "from": msg.from_email,
        "subject": msg.subject,
        "body": msg.latest_reply or msg.text_body or msg.html_body,
        "extracted": getattr(msg, "extracted", {}) or {},
        "date": msg.created_at or msg.received_at,
    }


@mcp.tool(
    title="Wait for Email",
    annotations=ToolAnnotations(
        title="Wait for Email",
        readOnlyHint=True,
        destructiveHint=False,
        idempotentHint=True,
        openWorldHint=True,
    ),
)
def wait_for_email(inbox_id: str, from_contains: str = "", subject_contains: str = "", timeout_seconds: int = 60) -> str:
    """Block until a NEW inbound email arrives in the inbox, then return it.

    Use for signup/verification flows: trigger the action that sends the email,
    then call this to receive it. Only emails arriving after this call count.

    Args:
        inbox_id: The inbox to watch
        from_contains: Only match senders containing this text (optional)
        subject_contains: Only match subjects containing this text (optional)
        timeout_seconds: Max seconds to wait (default 60)
    """
    client = _get_client()
    msg = client.messages.wait_for(
        inbox_id,
        from_contains=from_contains,
        subject_contains=subject_contains,
        timeout=float(timeout_seconds),
    )
    if not msg:
        return json.dumps({"status": "timeout", "message": f"No matching email within {timeout_seconds}s"}, indent=2)
    return json.dumps({"status": "received", **_message_summary(msg)}, indent=2)


@mcp.tool(
    title="Get Verification Code",
    annotations=ToolAnnotations(
        title="Get Verification Code",
        readOnlyHint=True,
        destructiveHint=False,
        idempotentHint=True,
        openWorldHint=True,
    ),
)
def get_verification_code(inbox_id: str, from_contains: str = "", timeout_seconds: int = 60) -> str:
    """Wait for a verification/OTP email and return the extracted code.

    Waits for the next new inbound email, then returns the auto-extracted
    verification code (and any magic link). Perfect for autonomous sign-ups.

    Args:
        inbox_id: The inbox to watch
        from_contains: Only match senders containing this text (optional)
        timeout_seconds: Max seconds to wait (default 60)
    """
    client = _get_client()
    msg = client.messages.wait_for(inbox_id, from_contains=from_contains, timeout=float(timeout_seconds))
    if not msg:
        return json.dumps({"status": "timeout", "message": f"No email within {timeout_seconds}s"}, indent=2)
    extracted = getattr(msg, "extracted", {}) or {}
    return json.dumps({
        "status": "received",
        "verification_code": extracted.get("verification_code"),
        "all_codes": extracted.get("all_codes"),
        "magic_link_url": extracted.get("magic_link_url"),
        "expires_in": extracted.get("expires_in"),
        "from": msg.from_email,
        "subject": msg.subject,
    }, indent=2)


@mcp.tool(
    title="Get Verification Link",
    annotations=ToolAnnotations(
        title="Get Verification Link",
        readOnlyHint=True,
        destructiveHint=False,
        idempotentHint=True,
        openWorldHint=True,
    ),
)
def get_verification_link(inbox_id: str, from_contains: str = "", timeout_seconds: int = 60) -> str:
    """Wait for an email and return the extracted magic link / verification URL.

    Args:
        inbox_id: The inbox to watch
        from_contains: Only match senders containing this text (optional)
        timeout_seconds: Max seconds to wait (default 60)
    """
    client = _get_client()
    msg = client.messages.wait_for(inbox_id, from_contains=from_contains, timeout=float(timeout_seconds))
    if not msg:
        return json.dumps({"status": "timeout", "message": f"No email within {timeout_seconds}s"}, indent=2)
    extracted = getattr(msg, "extracted", {}) or {}
    return json.dumps({
        "status": "received",
        "magic_link_url": extracted.get("magic_link_url"),
        "all_links": extracted.get("all_links"),
        "from": msg.from_email,
        "subject": msg.subject,
    }, indent=2)


# ── Thread tools ──────────────────────────────────────────────────────────────


@mcp.tool(
    title="List Threads",
    annotations=ToolAnnotations(
        title="List Threads",
        readOnlyHint=True,
        destructiveHint=False,
        idempotentHint=True,
        openWorldHint=True,
    ),
)
def list_threads(inbox_id: str, limit: int = 10) -> str:
    """List conversation threads in an inbox.

    Args:
        inbox_id: The inbox to list threads for
        limit: Maximum number of threads to return (default 10)
    """
    client = _get_client()
    result = client.threads.list(inbox_id, limit=limit)
    return json.dumps([{
        "thread_id": t.thread_id,
        "subject": t.subject,
        "message_count": t.message_count,
        "participants": t.participants,
        "updated_at": t.updated_at,
    } for t in result.threads], indent=2)


@mcp.tool(
    title="Read Thread",
    annotations=ToolAnnotations(
        title="Read Thread",
        readOnlyHint=True,
        destructiveHint=False,
        idempotentHint=True,
        openWorldHint=True,
    ),
)
def read_thread(inbox_id: str, thread_id: str) -> str:
    """Read all messages in a conversation thread.

    Args:
        inbox_id: The inbox containing the thread
        thread_id: The thread ID to read
    """
    client = _get_client()
    thread = client.threads.get(inbox_id, thread_id)
    return json.dumps({
        "thread_id": thread.thread_id,
        "subject": thread.subject,
        "participants": thread.participants,
        "messages": [{
            "message_id": m.message_id,
            "direction": m.direction,
            "from": m.from_email,
            "body": m.latest_reply or m.text_body,
            "date": m.created_at or m.received_at,
        } for m in thread.messages],
    }, indent=2)


# ── Utility tools ─────────────────────────────────────────────────────────────


@mcp.tool(
    title="Get Usage",
    annotations=ToolAnnotations(
        title="Get Usage",
        readOnlyHint=True,
        destructiveHint=False,
        idempotentHint=True,
        openWorldHint=True,
    ),
)
def get_usage() -> str:
    """Get account usage metrics: inboxes, emails sent/received, plan limits."""
    client = _get_client()
    usage = client.usage.get()
    return json.dumps({
        "plan": usage.plan_name,
        "inboxes": usage.inboxes,
        "emails": usage.emails,
        "webhooks": usage.webhooks,
        "custom_domains": usage.custom_domains,
    }, indent=2)


# ── Remote transport ──────────────────────────────────────────────────────────


class _ApiKeyMiddleware:
    """Pure-ASGI middleware that pins the caller's bearer token to this request.

    Written against the raw ASGI interface rather than Starlette's
    BaseHTTPMiddleware, which runs the downstream app in a separate task and
    would break ContextVar propagation into the tool call.
    """

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope.get("type") != "http":
            await self.app(scope, receive, send)
            return

        api_key = ""
        for raw_name, raw_value in scope.get("headers") or []:
            if raw_name.lower() == b"authorization":
                value = raw_value.decode("latin-1").strip()
                if value.lower().startswith("bearer "):
                    api_key = value[7:].strip()
                break

        token = _request_api_key.set(api_key)
        try:
            await self.app(scope, receive, send)
        finally:
            _request_api_key.reset(token)


def http_app(transport: str = "streamable-http"):
    """Build the ASGI app for remote hosting, with per-request auth applied.

    MCP ships DNS-rebinding protection that rejects any Host header not on an
    allowlist (HTTP 421). The default list covers localhost only, so anything
    served under a real domain must name it here — set DSE_MCP_ALLOWED_HOSTS to
    a comma-separated list of hostnames (a bare host also permits host:port).
    """
    global _http_mode
    _http_mode = True

    allowed = [h.strip() for h in os.environ.get("DSE_MCP_ALLOWED_HOSTS", "").split(",") if h.strip()]
    if allowed:
        from mcp.server.transport_security import TransportSecuritySettings

        hosts: list[str] = []
        origins: list[str] = []
        for host in allowed:
            hosts += [host, f"{host}:*"]
            origins += [f"https://{host}", f"http://{host}"]
        mcp.settings.transport_security = TransportSecuritySettings(
            allowed_hosts=hosts, allowed_origins=origins
        )

    base = mcp.sse_app() if transport == "sse" else mcp.streamable_http_app()
    return _ApiKeyMiddleware(base)


# ── Entry point ───────────────────────────────────────────────────────────────


def main(argv: list[str] | None = None) -> None:
    import argparse

    parser = argparse.ArgumentParser(prog="python -m deadsimple.mcp")
    parser.add_argument(
        "--transport",
        default=os.environ.get("DSE_MCP_TRANSPORT", "stdio"),
        choices=["stdio", "streamable-http", "sse"],
        help="stdio (default, one process per caller) or a remote HTTP transport.",
    )
    parser.add_argument("--host", default=os.environ.get("DSE_MCP_HOST", "127.0.0.1"))
    parser.add_argument("--port", type=int, default=int(os.environ.get("DSE_MCP_PORT", "8000")))
    args = parser.parse_args(argv)

    if args.transport == "stdio":
        mcp.run()
        return

    import uvicorn

    uvicorn.run(http_app(args.transport), host=args.host, port=args.port)


if __name__ == "__main__":
    main()
