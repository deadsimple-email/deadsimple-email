"""Dead Simple Email API client — sync and async."""

from __future__ import annotations

from typing import Any

import httpx

from deadsimple.exceptions import (
    AuthenticationError,
    DeadSimpleError,
    NotFoundError,
    RateLimitError,
    ValidationError,
)
from deadsimple.types import (
    ApiKey,
    ApiKeyList,
    AttachmentUrl,
    BulkCreateResult,
    Domain,
    DomainList,
    DomainVerification,
    Draft,
    DraftList,
    Inbox,
    InboxList,
    Message,
    MessageFull,
    MessageList,
    SendResult,
    Thread,
    ThreadDetail,
    ThreadList,
    Usage,
    Webhook,
    WebhookList,
    Workspace,
    WorkspaceList,
)

__version__ = "0.1.1"
DEFAULT_BASE_URL = "https://api.deadsimple.email"


# ── HTTP layer ────────────────────────────────────────────────────────────────


def _handle_response(response: httpx.Response) -> Any:
    """Parse an API response, raising typed exceptions on errors."""
    if response.status_code == 204:
        return None

    try:
        body = response.json()
    except Exception:
        raise DeadSimpleError(f"Invalid response: {response.text}", status_code=response.status_code)

    if response.status_code >= 400:
        error = body.get("error", {})
        msg = error.get("message", "Unknown error")
        code = error.get("code", "")
        details = error.get("details", [])

        if response.status_code == 401:
            raise AuthenticationError(msg, code=code, status_code=401, details=details)
        if response.status_code == 400:
            raise ValidationError(msg, code=code, status_code=400, details=details)
        if response.status_code == 404:
            raise NotFoundError(msg, code=code, status_code=404, details=details)
        if response.status_code == 429:
            retry_after = int(response.headers.get("Retry-After", "60"))
            raise RateLimitError(msg, retry_after=retry_after, code=code, status_code=429, details=details)
        raise DeadSimpleError(msg, code=code, status_code=response.status_code, details=details)

    return body.get("data")


def _build_headers(api_key: str) -> dict[str, str]:
    return {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "User-Agent": f"deadsimple-python/{__version__}",
    }


# ── Sync client ───────────────────────────────────────────────────────────────


class DeadSimple:
    """Dead Simple Email API client (synchronous).

    Usage::

        from deadsimple import DeadSimple

        client = DeadSimple("dse_your_api_key")
        inbox = client.inboxes.create(display_name="Support Bot")
        client.messages.send(
            inbox_id=inbox.inbox_id,
            to="user@example.com",
            subject="Hello",
            text_body="Sent by an AI agent.",
        )
    """

    def __init__(self, api_key: str, *, base_url: str = DEFAULT_BASE_URL, timeout: float = 30.0):
        if not api_key:
            raise AuthenticationError("API key is required", code="missing_key")
        self._api_key = api_key
        self._base_url = base_url.rstrip("/")
        self._client = httpx.Client(
            base_url=self._base_url,
            headers=_build_headers(api_key),
            timeout=timeout,
        )

        self.inboxes = _Inboxes(self)
        self.messages = _Messages(self)
        self.threads = _Threads(self)
        self.drafts = _Drafts(self)
        self.webhooks = _Webhooks(self)
        self.domains = _Domains(self)
        self.api_keys = _ApiKeys(self)
        self.workspaces = _Workspaces(self)
        self.usage = _Usage(self)
        self.attachments = _Attachments(self)
        self.filters = _Filters(self)
        self.templates = _Templates(self)
        self.identity = _Identity(self)

    def _request(
        self,
        method: str,
        path: str,
        *,
        json: dict | None = None,
        params: dict | None = None,
        idempotency_key: str | None = None,
    ) -> Any:
        headers = {}
        if idempotency_key:
            headers["Idempotency-Key"] = idempotency_key
        response = self._client.request(method, path, json=json, params=params, headers=headers)
        return _handle_response(response)

    def close(self) -> None:
        """Close the underlying HTTP client."""
        self._client.close()

    def __enter__(self) -> DeadSimple:
        return self

    def __exit__(self, *args: Any) -> None:
        self.close()


# ── Async client ──────────────────────────────────────────────────────────────


class AsyncDeadSimple:
    """Dead Simple Email API client (async).

    Usage::

        from deadsimple import AsyncDeadSimple

        async with AsyncDeadSimple("dse_your_api_key") as client:
            inbox = await client.inboxes.create(display_name="Support Bot")
            await client.messages.send(
                inbox_id=inbox.inbox_id,
                to="user@example.com",
                subject="Hello",
                text_body="Sent by an AI agent.",
            )
    """

    def __init__(self, api_key: str, *, base_url: str = DEFAULT_BASE_URL, timeout: float = 30.0):
        if not api_key:
            raise AuthenticationError("API key is required", code="missing_key")
        self._api_key = api_key
        self._base_url = base_url.rstrip("/")
        self._client = httpx.AsyncClient(
            base_url=self._base_url,
            headers=_build_headers(api_key),
            timeout=timeout,
        )

        self.inboxes = _AsyncInboxes(self)
        self.messages = _AsyncMessages(self)
        self.threads = _AsyncThreads(self)
        self.drafts = _AsyncDrafts(self)
        self.webhooks = _AsyncWebhooks(self)
        self.domains = _AsyncDomains(self)
        self.api_keys = _AsyncApiKeys(self)
        self.workspaces = _AsyncWorkspaces(self)
        self.usage = _AsyncUsage(self)
        self.attachments = _AsyncAttachments(self)
        self.filters = _AsyncFilters(self)
        self.templates = _AsyncTemplates(self)
        self.identity = _AsyncIdentity(self)

    async def _request(
        self,
        method: str,
        path: str,
        *,
        json: dict | None = None,
        params: dict | None = None,
        idempotency_key: str | None = None,
    ) -> Any:
        headers = {}
        if idempotency_key:
            headers["Idempotency-Key"] = idempotency_key
        response = await self._client.request(method, path, json=json, params=params, headers=headers)
        return _handle_response(response)

    async def close(self) -> None:
        await self._client.aclose()

    async def __aenter__(self) -> AsyncDeadSimple:
        return self

    async def __aexit__(self, *args: Any) -> None:
        await self.close()


# ── Sync resource classes ─────────────────────────────────────────────────────


