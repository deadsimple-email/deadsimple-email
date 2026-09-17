/** Core types for the Dead Simple Email API. */

export interface Inbox {
  inbox_id: string;
  email: string;
  local_part: string;
  domain: string;
  display_name: string;
  tags: string[];
  status: string;
  message_count: number;
  created_at: string;
  updated_at: string;
}

export interface InboxList {
  inboxes: Inbox[];
  count: number;
  cursor?: string;
}

export interface BulkCreateResult {
  results: Record<string, unknown>[];
  created: number;
  failed: number;
  total: number;
}

export interface Attachment {
  attachment_id: string;
  filename: string;
  content_type: string;
  size: number;
  /** Readable text for PDF/XLSX/DOCX/CSV/… attachments (when extractable). */
  extracted_text?: string;
}

export interface Message {
  message_id: string;
  inbox_id: string;
  thread_id: string;
  direction: string;
  from_email: string;
  from_name: string;
  to: string[];
  cc: string[];
  subject: string;
  labels: string[];
  status: string;
  snippet: string;
  attachments: Attachment[];
  is_spam?: boolean;
  spam_score?: number;
  /** Prompt-injection scan of inbound mail: "low" | "medium" | "high". Absent on outbound. */
  injection_risk?: "low" | "medium" | "high";
  /** 0..1 injection score that produced `injection_risk`. */
  injection_score?: number;
  created_at: string;
  received_at: string;
}

export interface MessageFull extends Message {
  text_body: string;
  html_body: string;
  latest_reply: string;
  in_reply_to: string;
  references: string[];
  headers: Record<string, string>;
  /** Auto-extracted verification data (verification_code, magic_link_url, expires_in, all_codes, all_links). */
  extracted?: {
    verification_code?: string;
    magic_link_url?: string;
    expires_in?: string;
    all_codes?: string[];
    all_links?: string[];
  };
}

export interface Draft {
  draft_id: string;
  inbox_id: string;
  to: string[];
  cc?: string[];
  bcc?: string[];
  subject: string;
  text_body: string;
  html_body: string;
  reply_to_message_id?: string;
  created_at: string;
  updated_at: string;
}

export interface DraftList {
  drafts: Draft[];
  count: number;
}

export interface BulkDeleteResult {
  results: { inbox_id: string; status: string; error?: string }[];
  deleted: number;
  failed: number;
  total: number;
}

export interface MessageList {
  messages: Message[];
  count: number;
  cursor?: string;
}

export interface SendResult {
  message_id: string;
  status: string;
  /**
   * Present only on a calendar invite. Rescheduling or cancelling the event is
   * matched to the original by UID, so an agent that does not keep this cannot
   * change the meeting it just booked.
   */
  calendar_uid?: string;
}

/**
 * A calendar invitation carried in the message body, which is what produces
 * Accept/Decline and puts the event on the recipient's calendar. Attaching an
 * .ics file does not: it arrives as a download nobody can act on.
 */
export interface CalendarInvite {
  /** Event title, as it appears on the calendar. */
  title: string;
  /**
   * ISO 8601 start. Needs a zone: a trailing "Z", an offset, or `timezone`.
   * A bare date ("2026-09-15") makes it an all-day event.
   */
  start: string;
  /** ISO 8601 end. Omit to use `durationMinutes`. */
  end?: string;
  /** Length when `end` is absent. Defaults to 30. */
  duration_minutes?: number;
  /** IANA zone for a local time with no offset, e.g. "America/New_York". */
  timezone?: string;
  location?: string;
  description?: string;
  /** Defaults to the message's own `to` + `cc`. */
  attendees?: (string | { email: string; name?: string; optional?: boolean })[];
  /** Minutes before the event to alarm. */
  reminder_minutes?: number;
  all_day?: boolean;
  /** RFC 5545 rule for a repeating event, e.g. "FREQ=WEEKLY;COUNT=4". */
  recurrence?: string;
  /** Pass the uid of an event already sent to reschedule or cancel it. */
  uid?: string;
  /** Raise above the last sent whenever an existing event changes. */
  sequence?: number;
  /** "REQUEST" (default), "CANCEL" to withdraw, or "PUBLISH" for no RSVP. */
  method?: "REQUEST" | "CANCEL" | "PUBLISH";
  /** Your own iCalendar object, instead of the fields above. */
  ics?: string;
}

