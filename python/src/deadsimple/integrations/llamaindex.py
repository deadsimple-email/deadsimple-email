"""LlamaIndex integration for Dead Simple Email.

Provides a tool spec for LlamaIndex agents and a reader for loading inbox
contents as documents for RAG pipelines.

Usage as tools::

    from deadsimple.integrations.llamaindex import DeadSimpleToolSpec

    tool_spec = DeadSimpleToolSpec(api_key="dse_your_api_key")
    tools = tool_spec.to_tool_list()
    agent = OpenAIAgent.from_tools(tools)

Usage as document reader::

    from deadsimple.integrations.llamaindex import DeadSimpleReader

    reader = DeadSimpleReader(api_key="dse_your_api_key")
    documents = reader.load_data(inbox_id="inb_xxx")
"""
from __future__ import annotations

import os
from typing import Any

from deadsimple.client import DeadSimple
from deadsimple.exceptions import DeadSimpleError
from deadsimple.integrations._common import describe_email, describe_verification


class DeadSimpleToolSpec:
    """LlamaIndex tool specification for Dead Simple Email.

    Exposes email operations as tools compatible with LlamaIndex agents.
    """

    spec_functions = [
        "send_email",
        "read_emails",
        "read_email",
        "reply_to_email",
        "wait_for_email",
        "get_verification_code",
        "create_inbox",
        "list_inboxes",
    ]

    def __init__(self, api_key: str | None = None, **kwargs: Any):
        key = api_key or os.environ.get("DSE_API_KEY", "")
        if not key:
            raise RuntimeError("DSE_API_KEY is required")
        self.client = DeadSimple(key, **kwargs)

    def send_email(self, inbox_id: str, to: str, subject: str, body: str) -> str:
        """Send an email from a Dead Simple Email inbox."""
        try:
            result = self.client.messages.send(inbox_id=inbox_id, to=to, subject=subject, text_body=body)
            return f"Email sent. Message ID: {result.message_id}"
        except DeadSimpleError as e:
            return f"Error: {e.message}"

    def read_emails(self, inbox_id: str, limit: int = 5) -> str:
        """Read recent emails from a Dead Simple Email inbox."""
        try:
            result = self.client.messages.list(inbox_id, limit=limit)
            if not result.messages:
                return "No messages found."
            lines = [f"[{'IN' if m.direction == 'inbound' else 'OUT'}] {m.from_email}: {m.subject} (ID: {m.message_id})" for m in result.messages]
            return "\n".join(lines)
        except DeadSimpleError as e:
            return f"Error: {e.message}"

    def read_email(self, inbox_id: str, message_id: str) -> str:
        """Read a single email with full body content."""
        try:
            msg = self.client.messages.get(inbox_id, message_id)
            body = msg.latest_reply or msg.text_body or "(no text body)"
            return f"From: {msg.from_email}\nTo: {', '.join(msg.to)}\nSubject: {msg.subject}\n---\n{body}"
        except DeadSimpleError as e:
            return f"Error: {e.message}"

    def reply_to_email(self, inbox_id: str, message_id: str, body: str) -> str:
        """Reply to an email. Threading is handled automatically."""
        try:
            result = self.client.messages.reply(inbox_id, message_id, text_body=body)
            return f"Reply sent. Message ID: {result.message_id}"
        except DeadSimpleError as e:
            return f"Error: {e.message}"

    def wait_for_email(self, inbox_id: str, from_contains: str = "", subject_contains: str = "", timeout_seconds: int = 60) -> str:
        """Wait for a NEW inbound email (signup/verification flows). Returns the email including any extracted verification code/link."""
        try:
            msg = self.client.messages.wait_for(inbox_id, from_contains=from_contains, subject_contains=subject_contains, timeout=float(timeout_seconds))
            return describe_email(msg, timeout_seconds)
        except DeadSimpleError as e:
            return f"Error: {e.message}"

    def get_verification_code(self, inbox_id: str, from_contains: str = "", timeout_seconds: int = 60) -> str:
        """Wait for a verification/OTP email and return the extracted code and any magic link."""
        try:
            msg = self.client.messages.wait_for(inbox_id, from_contains=from_contains, timeout=float(timeout_seconds))
            return describe_verification(msg, timeout_seconds)
        except DeadSimpleError as e:
            return f"Error: {e.message}"

    def create_inbox(self, display_name: str = "") -> str:
        """Create a new email inbox."""
        try:
            inbox = self.client.inboxes.create(display_name=display_name)
            return f"Created: {inbox.email} (ID: {inbox.inbox_id})"
        except DeadSimpleError as e:
            return f"Error: {e.message}"

    def list_inboxes(self) -> str:
        """List all email inboxes in the account."""
        try:
            result = self.client.inboxes.list()
            if not result.inboxes:
                return "No inboxes found."
            return "\n".join(f"{i.email} ({i.display_name or 'unnamed'}) — {i.message_count} msgs" for i in result.inboxes)
        except DeadSimpleError as e:
            return f"Error: {e.message}"

    def to_tool_list(self) -> list:
        """Convert to LlamaIndex FunctionTool list."""
        from llama_index.core.tools import FunctionTool

        tools = []
        for fn_name in self.spec_functions:
            fn = getattr(self, fn_name)
            tools.append(FunctionTool.from_defaults(fn=fn, name=fn_name, description=fn.__doc__ or ""))
        return tools


class DeadSimpleReader:
    """LlamaIndex document reader that loads inbox contents for RAG pipelines."""

    def __init__(self, api_key: str | None = None, **kwargs: Any):
        key = api_key or os.environ.get("DSE_API_KEY", "")
        if not key:
            raise RuntimeError("DSE_API_KEY is required")
        self.client = DeadSimple(key, **kwargs)

    def load_data(self, inbox_id: str, limit: int = 50) -> list:
        """Load messages from an inbox as LlamaIndex Documents.

        Args:
            inbox_id: The inbox to load messages from.
            limit: Maximum number of messages to load.

        Returns:
            List of LlamaIndex Document objects.
        """
        from llama_index.core import Document

        result = self.client.messages.list(inbox_id, limit=limit)
        documents = []

        for msg in result.messages:
            # Get full message with body
            try:
                full = self.client.messages.get(inbox_id, msg.message_id)
                text = full.latest_reply or full.text_body or full.snippet or ""
            except Exception:
                text = msg.snippet or ""

            if not text:
                continue

            doc = Document(
                text=text,
                metadata={
                    "source": "deadsimple_email",
                    "inbox_id": inbox_id,
                    "message_id": msg.message_id,
                    "from_email": msg.from_email,
                    "to": ", ".join(msg.to),
                    "subject": msg.subject,
                    "direction": msg.direction,
                    "date": msg.created_at or msg.received_at,
                },
            )
            documents.append(doc)

        return documents
