"""CrewAI tool integration for Dead Simple Email.

Usage::

    from deadsimple.integrations.crewai import (
        send_email, read_emails, reply_to_email, create_inbox,
    )

    agent = Agent(
        role="Email Assistant",
        goal="Handle email communication",
        tools=[send_email, read_emails, reply_to_email, create_inbox],
    )

Set the DSE_API_KEY environment variable or pass it to init_client().
"""

from __future__ import annotations

import os
from typing import Any

from crewai.tools import tool

from deadsimple.client import DeadSimple
from deadsimple.exceptions import DeadSimpleError
from deadsimple.integrations._common import describe_email, describe_verification

_client: DeadSimple | None = None


def init_client(api_key: str | None = None, **kwargs: Any) -> DeadSimple:
    """Initialize the Dead Simple Email client. Called automatically if DSE_API_KEY is set."""
    global _client
    key = api_key or os.environ.get("DSE_API_KEY", "")
    if not key:
        raise RuntimeError("DSE_API_KEY environment variable is required, or call init_client(api_key=...)")
    _client = DeadSimple(key, **kwargs)
    return _client


def _get_client() -> DeadSimple:
    global _client
    if _client is None:
        init_client()
    return _client


@tool("Send Email")
def send_email(inbox_id: str, to: str, subject: str, body: str) -> str:
    """Send an email from a Dead Simple Email inbox. Provide inbox_id, to (email address), subject, and body."""
    try:
        client = _get_client()
        result = client.messages.send(inbox_id=inbox_id, to=to, subject=subject, text_body=body)
        return f"Email sent successfully. Message ID: {result.message_id}"
    except DeadSimpleError as e:
        return f"Error: {e.message}"


@tool("Read Emails")
def read_emails(inbox_id: str) -> str:
    """Read recent emails from a Dead Simple Email inbox. Provide inbox_id."""
    try:
        client = _get_client()
        result = client.messages.list(inbox_id, limit=5)
        if not result.messages:
            return "No messages found."
        lines = []
        for msg in result.messages:
            direction = "IN" if msg.direction == "inbound" else "OUT"
            lines.append(f"[{direction}] From: {msg.from_email} | Subject: {msg.subject} | ID: {msg.message_id}")
        return "\n".join(lines)
    except DeadSimpleError as e:
        return f"Error: {e.message}"


@tool("Read Email")
def read_email(inbox_id: str, message_id: str) -> str:
    """Read a single email with full body. Provide inbox_id and message_id."""
    try:
        client = _get_client()
        msg = client.messages.get(inbox_id, message_id)
        body = msg.latest_reply or msg.text_body or "(no text body)"
        return f"From: {msg.from_name or msg.from_email}\nTo: {', '.join(msg.to)}\nSubject: {msg.subject}\n---\n{body}"
    except DeadSimpleError as e:
        return f"Error: {e.message}"


@tool("Reply to Email")
def reply_to_email(inbox_id: str, message_id: str, body: str) -> str:
    """Reply to an email. Threading is handled automatically. Provide inbox_id, message_id, and body."""
    try:
        client = _get_client()
        result = client.messages.reply(inbox_id, message_id, text_body=body)
        return f"Reply sent. Message ID: {result.message_id}"
    except DeadSimpleError as e:
        return f"Error: {e.message}"


@tool("Wait for Email")
def wait_for_email(inbox_id: str, from_contains: str = "", subject_contains: str = "", timeout_seconds: int = 60) -> str:
    """Wait for a NEW inbound email in an inbox (signup/verification flows). Provide inbox_id and optionally from_contains, subject_contains, timeout_seconds. Returns the email including any extracted verification code/link."""
    try:
        client = _get_client()
        msg = client.messages.wait_for(inbox_id, from_contains=from_contains, subject_contains=subject_contains, timeout=float(timeout_seconds))
        return describe_email(msg, timeout_seconds)
    except DeadSimpleError as e:
        return f"Error: {e.message}"


@tool("Get Verification Code")
def get_verification_code(inbox_id: str, from_contains: str = "", timeout_seconds: int = 60) -> str:
    """Wait for a verification/OTP email and return the extracted code and any magic link. Provide inbox_id and optionally from_contains, timeout_seconds."""
    try:
        client = _get_client()
        msg = client.messages.wait_for(inbox_id, from_contains=from_contains, timeout=float(timeout_seconds))
        return describe_verification(msg, timeout_seconds)
    except DeadSimpleError as e:
        return f"Error: {e.message}"


@tool("Create Inbox")
def create_inbox(display_name: str = "") -> str:
    """Create a new email inbox. Optionally provide a display_name (e.g. 'Support Bot')."""
    try:
        client = _get_client()
        inbox = client.inboxes.create(display_name=display_name)
        return f"Inbox created: {inbox.email} (ID: {inbox.inbox_id})"
    except DeadSimpleError as e:
        return f"Error: {e.message}"


@tool("List Inboxes")
def list_inboxes() -> str:
    """List all email inboxes in the account."""
    try:
        client = _get_client()
        result = client.inboxes.list()
        if not result.inboxes:
            return "No inboxes found."
        lines = [f"{i.email} ({i.display_name or 'unnamed'}) — {i.message_count} messages" for i in result.inboxes]
        return "\n".join(lines)
    except DeadSimpleError as e:
        return f"Error: {e.message}"