export interface Thread {
  thread_id: string;
  subject: string;
  message_count: number;
  participants: string[];
  latest_message: {
    message_id: string;
    from_email: string;
    snippet: string;
    direction: string;
    created_at: string;
  };
  created_at: string;
  updated_at: string;
}

export interface ThreadList {
  threads: Thread[];
  count: number;
  total: number;
}

export interface ThreadDetail {
  thread_id: string;
  subject: string;
  messages: MessageFull[];
  participants: string[];
}

/** Webhook event type constants. */
export const WebhookEvent = {
  MESSAGE_RECEIVED: "message.received",
  MESSAGE_SENT: "message.sent",
  MESSAGE_DELIVERED: "message.delivered",
  MESSAGE_BOUNCED: "message.bounced",
  MESSAGE_COMPLAINED: "message.complained",
  MESSAGE_REJECTED: "message.rejected",
  MESSAGE_OPENED: "message.opened",
  MESSAGE_LINK_CLICKED: "message.link_clicked",
  INBOX_CREATED: "inbox.created",
  INBOX_DELETED: "inbox.deleted",
  DOMAIN_VERIFIED: "domain.verified",
} as const;

export type WebhookEventType = (typeof WebhookEvent)[keyof typeof WebhookEvent];

export interface Webhook {
  webhook_id: string;
  url: string;
  events: string[];
  description: string;
  is_active: boolean;
  created_at: string;
  last_triggered_at?: string;
  failure_count: number;
  signing_secret?: string;
  /** Custom delivery headers. Values are masked by the API (write-only). */
  headers?: Record<string, string>;
  /** Inboxes this webhook is restricted to. Empty means every inbox. */
  inbox_ids: string[];
  workspace_id?: string;
}

export interface WebhookList {
  webhooks: Webhook[];
  count: number;
}

export interface Domain {
  domain_id: string;
  domain: string;
  status: string;
  dns_records: { type: string; name: string; value: string; purpose: string }[];
  created_at: string;
  verified_at?: string;
}

export interface DomainList {
  domains: Domain[];
  count: number;
}

export interface DomainVerification extends Domain {
  dns_checks: Record<string, boolean>;
}

export interface ApiKey {
  key_id: string;
  name: string;
  key_prefix: string;
  permissions: string[];
  is_active: boolean;
  created_at: string;
  key?: string;
  revoked_at?: string;
  /** Inboxes the key is restricted to. Empty means account- or workspace-wide. */
  inbox_ids: string[];
  workspace_id?: string;
}

export interface ApiKeyList {
  api_keys: ApiKey[];
  count: number;
}

export type MetricsInterval = "day" | "hour";

/** One interval of GET /v1/metrics; also the shape of `Metrics.totals`. */
export interface MetricsBucket {
  /** Bucket start, UTC. Absent on `totals`. */
  start?: string;
  sent: number;
  received: number;
  bounced: number;
  complained: number;
  opened: number;
  clicked: number;
  webhook_deliveries: number;
  webhook_failures: number;
  injection_flagged: number;
}

export interface Metrics {
  interval: MetricsInterval;
  from: string;
  to: string;
  series: MetricsBucket[];
  totals: MetricsBucket;
}

export interface Usage {
  plan: string;
  plan_name: string;
  inboxes: { used: number; limit: number };
  emails: {
    sent_today: number;
    received_today: number;
    sent_this_month: number;
    received_this_month: number;
    monthly_limit: number;
  };
  webhooks: number;
  custom_domains: { used: number; limit: number };
}

export interface Workspace {
  workspace_id: string;
  name: string;
  description: string;
  is_default: boolean;
  created_at: string;
  updated_at: string;
  inbox_count: number;
  api_key?: { key: string; key_id: string; key_prefix: string; warning: string };
}

/** @deprecated Use Workspace instead */
export type Pod = Workspace;

export interface WorkspaceList {
  workspaces: Workspace[];
  count: number;
}

/** @deprecated Use WorkspaceList instead */
export type PodList = WorkspaceList;

export interface AttachmentUrl {
  attachment_id: string;
  filename: string;
  content_type: string;
  size: number;
  url: string;
  expires_in: number;
}


// ── Sign in with Dead Simple (id.deadsimple.email) ───────────────────────────

