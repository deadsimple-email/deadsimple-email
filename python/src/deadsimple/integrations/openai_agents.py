"""OpenAI Agents SDK tool definitions for Dead Simple Email.

Usage with the OpenAI Agents SDK::

    from agents import Agent
    from deadsimple.integrations.openai_agents import get_tools

    agent = Agent(
        name="Email Agent",
        tools=get_tools(api_key="dse_your_api_key"),
    )

Usage with the raw OpenAI function calling API::

    from deadsimple.integrations.openai_agents import get_function_definitions

    tools = get_function_definitions()
    response = openai.chat.completions.create(
        model="gpt-4o",
        messages=[...],
        tools=tools,
    )
"""

from __future__ import annotations

import json
import os
from typing import Any, Callable

from deadsimple.client import DeadSimple
from deadsimple.exceptions import DeadSimpleError

_client: DeadSimple | None = None


def _get_client(api_key: str | None = None) -> DeadSimple:
    global _client
    if _client is None:
        key = api_key or os.environ.get("DSE_API_KEY", "")
        if not key:
            raise RuntimeError("DSE_API_KEY environment variable is required")
        _client = DeadSimple(key)
    return _client


# ── Tool implementations ─────────────────────────────────────────────────────


def _send_email(inbox_id: str, to: str, subject: str, body: str, **_: Any) -> str:
    try:
        result = _get_client().messages.send(inbox_id=inbox_id, to=to, subject=subject, text_body=body)
        return json.dumps({"message_id": result.message_id, "status": result.status})
    except DeadSimpleError as e:
        return json.dumps({"error": e.message})


def _read_emails(inbox_id: str, limit: int = 5, **_: Any) -> str:
    try:
        result = _get_client().messages.list(inbox_id, limit=int(limit))
        return json.dumps([{
            "message_id": m.message_id, "direction": m.direction,
            "from": m.from_email, "subject": m.subject, "snippet": m.snippet,
        } for m in result.messages])
    except DeadSimpleError as e:
        return json.dumps({"error": e.message})


def _read_email(inbox_id: str, message_id: str, **_: Any) -> str:
    try:
        msg = _get_client().messages.get(inbox_id, message_id)
        return json.dumps({
            "from": msg.from_email, "to": msg.to, "subject": msg.subject,
            "body": msg.latest_reply or msg.text_body,
        })
    except DeadSimpleError as e:
        return json.dumps({"error": e.message})


def _reply_to_email(inbox_id: str, message_id: str, body: str, **_: Any) -> str:
    try:
        result = _get_client().messages.reply(inbox_id, message_id, text_body=body)
        return json.dumps({"message_id": result.message_id, "status": result.status})
    except DeadSimpleError as e:
        return json.dumps({"error": e.message})


def _create_inbox(display_name: str = "", **_: Any) -> str:
    try:
        inbox = _get_client().inboxes.create(display_name=display_name)
        return json.dumps({"inbox_id": inbox.inbox_id, "email": inbox.email})
    except DeadSimpleError as e:
        return json.dumps({"error": e.message})


def _list_inboxes(**_: Any) -> str:
    try:
        result = _get_client().inboxes.list()
        return json.dumps([{
            "inbox_id": i.inbox_id, "email": i.email,
            "display_name": i.display_name, "message_count": i.message_count,
        } for i in result.inboxes])
    except DeadSimpleError as e:
        return json.dumps({"error": e.message})


def _wait_for_email(inbox_id: str, from_contains: str = "", subject_contains: str = "", timeout_seconds: int = 60, **_: Any) -> str:
    try:
        msg = _get_client().messages.wait_for(
            inbox_id, from_contains=from_contains, subject_contains=subject_contains, timeout=float(timeout_seconds),
        )
        if not msg:
            return json.dumps({"status": "timeout"})
        return json.dumps({
            "status": "received", "from": msg.from_email, "subject": msg.subject,
            "body": msg.latest_reply or msg.text_body, "extracted": getattr(msg, "extracted", {}) or {},
        })
    except DeadSimpleError as e:
        return json.dumps({"error": e.message})


def _get_verification_code(inbox_id: str, from_contains: str = "", timeout_seconds: int = 60, **_: Any) -> str:
    try:
        msg = _get_client().messages.wait_for(inbox_id, from_contains=from_contains, timeout=float(timeout_seconds))
        if not msg:
            return json.dumps({"status": "timeout"})
        extracted = getattr(msg, "extracted", {}) or {}
        return json.dumps({
            "status": "received",
            "verification_code": extracted.get("verification_code"),
            "magic_link_url": extracted.get("magic_link_url"),
            "all_codes": extracted.get("all_codes"),
        })
    except DeadSimpleError as e:
        return json.dumps({"error": e.message})


# ── Function definitions for OpenAI function calling ─────────────────────────