class _Inboxes:
    """Inbox management."""

    def __init__(self, client: DeadSimple):
        self._c = client

    def create(
        self,
        display_name: str = "",
        domain: str = "",
        local_part: str = "",
        tags: list[str] | None = None,
        *,
        idempotency_key: str | None = None,
    ) -> Inbox:
        """Create a new inbox. Returns inbox with email address."""
        body: dict[str, Any] = {}
        if display_name:
            body["display_name"] = display_name
        if domain:
            body["domain"] = domain
        if local_part:
            body["local_part"] = local_part
        if tags:
            body["tags"] = tags
        return Inbox.from_dict(self._c._request("POST", "/v1/inboxes", json=body, idempotency_key=idempotency_key))

    def bulk_create(self, inboxes: list[dict[str, Any]], *, idempotency_key: str | None = None) -> BulkCreateResult:
        """Create up to 100 inboxes in one call."""
        return BulkCreateResult.from_dict(
            self._c._request("POST", "/v1/inboxes/bulk", json={"inboxes": inboxes}, idempotency_key=idempotency_key)
        )

    def bulk_delete(self, inbox_ids: list[str]) -> dict[str, Any]:
        """Delete up to 100 inboxes in one call. Returns per-inbox results."""
        return self._c._request("DELETE", "/v1/inboxes/bulk", json={"inbox_ids": inbox_ids})

    def list(self, *, domain: str = "", status: str = "", tag: str = "", limit: int = 50, cursor: str = "") -> InboxList:
        """List inboxes with optional filters."""
        params: dict[str, str] = {"limit": str(limit)}
        if domain:
            params["domain"] = domain
        if status:
            params["status"] = status
        if tag:
            params["tag"] = tag
        if cursor:
            params["cursor"] = cursor
        return InboxList.from_dict(self._c._request("GET", "/v1/inboxes", params=params))

    def get(self, inbox_id: str) -> Inbox:
        """Get a single inbox."""
        return Inbox.from_dict(self._c._request("GET", f"/v1/inboxes/{inbox_id}"))

    def update(self, inbox_id: str, *, display_name: str | None = None, tags: list[str] | None = None, status: str | None = None) -> Inbox:
        """Update inbox properties."""
        body: dict[str, Any] = {}
        if display_name is not None:
            body["display_name"] = display_name
        if tags is not None:
            body["tags"] = tags
        if status is not None:
            body["status"] = status
        return Inbox.from_dict(self._c._request("PATCH", f"/v1/inboxes/{inbox_id}", json=body))

    def delete(self, inbox_id: str) -> None:
        """Delete an inbox and all its messages."""
        self._c._request("DELETE", f"/v1/inboxes/{inbox_id}")


class _Messages:
    """Email sending and reading."""

    def __init__(self, client: DeadSimple):
        self._c = client

    def send(
        self,
        inbox_id: str,
        to: list[str] | str,
        subject: str = "",
        text_body: str = "",
        html_body: str = "",
        *,
        cc: list[str] | None = None,
        bcc: list[str] | None = None,
        reply_to: str = "",
        headers: dict[str, str] | None = None,
        send_at: str | None = None,
        template_id: str | None = None,
        variables: dict[str, str] | None = None,
        attachments: list[Any] | None = None,
        images: list[Any] | None = None,
        in_reply_to: str | None = None,
        references: list[str] | None = None,
        calendar_invite: dict[str, Any] | None = None,
        idempotency_key: str | None = None,
    ) -> SendResult:
        """Send an email. Pass `send_at` to schedule, `template_id` + `variables` to use a template.

        `in_reply_to` threads this send onto an existing conversation. Pass
        either a `message_id` from this inbox or a raw Message-ID header; the
        Re: subject is still yours to set. Use it when you need a reply that
        also carries its own recipient list, otherwise `reply()` is simpler.

        `images` render in the body; `attachments` arrive as downloads. Both
        accept a file path, an http(s) URL, raw bytes, or a reference returned
        by `client.attachments.upload()`::

            client.messages.send(
                inbox_id=inbox.inbox_id,
                to="contractor@example.com",
                subject="Photos - 124 Lakeshore Dr",
                text_body="Photos of the four jobs below.",
                images=["./door.jpg", "./ceiling.jpg"],
            )

        Files are uploaded before the send, so size is not limited by the
        request body.

        `calendar_invite` makes the message a real invitation, with
        Accept/Decline in the recipient's mail client and the event on their
        calendar. Attaching an .ics file does not do this; the event has to
        ride in the body, which is what this builds::

            r = client.messages.send(
                inbox_id=inbox.inbox_id,
                to="tommy@example.com",
                subject="Roof inspection Tuesday",
                text_body="Proposing Tuesday at 3.",
                calendar_invite={
                    "title": "Roof inspection - 124 Lakeshore Dr",
                    "start": "2026-09-15T15:00:00",
                    "timezone": "America/New_York",
                    "duration_minutes": 45,
                    "location": "124 Lakeshore Dr",
                },
            )
            r.calendar_uid  # keep this to reschedule or cancel later

        Attendees default to `to` + `cc`. Times need a zone: either an offset,
        a trailing "Z", or `timezone`. To change a meeting, send again with the
        same `uid` and a higher `sequence`; to call it off, add
        `"method": "CANCEL"`.
        """
        if isinstance(to, str):
            to = [to]
        body: dict[str, Any] = {"to": to}
        prepared = self._c.attachments._prepare(attachments, images)
        if prepared:
            body["attachments"] = prepared
        if subject:
            body["subject"] = subject
        if text_body:
            body["text_body"] = text_body
        if html_body:
            body["html_body"] = html_body
        if cc:
            body["cc"] = cc
        if bcc:
            body["bcc"] = bcc
        if reply_to:
            body["reply_to"] = reply_to
        if headers:
            body["headers"] = headers
        if send_at:
            body["send_at"] = send_at
        if template_id:
            body["template_id"] = template_id
        if variables:
            body["variables"] = variables
        if in_reply_to:
            body["in_reply_to"] = in_reply_to
        if references:
            body["references"] = references
        if calendar_invite:
            body["calendar_invite"] = calendar_invite
        return SendResult.from_dict(
            self._c._request("POST", f"/v1/inboxes/{inbox_id}/messages", json=body, idempotency_key=idempotency_key)
        )

    def list(self, inbox_id: str, *, q: str = "", direction: str = "", from_email: str = "",
             labels: list[str] | str | None = None, limit: int = 50, cursor: str = "") -> MessageList:
        """List messages in an inbox, newest first. Supports search via `q`.

        `labels` narrows to messages carrying every label given, so a sweep for
        unanswered mail is one call:
        `client.messages.list(inbox_id, labels=["state:unreplied"])`.
        """
        params: dict[str, str] = {"limit": str(limit)}
        if labels:
            params["labels"] = labels if isinstance(labels, str) else ",".join(labels)
        if q:
            params["q"] = q
        if direction:
            params["direction"] = direction
        if from_email:
            params["from"] = from_email
        if cursor:
            params["cursor"] = cursor
        return MessageList.from_dict(self._c._request("GET", f"/v1/inboxes/{inbox_id}/messages", params=params))

    def get(self, inbox_id: str, message_id: str) -> MessageFull:
        """Get a single message with full body and headers."""
        return MessageFull.from_dict(self._c._request("GET", f"/v1/inboxes/{inbox_id}/messages/{message_id}"))

    def _reply_body(self, text_body: str, html_body: str, to, cc, bcc,
                    attachments, images, send_at=None, calendar_invite=None) -> dict[str, Any]:
        body: dict[str, Any] = {}
        if calendar_invite:
            body["calendar_invite"] = calendar_invite
        if send_at:
            body["send_at"] = send_at
        if text_body:
            body["text_body"] = text_body
        if html_body:
            body["html_body"] = html_body
        if to:
            body["to"] = [to] if isinstance(to, str) else list(to)
        if cc:
            body["cc"] = [cc] if isinstance(cc, str) else list(cc)
        if bcc:
            body["bcc"] = [bcc] if isinstance(bcc, str) else list(bcc)
        prepared = self._c.attachments._prepare(attachments, images)
        if prepared:
            body["attachments"] = prepared
        return body

    def reply(self, inbox_id: str, message_id: str, text_body: str = "", html_body: str = "",
              *, to: list[str] | str | None = None,
              cc: list[str] | str | None = None,
              bcc: list[str] | str | None = None,
              send_at: str | None = None,
              attachments: list[Any] | None = None,
              images: list[Any] | None = None,
              calendar_invite: dict[str, Any] | None = None) -> SendResult:
        """Reply to a message. Threading headers are set automatically.

        Recipients default to the other side of the conversation: the sender
        for a message you received, and the original recipients for one you
        sent, so nudging your own unanswered email reaches the right people
        rather than looping back to you. `to` overrides that; `cc` and `bcc`
        add addresses, which is how you keep a standing CC on every reply.
        """
        body = self._reply_body(text_body, html_body, to, cc, bcc, attachments, images,
                                send_at, calendar_invite)
        return SendResult.from_dict(self._c._request("POST", f"/v1/inboxes/{inbox_id}/messages/{message_id}/reply", json=body))

    def reply_all(self, inbox_id: str, message_id: str, text_body: str = "", html_body: str = "",
                  *, to: list[str] | str | None = None,
                  cc: list[str] | str | None = None,
                  bcc: list[str] | str | None = None,
                  send_at: str | None = None,
                  attachments: list[Any] | None = None,
                  images: list[Any] | None = None,
                  calendar_invite: dict[str, Any] | None = None) -> SendResult:
        """Reply-all to a message. `cc` adds to the original participants."""
        body = self._reply_body(text_body, html_body, to, cc, bcc, attachments, images,
                                send_at, calendar_invite)
        return SendResult.from_dict(self._c._request("POST", f"/v1/inboxes/{inbox_id}/messages/{message_id}/reply-all", json=body))

    def forward(self, inbox_id: str, message_id: str, to: list[str] | str, text_body: str = "",
                html_body: str = "", *, attachments: list[Any] | None = None,
                images: list[Any] | None = None) -> SendResult:
        """Forward a message to new recipients."""
        if isinstance(to, str):
            to = [to]
        body: dict[str, Any] = {"to": to}
        if text_body:
            body["text_body"] = text_body
        if html_body:
            body["html_body"] = html_body
        prepared = self._c.attachments._prepare(attachments, images)
        if prepared:
            body["attachments"] = prepared
        return SendResult.from_dict(self._c._request("POST", f"/v1/inboxes/{inbox_id}/messages/{message_id}/forward", json=body))

    def wait_for(
        self,
        inbox_id: str,
        *,
        from_contains: str = "",
        subject_contains: str = "",
        timeout: float = 60.0,
        poll_interval: float = 3.0,
    ) -> MessageFull | None:
        """Block until a *new* inbound message matching the filters arrives.

        Ideal for signup/OTP flows: trigger the action, then wait for the email.
        Only messages that arrive after this call are considered. Returns the full
        message (including `extracted` verification data), or None on timeout.

        Args:
            inbox_id: Inbox to watch.
            from_contains: Case-insensitive substring the sender must contain.
            subject_contains: Case-insensitive substring the subject must contain.
            timeout: Max seconds to wait.
            poll_interval: Seconds between polls.
        """
        import time

        deadline = time.monotonic() + timeout
        seen = {m.message_id for m in self.list(inbox_id, direction="inbound", limit=50).messages}
        while True:
            for m in self.list(inbox_id, direction="inbound", limit=50).messages:
                if m.message_id in seen:
                    continue
                if from_contains and from_contains.lower() not in (m.from_email or "").lower():
                    continue
                if subject_contains and subject_contains.lower() not in (m.subject or "").lower():
                    continue
                return self.get(inbox_id, m.message_id)
            if time.monotonic() >= deadline:
                return None
            time.sleep(poll_interval)

    def get_verification(self, inbox_id: str, *, from_contains: str = "", since: str = "", window: int = 20) -> dict:
        """Return the latest OTP / magic link in this inbox in a single call (non-blocking).

        Wraps GET /v1/inboxes/{id}/verification. Returns a dict with `found` plus
        `verification_code`, `magic_link_url`, `expires_in`, and the source
        message fields. `found` is False if no code has arrived yet.
        """
        params: dict = {"window": str(window)}
        if from_contains:
            params["from_contains"] = from_contains
        if since:
            params["since"] = since
        return self._c._request("GET", f"/v1/inboxes/{inbox_id}/verification", params=params)

    def wait_for_verification(
        self,
        inbox_id: str,
        *,
        from_contains: str = "",
        since: str = "",
        timeout: float = 60.0,
        poll_interval: float = 3.0,
    ) -> dict | None:
        """Block until a verification code / magic link arrives, then return it.

        The one-call agent self-onboarding helper: trigger the signup, then wait
        for the OTP. Returns the verification dict, or None on timeout. Pass
        `since` (an ISO-8601 timestamp taken before you triggered the signup) to
        ignore any stale code already sitting in the inbox.
        """
        import time

        deadline = time.monotonic() + timeout
        while True:
            result = self.get_verification(inbox_id, from_contains=from_contains, since=since)
            if result.get("found"):
                return result
            if time.monotonic() >= deadline:
                return None
            time.sleep(poll_interval)


