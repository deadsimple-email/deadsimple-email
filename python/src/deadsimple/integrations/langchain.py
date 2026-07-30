"""LangChain tool integration for Dead Simple Email.

Usage::

    from deadsimple.integrations.langchain import DeadSimpleEmailToolkit

    toolkit = DeadSimpleEmailToolkit(api_key="dse_your_api_key")
    tools = toolkit.get_tools()

    # Use with an agent
    from langchain.agents import AgentExecutor, create_tool_calling_agent
    agent = create_tool_calling_agent(llm, tools, prompt)
"""

from __future__ import annotations

from typing import Any

from langchain_core.tools import BaseTool, ToolException

from deadsimple.client import DeadSimple
from deadsimple.exceptions import DeadSimpleError
from deadsimple.integrations._common import describe_email, describe_verification


class _DSEBaseTool(BaseTool):
    """Base class for Dead Simple Email tools."""

    client: Any = None  # DeadSimple client instance
    handle_tool_error: bool = True

    class Config:
        arbitrary_types_allowed = True

    def _handle_error(self, e: DeadSimpleError) -> str:
        raise ToolException(f"Dead Simple Email error: {e.message}")


class SendEmailTool(_DSEBaseTool):
    """Send an email from an inbox."""

    name: str = "send_email"
    description: str = (
        "Send an email from a Dead Simple Email inbox. "
        "Input should include inbox_id, to (email address), subject, and body."
    )

    def _run(self, inbox_id: str, to: str, subject: str, body: str, **kwargs: Any) -> str:
        try:
            result = self.client.messages.send(
                inbox_id=inbox_id, to=to, subject=subject, text_body=body,
            )
            return f"Email sent successfully. Message ID: {result.message_id}"
        except DeadSimpleError as e:
            return self._handle_error(e)


class ReadEmailsTool(_DSEBaseTool):
    """Read recent emails from an inbox."""

    name: str = "read_emails"
    description: str = (
        "Read recent emails from a Dead Simple Email inbox. "
        "Input should include inbox_id and optionally limit (default 5)."
    )

    def _run(self, inbox_id: str, limit: int = 5, **kwargs: Any) -> str:
        try:
            result = self.client.messages.list(inbox_id, limit=limit)
            if not result.messages:
                return "No messages found in this inbox."
            lines = []
            for msg in result.messages:
                direction = "IN" if msg.direction == "inbound" else "OUT"
                lines.append(f"[{direction}] From: {msg.from_email} | Subject: {msg.subject} | ID: {msg.message_id}")
            return "\n".join(lines)
        except DeadSimpleError as e:
            return self._handle_error(e)


class ReadEmailTool(_DSEBaseTool):
    """Read a single email with full body."""

    name: str = "read_email"
    description: str = (
        "Read a single email with full body content. "
        "Input should include inbox_id and message_id."
    )

    def _run(self, inbox_id: str, message_id: str, **kwargs: Any) -> str:
        try:
            msg = self.client.messages.get(inbox_id, message_id)
            body = msg.latest_reply or msg.text_body or "(no text body)"
            return (
                f"From: {msg.from_name or msg.from_email}\n"
                f"To: {', '.join(msg.to)}\n"
                f"Subject: {msg.subject}\n"
                f"Date: {msg.created_at or msg.received_at}\n"
                f"---\n{body}"
            )
        except DeadSimpleError as e:
            return self._handle_error(e)


class ReplyToEmailTool(_DSEBaseTool):
    """Reply to an email."""

    name: str = "reply_to_email"
    description: str = (
        "Reply to an email. Threading is handled automatically. "
        "Input should include inbox_id, message_id, and body."
    )

    def _run(self, inbox_id: str, message_id: str, body: str, **kwargs: Any) -> str:
        try:
            result = self.client.messages.reply(inbox_id, message_id, text_body=body)
            return f"Reply sent. Message ID: {result.message_id}"
        except DeadSimpleError as e:
            return self._handle_error(e)


class WaitForEmailTool(_DSEBaseTool):
    """Wait for a new inbound email (signup/verification flows)."""

    name: str = "wait_for_email"
    description: str = (
        "Wait for a NEW inbound email to arrive in an inbox — use for signup/2FA "
        "flows after triggering the email. Input: inbox_id, optional from_contains, "
        "subject_contains, timeout_seconds (default 60). Returns the email including "
        "any extracted verification code or magic link."
    )

    def _run(self, inbox_id: str, from_contains: str = "", subject_contains: str = "", timeout_seconds: int = 60, **kwargs: Any) -> str:
        try:
            msg = self.client.messages.wait_for(
                inbox_id, from_contains=from_contains, subject_contains=subject_contains, timeout=float(timeout_seconds),
            )
            return describe_email(msg, timeout_seconds)
        except DeadSimpleError as e:
            return self._handle_error(e)


class GetVerificationCodeTool(_DSEBaseTool):
    """Wait for a verification email and return the extracted code/link."""

    name: str = "get_verification_code"
    description: str = (
        "Wait for a verification/OTP email and return the extracted code and any magic "
        "link. Input: inbox_id, optional from_contains, timeout_seconds (default 60)."
    )

    def _run(self, inbox_id: str, from_contains: str = "", timeout_seconds: int = 60, **kwargs: Any) -> str:
        try:
            msg = self.client.messages.wait_for(inbox_id, from_contains=from_contains, timeout=float(timeout_seconds))
            return describe_verification(msg, timeout_seconds)
        except DeadSimpleError as e:
            return self._handle_error(e)


class CreateInboxTool(_DSEBaseTool):
    """Create a new email inbox."""

    name: str = "create_inbox"
    description: str = (
        "Create a new email inbox. "
        "Optionally provide a display_name (e.g. 'Support Bot')."
    )

    def _run(self, display_name: str = "", **kwargs: Any) -> str:
        try:
            inbox = self.client.inboxes.create(display_name=display_name)
            return f"Inbox created: {inbox.email} (ID: {inbox.inbox_id})"
        except DeadSimpleError as e:
            return self._handle_error(e)


class ListInboxesTool(_DSEBaseTool):
    """List all email inboxes."""

    name: str = "list_inboxes"
    description: str = "List all email inboxes in the account."

    def _run(self, **kwargs: Any) -> str:
        try:
            result = self.client.inboxes.list()
            if not result.inboxes:
                return "No inboxes found."
            lines = [f"{i.email} ({i.display_name or 'unnamed'}) — {i.message_count} messages" for i in result.inboxes]
            return "\n".join(lines)
        except DeadSimpleError as e:
            return self._handle_error(e)


class DeadSimpleEmailToolkit:
    """LangChain toolkit providing all Dead Simple Email tools.

    Usage::

        from deadsimple.integrations.langchain import DeadSimpleEmailToolkit

        toolkit = DeadSimpleEmailToolkit(api_key="dse_your_api_key")
        tools = toolkit.get_tools()
    """

    def __init__(self, api_key: str, **kwargs: Any):
        self.client = DeadSimple(api_key, **kwargs)

    def get_tools(self) -> list[BaseTool]:
        return [
            SendEmailTool(client=self.client),
            ReadEmailsTool(client=self.client),
            ReadEmailTool(client=self.client),
            ReplyToEmailTool(client=self.client),
            WaitForEmailTool(client=self.client),
            GetVerificationCodeTool(client=self.client),
            CreateInboxTool(client=self.client),
            ListInboxesTool(client=self.client),
        ]