FUNCTION_DEFINITIONS: list[dict[str, Any]] = [
    {
        "type": "function",
        "function": {
            "name": "send_email",
            "description": "Send an email from a Dead Simple Email inbox.",
            "parameters": {
                "type": "object",
                "properties": {
                    "inbox_id": {"type": "string", "description": "The inbox to send from"},
                    "to": {"type": "string", "description": "Recipient email address"},
                    "subject": {"type": "string", "description": "Email subject"},
                    "body": {"type": "string", "description": "Email body (plain text)"},
                },
                "required": ["inbox_id", "to", "subject", "body"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "read_emails",
            "description": "Read recent emails from a Dead Simple Email inbox.",
            "parameters": {
                "type": "object",
                "properties": {
                    "inbox_id": {"type": "string", "description": "The inbox to read from"},
                    "limit": {"type": "integer", "description": "Max messages to return (default 5)"},
                },
                "required": ["inbox_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "read_email",
            "description": "Read a single email with full body content.",
            "parameters": {
                "type": "object",
                "properties": {
                    "inbox_id": {"type": "string", "description": "The inbox containing the message"},
                    "message_id": {"type": "string", "description": "The message ID to read"},
                },
                "required": ["inbox_id", "message_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "reply_to_email",
            "description": "Reply to an email. Threading is handled automatically.",
            "parameters": {
                "type": "object",
                "properties": {
                    "inbox_id": {"type": "string", "description": "The inbox containing the message"},
                    "message_id": {"type": "string", "description": "The message ID to reply to"},
                    "body": {"type": "string", "description": "Reply body (plain text)"},
                },
                "required": ["inbox_id", "message_id", "body"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "wait_for_email",
            "description": "Wait for a NEW inbound email (signup/verification flows) and return it with any extracted verification code/link.",
            "parameters": {
                "type": "object",
                "properties": {
                    "inbox_id": {"type": "string", "description": "The inbox to watch"},
                    "from_contains": {"type": "string", "description": "Only match senders containing this text"},
                    "subject_contains": {"type": "string", "description": "Only match subjects containing this text"},
                    "timeout_seconds": {"type": "integer", "description": "Max seconds to wait (default 60)"},
                },
                "required": ["inbox_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_verification_code",
            "description": "Wait for a verification/OTP email and return the extracted code and any magic link.",
            "parameters": {
                "type": "object",
                "properties": {
                    "inbox_id": {"type": "string", "description": "The inbox to watch"},
                    "from_contains": {"type": "string", "description": "Only match senders containing this text"},
                    "timeout_seconds": {"type": "integer", "description": "Max seconds to wait (default 60)"},
                },
                "required": ["inbox_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "create_inbox",
            "description": "Create a new email inbox.",
            "parameters": {
                "type": "object",
                "properties": {
                    "display_name": {"type": "string", "description": "Friendly name (e.g. 'Support Bot')"},
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "list_inboxes",
            "description": "List all email inboxes in the account.",
            "parameters": {"type": "object", "properties": {}},
        },
    },
]

TOOL_MAP: dict[str, Callable[..., str]] = {
    "send_email": _send_email,
    "read_emails": _read_emails,
    "read_email": _read_email,
    "reply_to_email": _reply_to_email,
    "wait_for_email": _wait_for_email,
    "get_verification_code": _get_verification_code,
    "create_inbox": _create_inbox,
    "list_inboxes": _list_inboxes,
}


def get_function_definitions() -> list[dict[str, Any]]:
    """Get OpenAI function calling tool definitions."""
    return FUNCTION_DEFINITIONS


def handle_tool_call(name: str, arguments: dict[str, Any]) -> str:
    """Execute a tool call and return the result string.

    Usage::

        for tool_call in response.choices[0].message.tool_calls:
            result = handle_tool_call(
                tool_call.function.name,
                json.loads(tool_call.function.arguments),
            )
    """
    fn = TOOL_MAP.get(name)
    if not fn:
        return json.dumps({"error": f"Unknown tool: {name}"})
    return fn(**arguments)


def get_tools(api_key: str | None = None) -> list[Any]:
    """Get tool objects compatible with the OpenAI Agents SDK.

    This initializes the Dead Simple client and returns function tool wrappers.
    Requires the `agents` package to be installed.
    """
    if api_key:
        _get_client(api_key)

    try:
        from agents import FunctionTool
    except ImportError:
        raise ImportError("Install the OpenAI Agents SDK: pip install openai-agents")

    tools = []
    for defn in FUNCTION_DEFINITIONS:
        fn_name = defn["function"]["name"]
        fn = TOOL_MAP[fn_name]
        tools.append(FunctionTool(
            name=fn_name,
            description=defn["function"]["description"],
            params_json_schema=defn["function"]["parameters"],
            on_invoke_tool=lambda ctx, args, _fn=fn: _fn(**json.loads(args)),
        ))
    return tools