class _Threads:
    """Conversation threads."""

    def __init__(self, client: DeadSimple):
        self._c = client

    def list_all(self, *, inbox_id: str | None = None, labels: str | None = None, limit: int = 50, offset: int = 0) -> ThreadList:
        """List threads across all inboxes (org-wide). Useful for supervisor agents."""
        params: dict = {"limit": str(limit), "offset": str(offset)}
        if inbox_id:
            params["inbox_id"] = inbox_id
        if labels:
            params["labels"] = labels
        return ThreadList.from_dict(self._c._request("GET", "/v1/threads", params=params))

    def list(self, inbox_id: str, *, limit: int = 50, offset: int = 0) -> ThreadList:
        """List threads in an inbox, newest activity first."""
        return ThreadList.from_dict(
            self._c._request("GET", f"/v1/inboxes/{inbox_id}/threads", params={"limit": str(limit), "offset": str(offset)})
        )

    def get(self, inbox_id: str, thread_id: str) -> ThreadDetail:
        """Get all messages in a thread."""
        return ThreadDetail.from_dict(self._c._request("GET", f"/v1/inboxes/{inbox_id}/threads/{thread_id}"))

    def get_attachments(self, inbox_id: str, thread_id: str) -> dict:
        """Get all attachments across every message in a thread."""
        return self._c._request("GET", f"/v1/inboxes/{inbox_id}/threads/{thread_id}/attachments")


class _Drafts:
    """Draft email management (human-in-the-loop review)."""

    def __init__(self, client: DeadSimple):
        self._c = client

    def create(self, inbox_id: str, *, to: list[str] | str = "", subject: str = "", text_body: str = "", html_body: str = "", cc: list[str] | None = None, bcc: list[str] | None = None, reply_to_message_id: str | None = None) -> Draft:
        """Create a draft email for later review and sending."""
        if isinstance(to, str) and to:
            to = [to]
        body: dict[str, Any] = {}
        if to:
            body["to"] = to
        if subject:
            body["subject"] = subject
        if text_body:
            body["text_body"] = text_body
        if html_body:
            body["html_body"] = html_body
        if cc:
            body["cc"] = cc
        if bcc:
            body["bcc"] = bcc
        if reply_to_message_id:
            body["reply_to_message_id"] = reply_to_message_id
        return Draft.from_dict(self._c._request("POST", f"/v1/inboxes/{inbox_id}/drafts", json=body))

    def list(self, inbox_id: str) -> DraftList:
        """List drafts for an inbox."""
        return DraftList.from_dict(self._c._request("GET", f"/v1/inboxes/{inbox_id}/drafts"))

    def get(self, inbox_id: str, draft_id: str) -> Draft:
        """Get a single draft."""
        return Draft.from_dict(self._c._request("GET", f"/v1/inboxes/{inbox_id}/drafts/{draft_id}"))

    def update(self, inbox_id: str, draft_id: str, **fields: Any) -> Draft:
        """Update a draft. Pass any of: to, cc, bcc, subject, text_body, html_body."""
        return Draft.from_dict(self._c._request("PUT", f"/v1/inboxes/{inbox_id}/drafts/{draft_id}", json=fields))

    def send(self, inbox_id: str, draft_id: str) -> SendResult:
        """Send a draft — converts it to a real email and deletes the draft."""
        return SendResult.from_dict(self._c._request("POST", f"/v1/inboxes/{inbox_id}/drafts/{draft_id}/send"))

    def delete(self, inbox_id: str, draft_id: str) -> None:
        """Delete a draft."""
        self._c._request("DELETE", f"/v1/inboxes/{inbox_id}/drafts/{draft_id}")


