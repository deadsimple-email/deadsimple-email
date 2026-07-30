"""Microsoft AutoGen tool definitions for Dead Simple Email.

Usage::

    from autogen import AssistantAgent, UserProxyAgent
    from deadsimple.integrations.autogen import get_tools, register_tools

    assistant = AssistantAgent("email_agent", llm_config=llm_config)
    user_proxy = UserProxyAgent("user")

    register_tools(user_proxy, assistant, api_key="dse_your_api_key")

Or set the DSE_API_KEY environment variable.
"""
from __future__ import annotations

import json
import os
from typing import Any, Annotated

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


def send_email(
    inbox_id: Annotated[str, "The inbox to send from"],
    to: Annotated[str, "Recipient email address"],
    subject: Annotated[str, "Email subject line"],
    body: Annotated[str, "Email body text"],
) -> str:
    """Send an email from a Dead Simple Email inbox."""
    try:
        result = _get_client().messages.send(inbox_id=inbox_id, to=to, subject=subject, text_body=body)
        return json.dumps({"message_id": result.message_id, "status": result.status})
    except DeadSimpleError as e:
        return json.dumps({"error": e.message})


def read_emails(
    inbox_id: Annotated[str, "The inbox to read from"],
    limit: Annotated[int, "Max messages to return"] = 5,
) -> str:
    """Read recent emails from a Dead Simple Email inbox."""
    try:
        result = _get_client().messages.list(inbox_id, limit=limit)
        return json.dumps([{
            "message_id": m.message_id, "direction": m.direction,
            "from": m.from_email, "subject": m.subject, "snippet": m.snippet,
        } for m in result.messages])
    except DeadSimpleError as e:
        return json.dumps({"error": e.message})


def read_email(
    inbox_id: Annotated[str, "The inbox containing the message"],
    message_id: Annotated[str, "The message ID to read"],
) -> str:
    """Read a single email with full body content."""
    try:
        msg = _get_client().messages.get(inbox_id, message_id)
        return json.dumps({
            "from": msg.from_email, "to": msg.to, "subject": msg.subject,
            "body": msg.latest_reply or msg.text_body,
        })
    except DeadSimpleError as e:
        return json.dumps({"error": e.message})


def reply_to_email(
    inbox_id: Annotated[str, "The inbox containing the message"],
    message_id: Annotated[str, "The message ID to reply to"],
    body: Annotated[str, "Reply body text"],
) -> str:
    """Reply to an email. Threading is handled automatically."""
    try:
        result = _get_client().messages.reply(inbox_id, message_id, text_body=body)
        return json.dumps({"message_id": result.message_id, "status": result.status})
    except DeadSimpleError as e:
        return json.dumps({"error": e.message})


def wait_for_email(
    inbox_id: Annotated[str, "The inbox to watch"],
    from_contains: Annotated[str, "Only match senders containing this text"] = "",
    subject_contains: Annotated[str, "Only match subjects containing this text"] = "",
    timeout_seconds: Annotated[int, "Max seconds to wait"] = 60,
) -> str:
    """Wait for a NEW inbound email (signup/verification flows) and return it with any extracted verification data."""
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


def get_verification_code(
    inbox_id: Annotated[str, "The inbox to watch"],
    from_contains: Annotated[str, "Only match senders containing this text"] = "",
    timeout_seconds: Annotated[int, "Max seconds to wait"] = 60,
) -> str:
    """Wait for a verification/OTP email and return the extracted code and any magic link."""
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


def create_inbox(
    display_name: Annotated[str, "Friendly name for the inbox"] = "",
) -> str:
    """Create a new email inbox."""
    try:
        inbox = _get_client().inboxes.create(display_name=display_name)
        return json.dumps({"inbox_id": inbox.inbox_id, "email": inbox.email})
    except DeadSimpleError as e:
        return json.dumps({"error": e.message})


def list_inboxes() -> str:
    """List all email inboxes in the account."""
    try:
        result = _get_client().inboxes.list()
        return json.dumps([{"inbox_id": i.inbox_id, "email": i.email, "display_name": i.display_name} for i in result.inboxes])
    except DeadSimpleError as e:
        return json.dumps({"error": e.message})


ALL_TOOLS = [send_email, read_emails, read_email, reply_to_email, wait_for_email, get_verification_code, create_inbox, list_inboxes]


def register_tools(user_proxy: Any, assistant: Any, api_key: str | None = None) -> None:
    """Register all Dead Simple Email tools with AutoGen agents.

    Args:
        user_proxy: The UserProxyAgent that will execute tools.
        assistant: The AssistantAgent that will decide to use tools.
        api_key: Optional API key (defaults to DSE_API_KEY env var).
    """
    if api_key:
        _get_client(api_key)

    from autogen import register_function

    for tool_fn in ALL_TOOLS:
        register_function(
            tool_fn,
            caller=assistant,
            executor=user_proxy,
            description=tool_fn.__doc__ or "",
        )


def get_tools() -> list:
    """Get the list of tool functions for manual registration."""
    return list(ALL_TOOLS)