export interface IdentitySignInResult {
  redirect_to: string;
  client_id: string;
  client_name: string;
  scope: string;
  expires_in: number;
  next_step: string;
  final_url?: string;
  final_status?: number;
}

export interface IdentityKey {
  kid: string;
  inbox_id: string;
  email: string;
  name: string;
  jwk: { kty: string; crv: string; x: string; y: string; kid: string };
  created_at: string;
  last_used_at: string | null;
}

export interface IdentityConnection {
  client_id: string;
  client_name: string;
  client_uri: string;
  scope: string;
  first_sign_in_at: string;
  last_sign_in_at: string;
  sign_in_count: number;
}

export interface IdentityClient {
  client_id: string;
  client_name: string;
  client_uri: string;
  logo_uri: string;
  redirect_uris: string[];
  token_endpoint_auth_method: string;
  scope: string;
  grant_types: string[];
  response_types: string[];
  created_at: string;
  issuer?: string;
  discovery_url?: string;
  warning?: string;
}

// ── Agent calendar ───────────────────────────────────────────────────────────

export type CalendarEventStatus = "confirmed" | "tentative" | "cancelled";
export type CalendarResponse = "needs-action" | "accepted" | "declined" | "tentative";

export interface CalendarAttendee {
  email: string;
  name?: string;
  /** The attendee's answer as last seen (our own rsvp, or their REPLY). */
  response?: CalendarResponse;
  /** OPT-PARTICIPANT rather than REQ-PARTICIPANT on the invitation. */
  optional?: boolean;
}

export interface CalendarOrganizer {
  email: string;
  name?: string;
}

/**
 * Fields for creating or updating an event. Times are ISO 8601 and need a
 * zone: a trailing "Z", an offset, or `timezone`. A bare date makes an
 * all-day event. Everything is optional on update.
 */
export interface CalendarEventInput {
  title?: string;
  start?: string;
  /** Omit to use `duration_minutes` (default 30). On update, a moved start keeps the length. */
  end?: string;
  duration_minutes?: number;
  /** IANA zone for a local start/end with no offset, e.g. "America/New_York". */
  timezone?: string;
  all_day?: boolean;
  description?: string;
  location?: string;
  status?: CalendarEventStatus;
  /** Defaults to the inbox itself. */
  organizer?: CalendarOrganizer | string;
  attendees?: (string | CalendarAttendee)[];
  /** Create only: bring your own iCalendar UID. */
  ical_uid?: string;
  sequence?: number;
}

export interface CalendarEvent {
  event_id: string;
  inbox_id: string;
  workspace_id?: string | null;
  /** Stable across updates; what updates, cancellations and replies are matched on. */
  ical_uid: string;
  title: string;
  description: string;
  location: string;
  /** ISO 8601 UTC, e.g. "2026-09-15T19:00:00Z". */
  start_at: string;
  /** ISO 8601 UTC. Exclusive for all-day events. */
  end_at: string;
  timezone: string;
  all_day: boolean;
  status: CalendarEventStatus;
  organizer: CalendarOrganizer;
  attendees: CalendarAttendee[];
  /** api = created here; sent = created here and sent as an invitation; inbound = arrived by email. */
  source: "api" | "sent" | "inbound";
  sequence: number;
  /** The invitation we sent, or the inbound message that last changed the event. */
  message_id?: string | null;
  invited_at?: string | null;
  created_at: string;
  updated_at: string;
}

export interface CalendarEventList {
  events: CalendarEvent[];
  count: number;
  /** Present when there is another page. */
  cursor?: string;
}

export interface CalendarInviteResult extends CalendarEvent {
  message_id: string;
  /** CANCEL when the event's status is cancelled; REQUEST otherwise. */
  method: "REQUEST" | "CANCEL";
  sent_to: string[];
}

export interface CalendarRsvpResult extends CalendarEvent {
  message_id: string;
  response: "accepted" | "declined" | "tentative";
}

export interface CalendarFeed {
  inbox_id: string;
  email: string;
  /** https URL of the .ics feed, token included. Treat as a secret. */
  feed_url: string;
  /** The same feed as a webcal:// link. */
  webcal_url: string;
  token_created_at: string;
  /** True when this call issued a new token (first request, or a rotate). */
  rotated: boolean;
}