class _Webhooks:
    """Webhook management."""

    def __init__(self, client: DeadSimple):
        self._c = client

    def create(self, url: str, events: list[str], description: str = "", *, headers: dict[str, str] | None = None, idempotency_key: str | None = None) -> Webhook:
        """Register a webhook. Returns signing secret (shown once).

        `headers` are sent on every delivery attempt (and every retry), for
        endpoints that require their own auth, e.g.
        `headers={"Authorization": "Bearer ..."}`. Values are write-only: the
        API masks them in every response.
        """
        body: dict[str, Any] = {"url": url, "events": events}
        if description:
            body["description"] = description
        if headers:
            body["headers"] = headers
        return Webhook.from_dict(self._c._request("POST", "/v1/webhooks", json=body, idempotency_key=idempotency_key))

    def list(self) -> WebhookList:
        """List all webhooks."""
        return WebhookList.from_dict(self._c._request("GET", "/v1/webhooks"))

    def delete(self, webhook_id: str) -> None:
        """Delete a webhook."""
        self._c._request("DELETE", f"/v1/webhooks/{webhook_id}")

    def get_headers(self, webhook_id: str) -> dict[str, str]:
        """Custom delivery header names for a webhook (values masked)."""
        return self._c._request("GET", f"/v1/webhooks/{webhook_id}/headers").get("headers", {})

    def set_headers(self, webhook_id: str, headers: dict[str, str]) -> dict[str, str]:
        """Replace the custom delivery headers. Pass `{}` to clear them."""
        resp = self._c._request("PUT", f"/v1/webhooks/{webhook_id}/headers", json={"headers": headers})
        return resp.get("headers", {})


class _Domains:
    """Custom domain management."""

    def __init__(self, client: DeadSimple):
        self._c = client

    def add(self, domain: str) -> Domain:
        """Add a custom domain. Returns DNS records to configure."""
        return Domain.from_dict(self._c._request("POST", "/v1/domains", json={"domain": domain}))

    def list(self) -> DomainList:
        """List custom domains."""
        return DomainList.from_dict(self._c._request("GET", "/v1/domains"))

    def verify(self, domain_id: str) -> DomainVerification:
        """Check DNS verification status."""
        return DomainVerification.from_dict(self._c._request("GET", f"/v1/domains/{domain_id}/verify"))

    def delete(self, domain_id: str) -> None:
        """Remove a custom domain."""
        self._c._request("DELETE", f"/v1/domains/{domain_id}")


class _ApiKeys:
    """API key management."""

    def __init__(self, client: DeadSimple):
        self._c = client

    def create(self, name: str, permissions: list[str] | None = None) -> ApiKey:
        """Create a new API key. The key value is only returned once."""
        body: dict[str, Any] = {"name": name}
        if permissions:
            body["permissions"] = permissions
        return ApiKey.from_dict(self._c._request("POST", "/v1/api-keys", json=body))

    def list(self) -> ApiKeyList:
        """List API keys (secrets are masked)."""
        return ApiKeyList.from_dict(self._c._request("GET", "/v1/api-keys"))

    def delete(self, key_id: str) -> None:
        """Revoke an API key."""
        self._c._request("DELETE", f"/v1/api-keys/{key_id}")


class _Workspaces:
    """Multi-tenant workspace management."""

    def __init__(self, client: DeadSimple):
        self._c = client

    def create(self, name: str, description: str = "", *, idempotency_key: str | None = None) -> Workspace:
        """Create an isolated workspace with its own scoped API key."""
        body: dict[str, Any] = {"name": name}
        if description:
            body["description"] = description
        return Workspace.from_dict(self._c._request("POST", "/v1/workspaces", json=body, idempotency_key=idempotency_key))

    def list(self) -> WorkspaceList:
        """List all workspaces."""
        return WorkspaceList.from_dict(self._c._request("GET", "/v1/workspaces"))

    def get(self, workspace_id: str) -> Workspace:
        """Get a single workspace."""
        return Workspace.from_dict(self._c._request("GET", f"/v1/workspaces/{workspace_id}"))

    def update(self, workspace_id: str, *, name: str | None = None, description: str | None = None) -> Workspace:
        """Update workspace properties."""
        body: dict[str, Any] = {}
        if name is not None:
            body["name"] = name
        if description is not None:
            body["description"] = description
        return Workspace.from_dict(self._c._request("PUT", f"/v1/workspaces/{workspace_id}", json=body))

    def delete(self, workspace_id: str) -> None:
        """Delete a workspace and all its data."""
        self._c._request("DELETE", f"/v1/workspaces/{workspace_id}")


class _Usage:
    """Account usage metrics."""

    def __init__(self, client: DeadSimple):
        self._c = client

    def get(self) -> Usage:
        """Get current usage: inboxes, emails, webhooks, domains."""
        return Usage.from_dict(self._c._request("GET", "/v1/usage"))


# ── Outbound attachment helpers ──────────────────────────────────────────────

# Hosts that must never be fetched when resolving an image URL. The same code
# runs inside the hosted MCP server, where the URL comes from whatever an agent
# was told to send — so a URL fetch there is a request an attacker can aim at
# our own network.
_BLOCKED_URL_HOSTS = ("169.254.169.254", "metadata.google.internal", "localhost")

MAX_FETCH_BYTES = 25 * 1024 * 1024


def _is_url(value: str) -> bool:
    return isinstance(value, str) and value.lower().startswith(("http://", "https://"))


def _direct_download_url(url: str) -> str:
    """Rewrite a Google Drive share link to its direct-download form.

    A .../file/d/<id>/view link serves an HTML viewer page, so fetching it
    verbatim attaches a web page named "view" instead of the photo.
    """
    import re

    match = re.match(r"https?://drive\.google\.com/file/d/([^/]+)", url)
    if match:
        return f"https://drive.google.com/uc?export=download&id={match.group(1)}"
    match = re.match(r"https?://drive\.google\.com/open\?id=([^&]+)", url)
    if match:
        return f"https://drive.google.com/uc?export=download&id={match.group(1)}"
    return url


def _fetch_url_bytes(url: str, *, expect_image: bool = False) -> tuple[bytes, str, str]:
    """Download an image by URL. Returns (bytes, filename, content_type)."""
    url = _direct_download_url(url)
    import ipaddress
    import socket
    from urllib.parse import unquote, urlparse

    parsed = urlparse(url)
    host = (parsed.hostname or "").lower()
    if not host or host in _BLOCKED_URL_HOSTS:
        raise ValidationError(f"Refusing to fetch {url!r}")
    try:
        for info in socket.getaddrinfo(host, None):
            ip = ipaddress.ip_address(info[4][0])
            if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved:
                raise ValidationError(
                    f"Refusing to fetch {url!r}: it resolves to a private address."
                )
    except socket.gaierror:
        raise ValidationError(f"Could not resolve the host in {url!r}") from None

    with httpx.Client(timeout=30, follow_redirects=False) as fetch:
        resp = fetch.get(url)
        resp.raise_for_status()
        data = resp.content
    if len(data) > MAX_FETCH_BYTES:
        raise ValidationError(f"{url} is larger than {MAX_FETCH_BYTES // (1024 * 1024)} MB")

    filename = unquote(parsed.path.rsplit("/", 1)[-1]) or "image"
    content_type = resp.headers.get("content-type", "").split(";")[0].strip()

    # A share link that still returns HTML is a permissions page, not a file.
    # Attaching it silently would send the recipient a login screen.
    if expect_image and not content_type.startswith("image/"):
        raise ValidationError(
            f"{url} returned {content_type or 'no content type'} rather than an image. "
            "If it is a Google Drive link, the file must be shared as 'anyone with the "
            "link'; otherwise pass a direct image URL or a local path."
        )
    return data, filename, content_type or "application/octet-stream"


