"""Typed response models for Dead Simple Email API."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class Inbox:
    inbox_id: str
    email: str
    local_part: str
    domain: str
    display_name: str
    tags: list[str]
    status: str
    message_count: int
    created_at: str
    updated_at: str

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> Inbox:
        return cls(**{k: d[k] for k in cls.__dataclass_fields__ if k in d})


@dataclass
class InboxList:
    inboxes: list[Inbox]
    count: int
    cursor: str | None = None

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> InboxList:
        return cls(
            inboxes=[Inbox.from_dict(i) for i in d.get("inboxes", [])],
            count=d.get("count", 0),
            cursor=d.get("cursor"),
        )


@dataclass
class BulkCreateResult:
    results: list[dict[str, Any]]
    created: int
    failed: int
    total: int

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> BulkCreateResult:
        return cls(
            results=d.get("results", []),
            created=d.get("created", 0),
            failed=d.get("failed", 0),
            total=d.get("total", 0),
        )


@dataclass
class Attachment:
    filename: str
    content_type: str
    size: int
    attachment_id: str = ""
    extracted_text: str = ""  # readable text for PDF/XLSX/DOCX/CSV/… attachments

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> Attachment:
        return cls(**{k: d[k] for k in cls.__dataclass_fields__ if k in d})


@dataclass
class Message:
    message_id: str
    inbox_id: str
    thread_id: str
    direction: str
    from_email: str
    from_name: str
    to: list[str]
    cc: list[str]
    subject: str
    labels: list[str]
    status: str
    snippet: str
    attachments: list[Attachment]
    is_spam: bool
    spam_score: float
    created_at: str
    received_at: str
    # Prompt-injection scan of inbound mail: "low" | "medium" | "high" and a
    # 0..1 score. Absent on outbound messages.
    injection_risk: str = ""
    injection_score: float = 0.0

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> Message:
        data = {k: d.get(k, "") for k in cls.__dataclass_fields__}
        data["to"] = d.get("to", [])
        data["cc"] = d.get("cc", [])
        data["attachments"] = [Attachment.from_dict(a) for a in d.get("attachments", [])]
        data["injection_risk"] = d.get("injection_risk") or ""
        data["injection_score"] = float(d.get("injection_score") or 0)
        return cls(**data)


@dataclass
class MessageFull(Message):
    text_body: str = ""
    html_body: str = ""
    latest_reply: str = ""
    in_reply_to: str = ""
    references: list[str] = field(default_factory=list)
    headers: dict[str, str] = field(default_factory=dict)
    # Auto-extracted verification data (verification_code, magic_link_url,
    # expires_in, all_codes, all_links) when the message contains an OTP/link.
    extracted: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> MessageFull:
        data = {k: d.get(k, "") for k in Message.__dataclass_fields__}
        data["to"] = d.get("to", [])
        data["cc"] = d.get("cc", [])
        data["attachments"] = [Attachment.from_dict(a) for a in d.get("attachments", [])]
        data["text_body"] = d.get("text_body", "")
        data["html_body"] = d.get("html_body", "")
        data["latest_reply"] = d.get("latest_reply", "")
        data["in_reply_to"] = d.get("in_reply_to", "")
        data["references"] = d.get("references", [])
        data["headers"] = d.get("headers", {})
        data["extracted"] = d.get("extracted", {})
        return cls(**data)


@dataclass
class MessageList:
    messages: list[Message]
    count: int
    cursor: str | None = None

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> MessageList:
        return cls(
            messages=[Message.from_dict(m) for m in d.get("messages", [])],
            count=d.get("count", 0),
            cursor=d.get("cursor"),
        )


@dataclass
class SendResult:
    message_id: str
    status: str
    # Present only on a calendar invite. Rescheduling or cancelling the event
    # is matched to the original by UID, so an agent that does not keep this
    # cannot change the meeting it just booked.
    calendar_uid: str = ""

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> SendResult:
        return cls(message_id=d.get("message_id", ""), status=d.get("status", ""),
                   calendar_uid=d.get("calendar_uid", ""))


@dataclass
class Thread:
    thread_id: str
    subject: str
    message_count: int
    participants: list[str]
    latest_message: dict[str, Any]
    created_at: str
    updated_at: str

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> Thread:
        return cls(**{k: d.get(k, "" if isinstance(cls.__dataclass_fields__[k].default, str) else cls.__dataclass_fields__[k].default) for k in cls.__dataclass_fields__ if k in d} | {k: d.get(k) for k in cls.__dataclass_fields__ if k in d})


@dataclass
class ThreadList:
    threads: list[Thread]
    count: int
    total: int

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> ThreadList:
        return cls(
            threads=[Thread.from_dict(t) for t in d.get("threads", [])],
            count=d.get("count", 0),
            total=d.get("total", 0),
        )


@dataclass
class ThreadDetail:
    thread_id: str
    subject: str
    messages: list[MessageFull]
    participants: list[str]

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> ThreadDetail:
        return cls(
            thread_id=d.get("thread_id", ""),
            subject=d.get("subject", ""),
            messages=[MessageFull.from_dict(m) for m in d.get("messages", [])],
            participants=d.get("participants", []),
        )


class WebhookEvent:
    """Webhook event type constants."""

    MESSAGE_RECEIVED = "message.received"
    MESSAGE_SENT = "message.sent"
    MESSAGE_DELIVERED = "message.delivered"
    MESSAGE_BOUNCED = "message.bounced"
    MESSAGE_COMPLAINED = "message.complained"
    MESSAGE_REJECTED = "message.rejected"
    MESSAGE_OPENED = "message.opened"
    MESSAGE_LINK_CLICKED = "message.link_clicked"
    INBOX_CREATED = "inbox.created"
    INBOX_DELETED = "inbox.deleted"
    DOMAIN_VERIFIED = "domain.verified"

    ALL = [
        MESSAGE_RECEIVED, MESSAGE_SENT, MESSAGE_DELIVERED,
        MESSAGE_BOUNCED, MESSAGE_COMPLAINED, MESSAGE_REJECTED,
        MESSAGE_OPENED, MESSAGE_LINK_CLICKED,
        INBOX_CREATED, INBOX_DELETED, DOMAIN_VERIFIED,
    ]


@dataclass
class Webhook:
    webhook_id: str
    url: str
    events: list[str]
    description: str
    is_active: bool
    created_at: str
    last_triggered_at: str | None = None
    failure_count: int = 0
    signing_secret: str | None = None
    # Custom delivery headers. Values are masked by the API (write-only).
    headers: dict[str, str] = field(default_factory=dict)
    # Inboxes this webhook is restricted to. Empty means every inbox.
    inbox_ids: list[str] = field(default_factory=list)
    workspace_id: str | None = None

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> Webhook:
        return cls(**{k: d[k] for k in cls.__dataclass_fields__ if k in d})


@dataclass
class WebhookList:
    webhooks: list[Webhook]
    count: int

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> WebhookList:
        return cls(
            webhooks=[Webhook.from_dict(w) for w in d.get("webhooks", [])],
            count=d.get("count", 0),
        )


@dataclass
class Domain:
    domain_id: str
    domain: str
    status: str
    dns_records: list[dict[str, str]]
    created_at: str
    verified_at: str | None = None

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> Domain:
        return cls(**{k: d[k] for k in cls.__dataclass_fields__ if k in d})


@dataclass
class DomainList:
    domains: list[Domain]
    count: int

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> DomainList:
        return cls(
            domains=[Domain.from_dict(dm) for dm in d.get("domains", [])],
            count=d.get("count", 0),
        )


@dataclass
class DomainVerification(Domain):
    dns_checks: dict[str, bool] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> DomainVerification:
        return cls(**{k: d[k] for k in cls.__dataclass_fields__ if k in d})


@dataclass
class ApiKey:
    key_id: str
    name: str
    key_prefix: str
    permissions: list[str]
    is_active: bool
    created_at: str
    key: str | None = None
    revoked_at: str | None = None
    # Inboxes the key is restricted to. Empty means account- or workspace-wide.
    inbox_ids: list[str] = field(default_factory=list)
    workspace_id: str | None = None

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> ApiKey:
        return cls(**{k: d[k] for k in cls.__dataclass_fields__ if k in d})


@dataclass
class ApiKeyList:
    api_keys: list[ApiKey]
    count: int

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> ApiKeyList:
        return cls(
            api_keys=[ApiKey.from_dict(k) for k in d.get("api_keys", [])],
            count=d.get("count", 0),
        )


@dataclass
class MetricsBucket:
    """One interval of GET /v1/metrics (also the shape of `Metrics.totals`)."""

    start: str
    sent: int = 0
    received: int = 0
    bounced: int = 0
    complained: int = 0
    opened: int = 0
    clicked: int = 0
    webhook_deliveries: int = 0
    webhook_failures: int = 0
    injection_flagged: int = 0

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> MetricsBucket:
        return cls(**{k: d[k] for k in cls.__dataclass_fields__ if k in d})


@dataclass
class Metrics:
    interval: str
    from_: str
    to: str
    series: list[MetricsBucket]
    totals: MetricsBucket

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> Metrics:
        totals = dict(d.get("totals") or {})
        totals.setdefault("start", d.get("from", ""))
        return cls(
            interval=d.get("interval", "day"),
            from_=d.get("from", ""),
            to=d.get("to", ""),
            series=[MetricsBucket.from_dict(b) for b in d.get("series", [])],
            totals=MetricsBucket.from_dict(totals),
        )


@dataclass
class Usage:
    plan: str
    plan_name: str
    inboxes: dict[str, int]
    emails: dict[str, int]
    webhooks: int
    custom_domains: dict[str, int]

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> Usage:
        return cls(
            plan=d.get("plan", ""),
            plan_name=d.get("plan_name", ""),
            inboxes=d.get("inboxes", {}),
            emails=d.get("emails", {}),
            webhooks=d.get("webhooks", 0),
            custom_domains=d.get("custom_domains", {}),
        )


@dataclass
class Workspace:
    workspace_id: str
    name: str
    description: str
    is_default: bool
    created_at: str
    updated_at: str
    inbox_count: int = 0
    api_key: dict[str, str] | None = None

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> Workspace:
        return cls(**{k: d[k] for k in cls.__dataclass_fields__ if k in d})


# Backward compatibility alias
Pod = Workspace


@dataclass
class WorkspaceList:
    workspaces: list[Workspace]
    count: int

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> WorkspaceList:
        return cls(
            workspaces=[Workspace.from_dict(w) for w in d.get("workspaces", [])],
            count=d.get("count", 0),
        )


# Backward compatibility alias
PodList = WorkspaceList


@dataclass
class Draft:
    draft_id: str
    inbox_id: str
    to: list[str]
    cc: list[str]
    bcc: list[str]
    subject: str
    text_body: str
    html_body: str
    created_at: str
    updated_at: str
    reply_to_message_id: str | None = None

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> Draft:
        return cls(
            draft_id=d.get("draft_id", ""),
            inbox_id=d.get("inbox_id", ""),
            to=d.get("to", []),
            cc=d.get("cc", []),
            bcc=d.get("bcc", []),
            subject=d.get("subject", ""),
            text_body=d.get("text_body", ""),
            html_body=d.get("html_body", ""),
            created_at=d.get("created_at", ""),
            updated_at=d.get("updated_at", ""),
            reply_to_message_id=d.get("reply_to_message_id"),
        )


@dataclass
class DraftList:
    drafts: list[Draft]
    count: int

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> DraftList:
        return cls(
            drafts=[Draft.from_dict(dr) for dr in d.get("drafts", [])],
            count=d.get("count", 0),
        )


@dataclass
class AttachmentUrl:
    attachment_id: str
    filename: str
    content_type: str
    size: int
    url: str
    expires_in: int = 3600

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> AttachmentUrl:
        return cls(**{k: d[k] for k in cls.__dataclass_fields__ if k in d})
