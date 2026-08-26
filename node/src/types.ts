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
}

export interface ApiKeyList {
  api_keys: ApiKey[];
  count: number;
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