def _read_source(source: Any, *, expect_image: bool = False) -> tuple[bytes, str, str]:
    """Normalize a path, URL or raw bytes into (bytes, filename, content_type)."""
    import mimetypes
    from pathlib import Path

    if isinstance(source, (bytes, bytearray)):
        return bytes(source), "attachment", "application/octet-stream"
    if _is_url(str(source)):
        return _fetch_url_bytes(str(source), expect_image=expect_image)

    path = Path(str(source)).expanduser()
    if not path.is_file():
        raise ValidationError(
            f"{source!r} is not a readable file, and does not look like a URL."
        )
    guessed, _ = mimetypes.guess_type(path.name)
    return path.read_bytes(), path.name, guessed or "application/octet-stream"


class _Attachments:
    """Attachment uploads and downloads."""

    def __init__(self, client: DeadSimple):
        self._c = client

    def get_url(self, inbox_id: str, message_id: str, attachment_id: str) -> AttachmentUrl:
        """Get a time-limited signed download URL for an attachment."""
        return AttachmentUrl.from_dict(
            self._c._request("GET", f"/v1/inboxes/{inbox_id}/messages/{message_id}/attachments/{attachment_id}")
        )

    def upload(self, source: Any, *, filename: str | None = None,
               content_type: str | None = None, inline: bool = False) -> dict[str, Any]:
        """Upload a file, URL or bytes and return an attachment reference.

        The bytes go straight to storage rather than through the send request,
        which is what makes real photos possible: a send call cannot carry more
        than a few MB. The returned reference can be attached to as many
        messages as you like without re-uploading.

        Pass `inline=True` for an image that should render in the body.
        """
        data, guessed_name, guessed_type = _read_source(source, expect_image=inline)
        name = filename or guessed_name
        ctype = content_type or guessed_type

        staged = self._c._request("POST", "/v1/attachments",
                                  json={"filename": name, "content_type": ctype,
                                        "size": len(data)})
        with httpx.Client(timeout=120) as put:
            resp = put.put(staged["upload_url"], content=data,
                           headers={"Content-Type": ctype})
            resp.raise_for_status()

        ref: dict[str, Any] = {"attachment_id": staged["attachment_id"]}
        if inline:
            ref["inline"] = True
        return ref

    def _prepare(self, attachments: list[Any] | None,
                 images: list[Any] | None = None) -> list[dict[str, Any]]:
        """Normalize send()'s attachments/images into API attachment entries."""
        prepared: list[dict[str, Any]] = []
        for source, inline in [(a, False) for a in (attachments or [])] + \
                              [(i, True) for i in (images or [])]:
            if isinstance(source, dict):
                entry = dict(source)
                if inline:
                    entry["inline"] = True
                prepared.append(entry)
            else:
                prepared.append(self.upload(source, inline=inline))
        return prepared


class _Filters:
    """Allowlist / blocklist management."""

    def __init__(self, client: DeadSimple):
        self._c = client

    def create(self, inbox_id: str, *, action: str, criteria: str, value: str, description: str = "") -> dict[str, Any]:
        """Add a filter rule. action: 'block' or 'allow'. criteria: 'email', 'domain', 'pattern', or 'keyword'."""
        body: dict[str, Any] = {"action": action, "criteria": criteria, "value": value}
        if description:
            body["description"] = description
        return self._c._request("POST", f"/v1/inboxes/{inbox_id}/filters", json=body)

    def list(self, inbox_id: str) -> dict[str, Any]:
        """List all filter rules for an inbox."""
        return self._c._request("GET", f"/v1/inboxes/{inbox_id}/filters")

    def delete(self, inbox_id: str, filter_id: str) -> None:
        """Remove a filter rule."""
        self._c._request("DELETE", f"/v1/inboxes/{inbox_id}/filters/{filter_id}")


class _Templates:
    """Email template management."""

    def __init__(self, client: DeadSimple):
        self._c = client

    def create(self, name: str, *, subject: str = "", text_body: str = "", html_body: str = "") -> dict[str, Any]:
        """Create a reusable email template with {{variable}} substitution."""
        body: dict[str, Any] = {"name": name}
        if subject:
            body["subject"] = subject
        if text_body:
            body["text_body"] = text_body
        if html_body:
            body["html_body"] = html_body
        return self._c._request("POST", "/v1/templates", json=body)

    def list(self) -> dict[str, Any]:
        """List all templates."""
        return self._c._request("GET", "/v1/templates")

    def get(self, template_id: str) -> dict[str, Any]:
        """Get a single template."""
        return self._c._request("GET", f"/v1/templates/{template_id}")

    def update(self, template_id: str, **fields: Any) -> dict[str, Any]:
        """Update a template. Pass any of: name, subject, text_body, html_body."""
        return self._c._request("PUT", f"/v1/templates/{template_id}", json=fields)

    def delete(self, template_id: str) -> None:
        """Delete a template."""
        self._c._request("DELETE", f"/v1/templates/{template_id}")

class _Identity:
    """Sign in with Dead Simple — the OIDC provider at https://id.deadsimple.email.

    An agent's inbox is its login. Any app that accepts a generic OpenID
    Connect provider can let the agent sign up and sign in; the app receives a
    stable ``sub`` (the inbox_id), the inbox address, and, for registered
    clients, the verified human owner behind the agent.
    """

    ISSUER = "https://id.deadsimple.email"

    def __init__(self, client: DeadSimple):
        self._c = client

    def sign_in(self, inbox_id: str, authorization_url: str, *, follow: bool = True) -> dict[str, Any]:
        """Sign in to an app with this inbox.

        ``authorization_url`` is the URL the app would send a browser to
        (``https://id.deadsimple.email/authorize?...``). Returns the redirect
        the app expects; with ``follow=True`` the redirect is fetched so the
        app completes the login, and ``final_url`` / ``final_status`` report
        where that landed.
        """
        out = self._c._request(
            "POST", f"/v1/inboxes/{inbox_id}/identity/sign-in", json={"authorization_url": authorization_url}
        )
        if follow:
            resp = httpx.get(out["redirect_to"], follow_redirects=True, timeout=30.0)
            out["final_url"] = str(resp.url)
            out["final_status"] = resp.status_code
        return out

    def enroll_key(self, inbox_id: str, *, public_key: dict[str, Any] | str, name: str = "") -> dict[str, Any]:
        """Enroll a P-256 public key (JWK dict or PEM) so the agent can sign in with a signed assertion."""
        body: dict[str, Any] = {"public_key": public_key}
        if name:
            body["name"] = name
        return self._c._request("POST", f"/v1/inboxes/{inbox_id}/identity/keys", json=body)

    def list_keys(self, inbox_id: str) -> dict[str, Any]:
        return self._c._request("GET", f"/v1/inboxes/{inbox_id}/identity/keys")

    def delete_key(self, inbox_id: str, kid: str) -> None:
        self._c._request("DELETE", f"/v1/inboxes/{inbox_id}/identity/keys/{kid}")

    def connections(self, inbox_id: str) -> dict[str, Any]:
        """Apps this inbox has signed in to."""
        return self._c._request("GET", f"/v1/inboxes/{inbox_id}/identity/connections")

    def register_client(
        self,
        client_name: str,
        redirect_uris: list[str],
        *,
        client_uri: str = "",
        logo_uri: str = "",
        scope: str = "openid email profile owner_email org offline_access",
        token_endpoint_auth_method: str = "client_secret_basic",
    ) -> dict[str, Any]:
        """Register your app as a relying party. The client_secret is returned once."""
        body: dict[str, Any] = {
            "client_name": client_name,
            "redirect_uris": redirect_uris,
            "scope": scope,
            "token_endpoint_auth_method": token_endpoint_auth_method,
        }
        if client_uri:
            body["client_uri"] = client_uri
        if logo_uri:
            body["logo_uri"] = logo_uri
        return self._c._request("POST", "/v1/identity/clients", json=body)

    def list_clients(self) -> dict[str, Any]:
        return self._c._request("GET", "/v1/identity/clients")

    def delete_client(self, client_id: str) -> None:
        self._c._request("DELETE", f"/v1/identity/clients/{client_id}")

    @staticmethod
    def make_assertion(inbox_id: str, private_key_pem: str, kid: str, *, client_id: str = "",
                       code_challenge: str = "", nonce: str = "", ttl: int = 120) -> str:
        """Build the ES256 assertion for the key-based sign-in path.

        Requires ``pyjwt[crypto]``. Optional bindings (client_id, code_challenge,
        nonce) are checked against the authorization request when present.
        """
        import time as _time
        import uuid as _uuid

        try:
            import jwt as _jwt
        except ImportError as exc:  # pragma: no cover
            raise RuntimeError("pip install 'pyjwt[crypto]' to build assertions") from exc
        now = int(_time.time())
        claims: dict[str, Any] = {
            "iss": inbox_id, "sub": inbox_id, "aud": _Identity.ISSUER,
            "iat": now, "exp": now + min(ttl, 600), "jti": str(_uuid.uuid4()),
        }
        if client_id:
            claims["client_id"] = client_id
        if code_challenge:
            claims["code_challenge"] = code_challenge
        if nonce:
            claims["nonce"] = nonce
        return _jwt.encode(claims, private_key_pem, algorithm="ES256", headers={"kid": kid})



# ── Async resource classes ────────────────────────────────────────────────────
# Mirror the sync API exactly, but all methods are async.


class _AsyncInboxes:
    def __init__(self, client: AsyncDeadSimple):
        self._c = client

    async def create(self, display_name: str = "", domain: str = "", local_part: str = "", tags: list[str] | None = None, *, idempotency_key: str | None = None) -> Inbox:
        body: dict[str, Any] = {}
        if display_name:
            body["display_name"] = display_name
        if domain:
            body["domain"] = domain
        if local_part:
            body["local_part"] = local_part
        if tags:
            body["tags"] = tags
        return Inbox.from_dict(await self._c._request("POST", "/v1/inboxes", json=body, idempotency_key=idempotency_key))

    async def bulk_create(self, inboxes: list[dict[str, Any]], *, idempotency_key: str | None = None) -> BulkCreateResult:
        return BulkCreateResult.from_dict(await self._c._request("POST", "/v1/inboxes/bulk", json={"inboxes": inboxes}, idempotency_key=idempotency_key))

    async def bulk_delete(self, inbox_ids: list[str]) -> dict[str, Any]:
        return await self._c._request("DELETE", "/v1/inboxes/bulk", json={"inbox_ids": inbox_ids})

    async def list(self, *, domain: str = "", status: str = "", tag: str = "", limit: int = 50, cursor: str = "") -> InboxList:
        params: dict[str, str] = {"limit": str(limit)}
        if domain:
            params["domain"] = domain
        if status:
            params["status"] = status
        if tag:
            params["tag"] = tag
        if cursor:
            params["cursor"] = cursor
        return InboxList.from_dict(await self._c._request("GET", "/v1/inboxes", params=params))

    async def get(self, inbox_id: str) -> Inbox:
        return Inbox.from_dict(await self._c._request("GET", f"/v1/inboxes/{inbox_id}"))

    async def update(self, inbox_id: str, *, display_name: str | None = None, tags: list[str] | None = None, status: str | None = None) -> Inbox:
        body: dict[str, Any] = {}
        if display_name is not None:
            body["display_name"] = display_name
        if tags is not None:
            body["tags"] = tags
        if status is not None:
            body["status"] = status
        return Inbox.from_dict(await self._c._request("PATCH", f"/v1/inboxes/{inbox_id}", json=body))

    async def delete(self, inbox_id: str) -> None:
        await self._c._request("DELETE", f"/v1/inboxes/{inbox_id}")


class _AsyncMessages:
    def __init__(self, client: AsyncDeadSimple):
        self._c = client

    async def send(self, inbox_id: str, to: list[str] | str, subject: str, text_body: str = "", html_body: str = "", *, cc: list[str] | None = None, bcc: list[str] | None = None, reply_to: str = "", headers: dict[str, str] | None = None, idempotency_key: str | None = None) -> SendResult:
        if isinstance(to, str):
            to = [to]
        body: dict[str, Any] = {"to": to, "subject": subject}
        if text_body:
            body["text_body"] = text_body
        if html_body:
            body["html_body"] = html_body
        if cc:
            body["cc"] = cc
        if bcc:
            body["bcc"] = bcc
        if reply_to:
            body["reply_to"] = reply_to
        if headers:
            body["headers"] = headers
        return SendResult.from_dict(await self._c._request("POST", f"/v1/inboxes/{inbox_id}/messages", json=body, idempotency_key=idempotency_key))

    async def list(self, inbox_id: str, *, q: str = "", direction: str = "", from_email: str = "", limit: int = 50, cursor: str = "") -> MessageList:
        params: dict[str, str] = {"limit": str(limit)}
        if q:
            params["q"] = q
        if direction:
            params["direction"] = direction
        if from_email:
            params["from"] = from_email
        if cursor:
            params["cursor"] = cursor
        return MessageList.from_dict(await self._c._request("GET", f"/v1/inboxes/{inbox_id}/messages", params=params))

    async def get(self, inbox_id: str, message_id: str) -> MessageFull:
        return MessageFull.from_dict(await self._c._request("GET", f"/v1/inboxes/{inbox_id}/messages/{message_id}"))

    async def reply(self, inbox_id: str, message_id: str, text_body: str = "", html_body: str = "") -> SendResult:
        body: dict[str, Any] = {}
        if text_body:
            body["text_body"] = text_body
        if html_body:
            body["html_body"] = html_body
        return SendResult.from_dict(await self._c._request("POST", f"/v1/inboxes/{inbox_id}/messages/{message_id}/reply", json=body))

    async def reply_all(self, inbox_id: str, message_id: str, text_body: str = "", html_body: str = "") -> SendResult:
        body: dict[str, Any] = {}
        if text_body:
            body["text_body"] = text_body
        if html_body:
            body["html_body"] = html_body
        return SendResult.from_dict(await self._c._request("POST", f"/v1/inboxes/{inbox_id}/messages/{message_id}/reply-all", json=body))

    async def forward(self, inbox_id: str, message_id: str, to: list[str] | str, text_body: str = "", html_body: str = "") -> SendResult:
        if isinstance(to, str):
            to = [to]
        body: dict[str, Any] = {"to": to}
        if text_body:
            body["text_body"] = text_body
        if html_body:
            body["html_body"] = html_body
        return SendResult.from_dict(await self._c._request("POST", f"/v1/inboxes/{inbox_id}/messages/{message_id}/forward", json=body))

    async def wait_for(self, inbox_id: str, *, from_contains: str = "", subject_contains: str = "", timeout: float = 60.0, poll_interval: float = 3.0) -> MessageFull | None:
        """Block until a new inbound message matching the filters arrives, or None on timeout."""
        import asyncio
        import time

        deadline = time.monotonic() + timeout
        seen = {m.message_id for m in (await self.list(inbox_id, direction="inbound", limit=50)).messages}
        while True:
            for m in (await self.list(inbox_id, direction="inbound", limit=50)).messages:
                if m.message_id in seen:
                    continue
                if from_contains and from_contains.lower() not in (m.from_email or "").lower():
                    continue
                if subject_contains and subject_contains.lower() not in (m.subject or "").lower():
                    continue
                return await self.get(inbox_id, m.message_id)
            if time.monotonic() >= deadline:
                return None
            await asyncio.sleep(poll_interval)


class _AsyncThreads:
    def __init__(self, client: AsyncDeadSimple):
        self._c = client

    async def list_all(self, *, inbox_id: str | None = None, labels: str | None = None, limit: int = 50, offset: int = 0) -> ThreadList:
        params: dict = {"limit": str(limit), "offset": str(offset)}
        if inbox_id:
            params["inbox_id"] = inbox_id
        if labels:
            params["labels"] = labels
        return ThreadList.from_dict(await self._c._request("GET", "/v1/threads", params=params))

    async def list(self, inbox_id: str, *, limit: int = 50, offset: int = 0) -> ThreadList:
        return ThreadList.from_dict(await self._c._request("GET", f"/v1/inboxes/{inbox_id}/threads", params={"limit": str(limit), "offset": str(offset)}))

    async def get(self, inbox_id: str, thread_id: str) -> ThreadDetail:
        return ThreadDetail.from_dict(await self._c._request("GET", f"/v1/inboxes/{inbox_id}/threads/{thread_id}"))

    async def get_attachments(self, inbox_id: str, thread_id: str) -> dict:
        return await self._c._request("GET", f"/v1/inboxes/{inbox_id}/threads/{thread_id}/attachments")


class _AsyncWebhooks:
    def __init__(self, client: AsyncDeadSimple):
        self._c = client

    async def create(self, url: str, events: list[str], description: str = "", *, headers: dict[str, str] | None = None, idempotency_key: str | None = None) -> Webhook:
        body: dict[str, Any] = {"url": url, "events": events}
        if description:
            body["description"] = description
        if headers:
            body["headers"] = headers
        return Webhook.from_dict(await self._c._request("POST", "/v1/webhooks", json=body, idempotency_key=idempotency_key))

    async def list(self) -> WebhookList:
        return WebhookList.from_dict(await self._c._request("GET", "/v1/webhooks"))

    async def delete(self, webhook_id: str) -> None:
        await self._c._request("DELETE", f"/v1/webhooks/{webhook_id}")

    async def get_headers(self, webhook_id: str) -> dict[str, str]:
        resp = await self._c._request("GET", f"/v1/webhooks/{webhook_id}/headers")
        return resp.get("headers", {})

    async def set_headers(self, webhook_id: str, headers: dict[str, str]) -> dict[str, str]:
        resp = await self._c._request("PUT", f"/v1/webhooks/{webhook_id}/headers", json={"headers": headers})
        return resp.get("headers", {})


class _AsyncDomains:
    def __init__(self, client: AsyncDeadSimple):
        self._c = client

    async def add(self, domain: str) -> Domain:
        return Domain.from_dict(await self._c._request("POST", "/v1/domains", json={"domain": domain}))

    async def list(self) -> DomainList:
        return DomainList.from_dict(await self._c._request("GET", "/v1/domains"))

    async def verify(self, domain_id: str) -> DomainVerification:
        return DomainVerification.from_dict(await self._c._request("GET", f"/v1/domains/{domain_id}/verify"))

    async def delete(self, domain_id: str) -> None:
        await self._c._request("DELETE", f"/v1/domains/{domain_id}")


class _AsyncApiKeys:
    def __init__(self, client: AsyncDeadSimple):
        self._c = client

    async def create(self, name: str, permissions: list[str] | None = None) -> ApiKey:
        body: dict[str, Any] = {"name": name}
        if permissions:
            body["permissions"] = permissions
        return ApiKey.from_dict(await self._c._request("POST", "/v1/api-keys", json=body))

    async def list(self) -> ApiKeyList:
        return ApiKeyList.from_dict(await self._c._request("GET", "/v1/api-keys"))

    async def delete(self, key_id: str) -> None:
        await self._c._request("DELETE", f"/v1/api-keys/{key_id}")


class _AsyncWorkspaces:
    def __init__(self, client: AsyncDeadSimple):
        self._c = client

    async def create(self, name: str, description: str = "", *, idempotency_key: str | None = None) -> Workspace:
        body: dict[str, Any] = {"name": name}
        if description:
            body["description"] = description
        return Workspace.from_dict(await self._c._request("POST", "/v1/workspaces", json=body, idempotency_key=idempotency_key))

    async def list(self) -> WorkspaceList:
        return WorkspaceList.from_dict(await self._c._request("GET", "/v1/workspaces"))

    async def get(self, workspace_id: str) -> Workspace:
        return Workspace.from_dict(await self._c._request("GET", f"/v1/workspaces/{workspace_id}"))

    async def update(self, workspace_id: str, *, name: str | None = None, description: str | None = None) -> Workspace:
        body: dict[str, Any] = {}
        if name is not None:
            body["name"] = name
        if description is not None:
            body["description"] = description
        return Workspace.from_dict(await self._c._request("PUT", f"/v1/workspaces/{workspace_id}", json=body))

    async def delete(self, workspace_id: str) -> None:
        await self._c._request("DELETE", f"/v1/workspaces/{workspace_id}")


class _AsyncUsage:
    def __init__(self, client: AsyncDeadSimple):
        self._c = client

    async def get(self) -> Usage:
        return Usage.from_dict(await self._c._request("GET", "/v1/usage"))


class _AsyncAttachments:
    def __init__(self, client: AsyncDeadSimple):
        self._c = client

    async def get_url(self, inbox_id: str, message_id: str, attachment_id: str) -> AttachmentUrl:
        return AttachmentUrl.from_dict(await self._c._request("GET", f"/v1/inboxes/{inbox_id}/messages/{message_id}/attachments/{attachment_id}"))


class _AsyncDrafts:
    """Draft email management (human-in-the-loop review)."""

    def __init__(self, client: AsyncDeadSimple):
        self._c = client

    async def create(self, inbox_id: str, *, to: list[str] | str = "", subject: str = "", text_body: str = "", html_body: str = "", cc: list[str] | None = None, bcc: list[str] | None = None, reply_to_message_id: str | None = None) -> Draft:
        if isinstance(to, str) and to:
            to = [to]
        body: dict[str, Any] = {}
        if to:
            body["to"] = to
        if subject:
            body["subject"] = subject
        if text_body:
            body["text_body"] = text_body
        if html_body:
            body["html_body"] = html_body
        if cc:
            body["cc"] = cc
        if bcc:
            body["bcc"] = bcc
        if reply_to_message_id:
            body["reply_to_message_id"] = reply_to_message_id
        return Draft.from_dict(await self._c._request("POST", f"/v1/inboxes/{inbox_id}/drafts", json=body))

    async def list(self, inbox_id: str) -> DraftList:
        return DraftList.from_dict(await self._c._request("GET", f"/v1/inboxes/{inbox_id}/drafts"))

    async def get(self, inbox_id: str, draft_id: str) -> Draft:
        return Draft.from_dict(await self._c._request("GET", f"/v1/inboxes/{inbox_id}/drafts/{draft_id}"))

    async def update(self, inbox_id: str, draft_id: str, **fields: Any) -> Draft:
        return Draft.from_dict(await self._c._request("PUT", f"/v1/inboxes/{inbox_id}/drafts/{draft_id}", json=fields))

    async def send(self, inbox_id: str, draft_id: str) -> SendResult:
        return SendResult.from_dict(await self._c._request("POST", f"/v1/inboxes/{inbox_id}/drafts/{draft_id}/send"))

    async def delete(self, inbox_id: str, draft_id: str) -> None:
        await self._c._request("DELETE", f"/v1/inboxes/{inbox_id}/drafts/{draft_id}")


class _AsyncFilters:
    """Allowlist / blocklist management."""

    def __init__(self, client: AsyncDeadSimple):
        self._c = client

    async def create(self, inbox_id: str, *, action: str, criteria: str, value: str, description: str = "") -> dict[str, Any]:
        body: dict[str, Any] = {"action": action, "criteria": criteria, "value": value}
        if description:
            body["description"] = description
        return await self._c._request("POST", f"/v1/inboxes/{inbox_id}/filters", json=body)

    async def list(self, inbox_id: str) -> dict[str, Any]:
        return await self._c._request("GET", f"/v1/inboxes/{inbox_id}/filters")

    async def delete(self, inbox_id: str, filter_id: str) -> None:
        await self._c._request("DELETE", f"/v1/inboxes/{inbox_id}/filters/{filter_id}")


class _AsyncTemplates:
    """Email template management."""

    def __init__(self, client: AsyncDeadSimple):
        self._c = client

    async def create(self, name: str, *, subject: str = "", text_body: str = "", html_body: str = "") -> dict[str, Any]:
        body: dict[str, Any] = {"name": name}
        if subject:
            body["subject"] = subject
        if text_body:
            body["text_body"] = text_body
        if html_body:
            body["html_body"] = html_body
        return await self._c._request("POST", "/v1/templates", json=body)

    async def list(self) -> dict[str, Any]:
        return await self._c._request("GET", "/v1/templates")

    async def get(self, template_id: str) -> dict[str, Any]:
        return await self._c._request("GET", f"/v1/templates/{template_id}")

    async def update(self, template_id: str, **fields: Any) -> dict[str, Any]:
        return await self._c._request("PUT", f"/v1/templates/{template_id}", json=fields)

    async def delete(self, template_id: str) -> None:
        await self._c._request("DELETE", f"/v1/templates/{template_id}")

# Public alias: a worker that holds only the agent's private key (no API key)
# can build the sign-in assertion without constructing a client.
make_assertion = _Identity.make_assertion


class _AsyncIdentity:
    """Async version of :class:`_Identity`."""

    ISSUER = _Identity.ISSUER
    make_assertion = staticmethod(_Identity.make_assertion)

    def __init__(self, client: AsyncDeadSimple):
        self._c = client

    async def sign_in(self, inbox_id: str, authorization_url: str, *, follow: bool = True) -> dict[str, Any]:
        out = await self._c._request(
            "POST", f"/v1/inboxes/{inbox_id}/identity/sign-in", json={"authorization_url": authorization_url}
        )
        if follow:
            async with httpx.AsyncClient(follow_redirects=True, timeout=30.0) as h:
                resp = await h.get(out["redirect_to"])
            out["final_url"] = str(resp.url)
            out["final_status"] = resp.status_code
        return out

    async def enroll_key(self, inbox_id: str, *, public_key: dict[str, Any] | str, name: str = "") -> dict[str, Any]:
        body: dict[str, Any] = {"public_key": public_key}
        if name:
            body["name"] = name
        return await self._c._request("POST", f"/v1/inboxes/{inbox_id}/identity/keys", json=body)

    async def list_keys(self, inbox_id: str) -> dict[str, Any]:
        return await self._c._request("GET", f"/v1/inboxes/{inbox_id}/identity/keys")

    async def delete_key(self, inbox_id: str, kid: str) -> None:
        await self._c._request("DELETE", f"/v1/inboxes/{inbox_id}/identity/keys/{kid}")

    async def connections(self, inbox_id: str) -> dict[str, Any]:
        return await self._c._request("GET", f"/v1/inboxes/{inbox_id}/identity/connections")

    async def register_client(self, client_name: str, redirect_uris: list[str], *, client_uri: str = "",
                              logo_uri: str = "", scope: str = "openid email profile owner_email org offline_access",
                              token_endpoint_auth_method: str = "client_secret_basic") -> dict[str, Any]:
        body: dict[str, Any] = {"client_name": client_name, "redirect_uris": redirect_uris, "scope": scope,
                                "token_endpoint_auth_method": token_endpoint_auth_method}
        if client_uri:
            body["client_uri"] = client_uri
        if logo_uri:
            body["logo_uri"] = logo_uri
        return await self._c._request("POST", "/v1/identity/clients", json=body)

    async def list_clients(self) -> dict[str, Any]:
        return await self._c._request("GET", "/v1/identity/clients")

    async def delete_client(self, client_id: str) -> None:
        await self._c._request("DELETE", f"/v1/identity/clients/{client_id}")



# ── WebSocket streaming ──────────────────────────────────────────────────────


class WebSocketStream:
    """Real-time event stream via WebSocket.

    Usage::

        import asyncio
        from deadsimple import WebSocketStream

        async def main():
            async with WebSocketStream("dse_your_api_key") as stream:
                await stream.subscribe(inbox_ids=["..."], events=["message.received"])
                async for event in stream:
                    print(event["event"], event["data"])

        asyncio.run(main())
    """

    def __init__(
        self,
        api_key: str,
        ws_url: str = "wss://ws.deadsimple.email",
    ):
        self._api_key = api_key
        self._ws_url = ws_url
        self._ws = None

    async def __aenter__(self):
        try:
            import websockets
        except ImportError:
            raise ImportError("Install websockets: pip install deadsimple-email[websocket]")

        url = f"{self._ws_url}?api_key={self._api_key}"
        self._ws = await websockets.connect(url)
        return self

    async def __aexit__(self, *args):
        if self._ws:
            await self._ws.close()
            self._ws = None

    async def subscribe(
        self,
        inbox_ids: list[str] | None = None,
        events: list[str] | None = None,
    ) -> dict:
        """Subscribe to specific inboxes and/or event types."""
        import json as _json
        msg = {"action": "subscribe"}
        if inbox_ids:
            msg["inbox_ids"] = inbox_ids
        if events:
            msg["events"] = events
        await self._ws.send(_json.dumps(msg))
        resp = await self._ws.recv()
        return _json.loads(resp)

    async def ping(self) -> None:
        """Send a keepalive ping."""
        import json as _json
        await self._ws.send(_json.dumps({"action": "ping"}))
        await self._ws.recv()  # pong

    def __aiter__(self):
        return self

    async def __anext__(self) -> dict:
        import json as _json
        try:
            raw = await self._ws.recv()
            return _json.loads(raw)
        except Exception:
            raise StopAsyncIteration
