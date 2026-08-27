/**
 * Dead Simple Email API client for Node.js / TypeScript.
 *
 * @example
 * ```ts
 * import { DeadSimple } from "@deadsimple/email";
 *
 * const client = new DeadSimple("dse_your_api_key");
 * const inbox = await client.inboxes.create({ displayName: "Support Bot" });
 * await client.messages.send({
 *   inboxId: inbox.inbox_id,
 *   to: "user@example.com",
 *   subject: "Hello",
 *   textBody: "Sent by an AI agent.",
 * });
 * ```
 */

import {
  AuthenticationError,
  DeadSimpleError,
  NotFoundError,
  RateLimitError,
  ValidationError,
} from "./errors.js";
import type {
  ApiKey,
  ApiKeyList,
  AttachmentUrl,
  BulkCreateResult,
  BulkDeleteResult,
  Domain,
  DomainList,
  DomainVerification,
  Draft,
  DraftList,
  Inbox,
  InboxList,
  MessageFull,
  MessageList,
  SendResult,
  ThreadDetail,
  ThreadList,
  Usage,
  Webhook,
  WebhookList,
  Workspace,
  WorkspaceList,
} from "./types.js";

const DEFAULT_BASE_URL = "https://api.deadsimple.email";
const VERSION = "1.1.0";

export interface DeadSimpleOptions {
  baseUrl?: string;
  timeout?: number;
}

// ── HTTP layer ───────────────────────────────────────────────────────────────

async function handleResponse(response: Response): Promise<unknown> {
  if (response.status === 204) return null;

  let body: Record<string, unknown>;
  try {
    body = (await response.json()) as Record<string, unknown>;
  } catch {
    throw new DeadSimpleError(`Invalid response: ${response.statusText}`, {
      statusCode: response.status,
    });
  }

  if (!response.ok) {
    const error = (body.error ?? {}) as Record<string, unknown>;
    const msg = (error.message as string) ?? "Unknown error";
    const code = (error.code as string) ?? "";
    const details = (error.details ?? []) as { field: string; message: string }[];

    if (response.status === 401)
      throw new AuthenticationError(msg, { code, details });
    if (response.status === 400)
      throw new ValidationError(msg, { code, details });
    if (response.status === 404) throw new NotFoundError(msg, { code });
    if (response.status === 429) {
      const retryAfter = parseInt(
        response.headers.get("Retry-After") ?? "60",
        10
      );
      throw new RateLimitError(msg, { code, retryAfter });
    }
    throw new DeadSimpleError(msg, { code, statusCode: response.status, details });
  }

  return (body as { data: unknown }).data;
}

// ── Client ───────────────────────────────────────────────────────────────────

export class DeadSimple {
  private apiKey: string;
  private baseUrl: string;
  private timeout: number;

  readonly inboxes: Inboxes;
  readonly messages: Messages;
  readonly threads: Threads;
  readonly drafts: Drafts;
  readonly webhooks: Webhooks;
  readonly domains: Domains;
  readonly apiKeys: ApiKeys;
  readonly workspaces: Workspaces;
  readonly usage: UsageResource;
  readonly attachments: Attachments;
  readonly filters: Filters;
  readonly templates: Templates;

  constructor(apiKey: string, options?: DeadSimpleOptions) {
    if (!apiKey) {
      throw new AuthenticationError("API key is required", {
        code: "missing_key",
      });
    }
    this.apiKey = apiKey;
    this.baseUrl = (options?.baseUrl ?? DEFAULT_BASE_URL).replace(/\/$/, "");
    this.timeout = options?.timeout ?? 30_000;

    this.inboxes = new Inboxes(this);
    this.messages = new Messages(this);
    this.threads = new Threads(this);
    this.drafts = new Drafts(this);
    this.webhooks = new Webhooks(this);
    this.domains = new Domains(this);
    this.apiKeys = new ApiKeys(this);
    this.workspaces = new Workspaces(this);
    this.usage = new UsageResource(this);
    this.attachments = new Attachments(this);
    this.filters = new Filters(this);
    this.templates = new Templates(this);
  }

  /** @internal */
  async _request<T>(
    method: string,
    path: string,
    opts?: {
      body?: Record<string, unknown>;
      params?: Record<string, string>;
      idempotencyKey?: string;
    }
  ): Promise<T> {
    let url = `${this.baseUrl}${path}`;
    if (opts?.params) {
      const qs = new URLSearchParams(opts.params).toString();
      if (qs) url += `?${qs}`;
    }

    const headers: Record<string, string> = {
      Authorization: `Bearer ${this.apiKey}`,
      "Content-Type": "application/json",
      "User-Agent": `deadsimple-node/${VERSION}`,
    };
    if (opts?.idempotencyKey) {
      headers["Idempotency-Key"] = opts.idempotencyKey;
    }

    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), this.timeout);

    try {
      const response = await fetch(url, {
        method,
        headers,
        body: opts?.body ? JSON.stringify(opts.body) : undefined,
        signal: controller.signal,
      });
      return (await handleResponse(response)) as T;
    } finally {
      clearTimeout(timer);
    }
  }
}

// ── Resource classes ─────────────────────────────────────────────────────────

class Inboxes {
  constructor(private client: DeadSimple) {}

  /** Create a new inbox. Returns inbox with email address. */
  async create(opts?: {
    displayName?: string;
    domain?: string;
    localPart?: string;
    tags?: string[];
    idempotencyKey?: string;
  }): Promise<Inbox> {
    const body: Record<string, unknown> = {};
    if (opts?.displayName) body.display_name = opts.displayName;
    if (opts?.domain) body.domain = opts.domain;
    if (opts?.localPart) body.local_part = opts.localPart;
    if (opts?.tags) body.tags = opts.tags;
    return this.client._request("POST", "/v1/inboxes", {
      body,
      idempotencyKey: opts?.idempotencyKey,
    });
  }

  /** Create up to 100 inboxes in one call. */
  async bulkCreate(
    inboxes: { displayName?: string; tags?: string[] }[],
    opts?: { idempotencyKey?: string }
  ): Promise<BulkCreateResult> {
    return this.client._request("POST", "/v1/inboxes/bulk", {
      body: {
        inboxes: inboxes.map((i) => ({
          display_name: i.displayName,
          tags: i.tags,
        })),
      },
      idempotencyKey: opts?.idempotencyKey,
    });
  }

  /** List inboxes with optional filters. */
  async list(opts?: {
    domain?: string;
    status?: string;
    tag?: string;
    limit?: number;
    cursor?: string;
  }): Promise<InboxList> {
    const params: Record<string, string> = {
      limit: String(opts?.limit ?? 50),
    };
    if (opts?.domain) params.domain = opts.domain;
    if (opts?.status) params.status = opts.status;
    if (opts?.tag) params.tag = opts.tag;
    if (opts?.cursor) params.cursor = opts.cursor;
    return this.client._request("GET", "/v1/inboxes", { params });
  }

  /** Get a single inbox. */
  async get(inboxId: string): Promise<Inbox> {
    return this.client._request("GET", `/v1/inboxes/${inboxId}`);
  }

  /** Update inbox properties. */
  async update(
    inboxId: string,
    opts: { displayName?: string; tags?: string[]; status?: string }
  ): Promise<Inbox> {
    const body: Record<string, unknown> = {};
    if (opts.displayName !== undefined) body.display_name = opts.displayName;
    if (opts.tags !== undefined) body.tags = opts.tags;
    if (opts.status !== undefined) body.status = opts.status;
    return this.client._request("PATCH", `/v1/inboxes/${inboxId}`, { body });
  }

  /** Delete an inbox and all its messages. */
  async delete(inboxId: string): Promise<void> {
    await this.client._request("DELETE", `/v1/inboxes/${inboxId}`);
  }

  /** Delete up to 100 inboxes in one call. Returns per-inbox results. */
  async bulkDelete(inboxIds: string[]): Promise<BulkDeleteResult> {
    return this.client._request("DELETE", "/v1/inboxes/bulk", {
      body: { inbox_ids: inboxIds },
    });
  }
}

class Messages {
  constructor(private client: DeadSimple) {}

  /** Send an email from an inbox. */
  async send(opts: {
    inboxId: string;
    to: string | string[];
    subject: string;
    textBody?: string;
    htmlBody?: string;
    cc?: string[];
    bcc?: string[];
    replyTo?: string;
    headers?: Record<string, string>;
    /** Photos to render IN the body: file path, https URL, Buffer, or an upload() ref. */
    images?: AttachmentSource[];
    /** Files to attach as downloads. Same accepted forms as `images`. */
    attachments?: AttachmentSource[];
    idempotencyKey?: string;
  }): Promise<SendResult> {
    const body: Record<string, unknown> = {
      to: Array.isArray(opts.to) ? opts.to : [opts.to],
      subject: opts.subject,
    };
    const prepared = await this.client.attachments._prepare(
      opts.attachments,
      opts.images,
    );
    if (prepared.length) body.attachments = prepared;
    if (opts.textBody) body.text_body = opts.textBody;
    if (opts.htmlBody) body.html_body = opts.htmlBody;
    if (opts.cc) body.cc = opts.cc;
    if (opts.bcc) body.bcc = opts.bcc;
    if (opts.replyTo) body.reply_to = opts.replyTo;
    if (opts.headers) body.headers = opts.headers;
    return this.client._request(
      "POST",
      `/v1/inboxes/${opts.inboxId}/messages`,
      { body, idempotencyKey: opts.idempotencyKey }
    );
  }

  /** List messages in an inbox, newest first. Supports search via `q`. */
  async list(
    inboxId: string,
    opts?: {
      q?: string;
      direction?: string;
      fromEmail?: string;
      limit?: number;
      cursor?: string;
    }
  ): Promise<MessageList> {
    const params: Record<string, string> = {
      limit: String(opts?.limit ?? 50),
    };
    if (opts?.q) params.q = opts.q;
    if (opts?.direction) params.direction = opts.direction;
    if (opts?.fromEmail) params.from = opts.fromEmail;
    if (opts?.cursor) params.cursor = opts.cursor;
    return this.client._request("GET", `/v1/inboxes/${inboxId}/messages`, {
      params,
    });
  }

  /**
   * Block until a NEW inbound message matching the filters arrives, then
   * resolve with the full message (incl. `extracted` verification data).
   * Ideal for signup/OTP flows. Resolves to null on timeout.
   */
  async waitFor(
    inboxId: string,
    opts?: {
      fromContains?: string;
      subjectContains?: string;
      timeoutMs?: number;
      pollIntervalMs?: number;
    }
  ): Promise<MessageFull | null> {
    const timeoutMs = opts?.timeoutMs ?? 60_000;
    const pollIntervalMs = opts?.pollIntervalMs ?? 3_000;
    const fromContains = (opts?.fromContains ?? "").toLowerCase();
    const subjectContains = (opts?.subjectContains ?? "").toLowerCase();
    const deadline = Date.now() + timeoutMs;

    const baseline = new Set(
      (await this.list(inboxId, { direction: "inbound", limit: 50 })).messages.map(
        (m) => m.message_id
      )
    );

    for (;;) {
      const current = await this.list(inboxId, {
        direction: "inbound",
        limit: 50,
      });
      for (const m of current.messages) {
        if (baseline.has(m.message_id)) continue;
        if (fromContains && !(m.from_email ?? "").toLowerCase().includes(fromContains))
          continue;
        if (subjectContains && !(m.subject ?? "").toLowerCase().includes(subjectContains))
          continue;
        return this.get(inboxId, m.message_id);
      }
      if (Date.now() >= deadline) return null;
      await new Promise((r) => setTimeout(r, pollIntervalMs));
    }
  }

  /** Get a single message with full body and headers. */
  async get(inboxId: string, messageId: string): Promise<MessageFull> {
    return this.client._request(
      "GET",
      `/v1/inboxes/${inboxId}/messages/${messageId}`
    );
  }

  /** Reply to a message. Threading headers are set automatically. */
  async reply(
    inboxId: string,
    messageId: string,
    opts: {
      textBody?: string;
      htmlBody?: string;
      images?: AttachmentSource[];
      attachments?: AttachmentSource[];
    }
  ): Promise<SendResult> {
    const body: Record<string, unknown> = {};
    if (opts.textBody) body.text_body = opts.textBody;
    if (opts.htmlBody) body.html_body = opts.htmlBody;
    const preparedreply = await this.client.attachments._prepare(
      opts.attachments,
      opts.images,
    );
    if (preparedreply.length) body.attachments = preparedreply;
    return this.client._request(
      "POST",
      `/v1/inboxes/${inboxId}/messages/${messageId}/reply`,
      { body }
    );
  }

  /** Reply-all to a message. */
  async replyAll(
    inboxId: string,
    messageId: string,
    opts: {
      textBody?: string;
      htmlBody?: string;
      images?: AttachmentSource[];
      attachments?: AttachmentSource[];
    }
  ): Promise<SendResult> {
    const body: Record<string, unknown> = {};
    if (opts.textBody) body.text_body = opts.textBody;
    if (opts.htmlBody) body.html_body = opts.htmlBody;
    const preparedreplyAll = await this.client.attachments._prepare(
      opts.attachments,
      opts.images,
    );
    if (preparedreplyAll.length) body.attachments = preparedreplyAll;
    return this.client._request(
      "POST",
      `/v1/inboxes/${inboxId}/messages/${messageId}/reply-all`,
      { body }
    );
  }

  /** Forward a message to new recipients. */
  async forward(
    inboxId: string,
    messageId: string,
    opts: {
      to: string | string[];
      textBody?: string;
      htmlBody?: string;
      images?: AttachmentSource[];
      attachments?: AttachmentSource[];
    }
  ): Promise<SendResult> {
    const body: Record<string, unknown> = {
      to: Array.isArray(opts.to) ? opts.to : [opts.to],
    };
    if (opts.textBody) body.text_body = opts.textBody;
    if (opts.htmlBody) body.html_body = opts.htmlBody;
    const preparedFwd = await this.client.attachments._prepare(
      opts.attachments,
      opts.images,
    );
    if (preparedFwd.length) body.attachments = preparedFwd;
    return this.client._request(
      "POST",
      `/v1/inboxes/${inboxId}/messages/${messageId}/forward`,
      { body }
    );
  }
}

class Drafts {
  constructor(private client: DeadSimple) {}

  /** Create a draft email for later review and sending (human-in-the-loop). */
  async create(
    inboxId: string,
    opts: {
      to?: string | string[];
      subject?: string;
      textBody?: string;
      htmlBody?: string;
      cc?: string[];
      bcc?: string[];
      replyToMessageId?: string;
    }
  ): Promise<Draft> {
    const body: Record<string, unknown> = {};
    if (opts.to) body.to = Array.isArray(opts.to) ? opts.to : [opts.to];
    if (opts.subject) body.subject = opts.subject;
    if (opts.textBody) body.text_body = opts.textBody;
    if (opts.htmlBody) body.html_body = opts.htmlBody;
    if (opts.cc) body.cc = opts.cc;
    if (opts.bcc) body.bcc = opts.bcc;
    if (opts.replyToMessageId) body.reply_to_message_id = opts.replyToMessageId;
    return this.client._request("POST", `/v1/inboxes/${inboxId}/drafts`, { body });
  }

  async list(inboxId: string): Promise<DraftList> {
    return this.client._request("GET", `/v1/inboxes/${inboxId}/drafts`);
  }

  async get(inboxId: string, draftId: string): Promise<Draft> {
    return this.client._request("GET", `/v1/inboxes/${inboxId}/drafts/${draftId}`);
  }

  async update(
    inboxId: string,
    draftId: string,
    fields: Record<string, unknown>
  ): Promise<Draft> {
    return this.client._request("PUT", `/v1/inboxes/${inboxId}/drafts/${draftId}`, {
      body: fields,
    });
  }

  /** Send a draft — converts it to a real email and deletes the draft. */
  async send(inboxId: string, draftId: string): Promise<SendResult> {
    return this.client._request(
      "POST",
      `/v1/inboxes/${inboxId}/drafts/${draftId}/send`
    );
  }

  async delete(inboxId: string, draftId: string): Promise<void> {
    await this.client._request("DELETE", `/v1/inboxes/${inboxId}/drafts/${draftId}`);
  }
}

class Filters {
  constructor(private client: DeadSimple) {}

  /** Add a filter rule. action: 'block'|'allow'; criteria: 'email'|'domain'|'pattern'|'keyword'. */
  async create(
    inboxId: string,
    opts: { action: string; criteria: string; value: string; description?: string }
  ): Promise<Record<string, unknown>> {
    const body: Record<string, unknown> = {
      action: opts.action,
      criteria: opts.criteria,
      value: opts.value,
    };
    if (opts.description) body.description = opts.description;
    return this.client._request("POST", `/v1/inboxes/${inboxId}/filters`, { body });
  }

  async list(inboxId: string): Promise<Record<string, unknown>> {
    return this.client._request("GET", `/v1/inboxes/${inboxId}/filters`);
  }

  async delete(inboxId: string, filterId: string): Promise<void> {
    await this.client._request(
      "DELETE",
      `/v1/inboxes/${inboxId}/filters/${filterId}`
    );
  }
}

class Templates {
  constructor(private client: DeadSimple) {}

  /** Create a reusable email template with {{variable}} substitution. */
  async create(opts: {
    name: string;
    subject?: string;
    textBody?: string;
    htmlBody?: string;
  }): Promise<Record<string, unknown>> {
    const body: Record<string, unknown> = { name: opts.name };
    if (opts.subject) body.subject = opts.subject;
    if (opts.textBody) body.text_body = opts.textBody;
    if (opts.htmlBody) body.html_body = opts.htmlBody;
    return this.client._request("POST", "/v1/templates", { body });
  }

  async list(): Promise<Record<string, unknown>> {
    return this.client._request("GET", "/v1/templates");
  }

  async get(templateId: string): Promise<Record<string, unknown>> {
    return this.client._request("GET", `/v1/templates/${templateId}`);
  }

  async update(
    templateId: string,
    fields: Record<string, unknown>
  ): Promise<Record<string, unknown>> {
    return this.client._request("PUT", `/v1/templates/${templateId}`, {
      body: fields,
    });
  }

  async delete(templateId: string): Promise<void> {
    await this.client._request("DELETE", `/v1/templates/${templateId}`);
  }
}

class Threads {
  constructor(private client: DeadSimple) {}

  /** List threads across all inboxes (org-wide). Useful for supervisor agents. */
  async listAll(opts?: {
    inboxId?: string;
    labels?: string;
    limit?: number;
    offset?: number;
  }): Promise<ThreadList> {
    const params: Record<string, string> = {
      limit: String(opts?.limit ?? 50),
      offset: String(opts?.offset ?? 0),
    };
    if (opts?.inboxId) params.inbox_id = opts.inboxId;
    if (opts?.labels) params.labels = opts.labels;
    return this.client._request("GET", "/v1/threads", { params });
  }

  /** List threads in an inbox, newest activity first. */
  async list(
    inboxId: string,
    opts?: { limit?: number; offset?: number }
  ): Promise<ThreadList> {
    return this.client._request(
      "GET",
      `/v1/inboxes/${inboxId}/threads`,
      {
        params: {
          limit: String(opts?.limit ?? 50),
          offset: String(opts?.offset ?? 0),
        },
      }
    );
  }

  /** Get all messages in a thread. */
  async get(inboxId: string, threadId: string): Promise<ThreadDetail> {
    return this.client._request(
      "GET",
      `/v1/inboxes/${inboxId}/threads/${threadId}`
    );
  }

  /** Get all attachments across every message in a thread. */
  async getAttachments(
    inboxId: string,
    threadId: string
  ): Promise<{ thread_id: string; attachments: Array<{ attachment_id: string; message_id: string; filename: string; content_type: string; size: number }>; count: number }> {
    return this.client._request(
      "GET",
      `/v1/inboxes/${inboxId}/threads/${threadId}/attachments`
    );
  }
}

class Webhooks {
  constructor(private client: DeadSimple) {}

  /**
   * Register a webhook. Returns signing secret (shown once).
   *
   * `headers` are sent on every delivery attempt (and every retry), for
   * endpoints that require their own auth, e.g.
   * `headers: { Authorization: "Bearer ..." }`. Values are write-only: the API
   * masks them in every response.
   */
  async create(opts: {
    url: string;
    events: string[];
    description?: string;
    headers?: Record<string, string>;
    idempotencyKey?: string;
  }): Promise<Webhook> {
    const body: Record<string, unknown> = {
      url: opts.url,
      events: opts.events,
    };
    if (opts.description) body.description = opts.description;
    if (opts.headers) body.headers = opts.headers;
    return this.client._request("POST", "/v1/webhooks", {
      body,
      idempotencyKey: opts.idempotencyKey,
    });
  }

  /** List all webhooks. */
  async list(): Promise<WebhookList> {
    return this.client._request("GET", "/v1/webhooks");
  }

  /** Delete a webhook. */
  async delete(webhookId: string): Promise<void> {
    await this.client._request("DELETE", `/v1/webhooks/${webhookId}`);
  }

  /** Custom delivery header names for a webhook (values masked). */
  async getHeaders(webhookId: string): Promise<Record<string, string>> {
    const resp = await this.client._request<{ headers?: Record<string, string> }>(
      "GET",
      `/v1/webhooks/${webhookId}/headers`,
    );
    return resp.headers ?? {};
  }

  /** Replace the custom delivery headers. Pass `{}` to clear them. */
  async setHeaders(
    webhookId: string,
    headers: Record<string, string>,
  ): Promise<Record<string, string>> {
    const resp = await this.client._request<{ headers?: Record<string, string> }>(
      "PUT",
      `/v1/webhooks/${webhookId}/headers`,
      { body: { headers } },
    );
    return resp.headers ?? {};
  }
}

class Domains {
  constructor(private client: DeadSimple) {}

  /** Add a custom domain. Returns DNS records to configure. */
  async add(domain: string): Promise<Domain> {
    return this.client._request("POST", "/v1/domains", {
      body: { domain },
    });
  }

  /** List custom domains. */
  async list(): Promise<DomainList> {
    return this.client._request("GET", "/v1/domains");
  }

  /** Check DNS verification status. */
  async verify(domainId: string): Promise<DomainVerification> {
    return this.client._request(
      "GET",
      `/v1/domains/${domainId}/verify`
    );
  }

  /** Remove a custom domain. */
  async delete(domainId: string): Promise<void> {
    await this.client._request("DELETE", `/v1/domains/${domainId}`);
  }
}

class ApiKeys {
  constructor(private client: DeadSimple) {}

  /** Create a new API key. The key value is only returned once. */
  async create(opts: {
    name: string;
    permissions?: string[];
  }): Promise<ApiKey> {
    const body: Record<string, unknown> = { name: opts.name };
    if (opts.permissions) body.permissions = opts.permissions;
    return this.client._request("POST", "/v1/api-keys", { body });
  }

  /** List API keys (secrets are masked). */
  async list(): Promise<ApiKeyList> {
    return this.client._request("GET", "/v1/api-keys");
  }

  /** Revoke an API key. */
  async delete(keyId: string): Promise<void> {
    await this.client._request("DELETE", `/v1/api-keys/${keyId}`);
  }
}

class Workspaces {
  constructor(private client: DeadSimple) {}

  /** Create an isolated workspace with its own scoped API key. */
  async create(opts: {
    name: string;
    description?: string;
    idempotencyKey?: string;
  }): Promise<Workspace> {
    const body: Record<string, unknown> = { name: opts.name };
    if (opts.description) body.description = opts.description;
    return this.client._request("POST", "/v1/workspaces", {
      body,
      idempotencyKey: opts.idempotencyKey,
    });
  }

  /** List all workspaces. */
  async list(): Promise<WorkspaceList> {
    return this.client._request("GET", "/v1/workspaces");
  }

  /** Get a single workspace. */
  async get(workspaceId: string): Promise<Workspace> {
    return this.client._request("GET", `/v1/workspaces/${workspaceId}`);
  }

  /** Update a workspace. */
  async update(
    workspaceId: string,
    opts: { name?: string; description?: string }
  ): Promise<Workspace> {
    const body: Record<string, unknown> = {};
    if (opts.name !== undefined) body.name = opts.name;
    if (opts.description !== undefined) body.description = opts.description;
    return this.client._request("PUT", `/v1/workspaces/${workspaceId}`, {
      body,
    });
  }

  /** Delete a workspace and all its data. */
  async delete(workspaceId: string): Promise<void> {
    await this.client._request("DELETE", `/v1/workspaces/${workspaceId}`);
  }
}

class UsageResource {
  constructor(private client: DeadSimple) {}

  /** Get current usage: inboxes, emails, webhooks, domains. */
  async get(): Promise<Usage> {
    return this.client._request("GET", "/v1/usage");
  }
}


// ── Attachment sources ───────────────────────────────────────────────────────

const BLOCKED_FETCH_HOSTS = new Set([
  "169.254.169.254",
  "metadata.google.internal",
  "localhost",
  "127.0.0.1",
  "::1",
]);

const MAX_FETCH_BYTES = 25 * 1024 * 1024;

const EXT_TYPES: Record<string, string> = {
  jpg: "image/jpeg", jpeg: "image/jpeg", png: "image/png", gif: "image/gif",
  webp: "image/webp", heic: "image/heic", pdf: "application/pdf",
  txt: "text/plain", csv: "text/csv", zip: "application/zip",
};

function guessType(name: string): string {
  const ext = name.includes(".") ? name.split(".").pop()!.toLowerCase() : "";
  return EXT_TYPES[ext] ?? "application/octet-stream";
}

/**
 * Read a path, URL or bytes into upload-ready data.
 *
 * The URL branch also runs server-side in hosted connectors, where the URL is
 * whatever an agent was handed — so internal addresses are refused rather than
 * turned into a request from our own network.
 */
/**
 * Rewrite a Google Drive share link to its direct-download form.
 *
 * A .../file/d/<id>/view link serves an HTML viewer page, so fetching it
 * verbatim attaches a web page named "view" instead of the photo.
 */
function directDownloadUrl(url: string): string {
  const file = url.match(/^https?:\/\/drive\.google\.com\/file\/d\/([^/]+)/);
  if (file) return `https://drive.google.com/uc?export=download&id=${file[1]}`;
  const open = url.match(/^https?:\/\/drive\.google\.com\/open\?id=([^&]+)/);
  if (open) return `https://drive.google.com/uc?export=download&id=${open[1]}`;
  return url;
}

async function readSource(
  source: string | Uint8Array,
  opts?: { expectImage?: boolean },
): Promise<{ data: Uint8Array; filename: string; contentType: string }> {
  if (typeof source !== "string") {
    return { data: source, filename: "attachment", contentType: "application/octet-stream" };
  }

  if (/^https?:\/\//i.test(source)) {
    source = directDownloadUrl(source);
    const url = new URL(source);
    if (BLOCKED_FETCH_HOSTS.has(url.hostname.toLowerCase())) {
      throw new ValidationError(`Refusing to fetch ${source}`, { code: "blocked_url" });
    }
    const resp = await fetch(source, { redirect: "manual" });
    if (!resp.ok) {
      throw new ValidationError(`Could not fetch ${source}: ${resp.status}`, {
        code: "fetch_failed",
      });
    }
    const data = new Uint8Array(await resp.arrayBuffer());
    if (data.byteLength > MAX_FETCH_BYTES) {
      throw new ValidationError(`${source} is larger than 25 MB`, { code: "too_large" });
    }
    const filename = decodeURIComponent(url.pathname.split("/").pop() || "image");
    const contentType =
      resp.headers.get("content-type")?.split(";")[0]?.trim() || guessType(filename);

    // A share link that still returns HTML is a permissions page, not a file.
    // Attaching it silently would mail the recipient a login screen.
    if (opts?.expectImage && !contentType.startsWith("image/")) {
      throw new ValidationError(
        `${source} returned ${contentType || "no content type"} rather than an image. ` +
          "If it is a Google Drive link, the file must be shared as 'anyone with the " +
          "link'; otherwise pass a direct image URL or a local path.",
        { code: "not_an_image" },
      );
    }
    return { data, filename, contentType };
  }

  const { readFile } = await import("node:fs/promises");
  const { basename } = await import("node:path");
  const data = new Uint8Array(await readFile(source));
  const filename = basename(source);
  return { data, filename, contentType: guessType(filename) };
}

export type AttachmentSource =
  | string
  | Uint8Array
  | { attachment_id: string; inline?: boolean };

class Attachments {
  constructor(private client: DeadSimple) {}

  /**
   * Upload a file, URL or bytes and get a reference usable on any message.
   *
   * The bytes go straight to storage rather than through the send request,
   * which is what allows real photos: a send call cannot carry more than a few
   * megabytes.
   */
  async upload(
    source: string | Uint8Array,
    opts?: { filename?: string; contentType?: string; inline?: boolean },
  ): Promise<{ attachment_id: string; inline?: boolean }> {
    const { data, filename, contentType } = await readSource(source, {
      expectImage: opts?.inline,
    });
    const name = opts?.filename ?? filename;
    const type = opts?.contentType ?? contentType;

    const staged = await this.client._request<{
      attachment_id: string;
      upload_url: string;
    }>("POST", "/v1/attachments", {
      body: { filename: name, content_type: type, size: data.byteLength },
    });

    const put = await fetch(staged.upload_url, {
      method: "PUT",
      body: data as BodyInit,
      headers: { "Content-Type": type },
    });
    if (!put.ok) {
      throw new DeadSimpleError(`Attachment upload failed: ${put.status}`, {
        statusCode: put.status,
      });
    }

    return opts?.inline
      ? { attachment_id: staged.attachment_id, inline: true }
      : { attachment_id: staged.attachment_id };
  }

  /** @internal Normalize send()'s attachments/images into API entries. */
  async _prepare(
    attachments?: AttachmentSource[],
    images?: AttachmentSource[],
  ): Promise<Array<Record<string, unknown>>> {
    const pairs: Array<[AttachmentSource, boolean]> = [
      ...(attachments ?? []).map((a) => [a, false] as [AttachmentSource, boolean]),
      ...(images ?? []).map((i) => [i, true] as [AttachmentSource, boolean]),
    ];
    const out: Array<Record<string, unknown>> = [];
    for (const [source, inline] of pairs) {
      if (typeof source === "object" && "attachment_id" in source) {
        out.push(inline ? { ...source, inline: true } : { ...source });
      } else {
        out.push(await this.upload(source, { inline }));
      }
    }
    return out;
  }

  /** Get a time-limited signed download URL for an attachment. */
  async getUrl(
    inboxId: string,
    messageId: string,
    attachmentId: string
  ): Promise<AttachmentUrl> {
    return this.client._request(
      "GET",
      `/v1/inboxes/${inboxId}/messages/${messageId}/attachments/${attachmentId}`
    );
  }
}

/**
 * Real-time event stream via WebSocket.
 *
 * @example
 * ```ts
 * import { WebSocketStream } from "@deadsimple/email";
 *
 * const stream = new WebSocketStream("dse_your_api_key");
 * await stream.connect();
 * await stream.subscribe({ inboxIds: ["..."], events: ["message.received"] });
 * stream.on("event", (event) => console.log(event));
 * ```
 */
export class WebSocketStream {
  private ws: WebSocket | null = null;
  private listeners: Map<string, Array<(data: any) => void>> = new Map();

  constructor(
    private apiKey: string,
    private wsUrl: string = "wss://ws.deadsimple.email"
  ) {}

  /** Connect to the WebSocket server. */
  async connect(): Promise<void> {
    const url = `${this.wsUrl}?api_key=${this.apiKey}`;
    return new Promise((resolve, reject) => {
      this.ws = new WebSocket(url);
      this.ws.onopen = () => resolve();
      this.ws.onerror = (err) => reject(err);
      this.ws.onmessage = (msg) => {
        try {
          const data = JSON.parse(msg.data as string);
          const handlers = this.listeners.get("event") || [];
          for (const handler of handlers) handler(data);
        } catch {}
      };
      this.ws.onclose = () => {
        const handlers = this.listeners.get("close") || [];
        for (const handler of handlers) handler(undefined);
      };
    });
  }

  /** Subscribe to specific inboxes and/or event types. */
  async subscribe(opts?: { inboxIds?: string[]; events?: string[] }): Promise<void> {
    const msg: Record<string, any> = { action: "subscribe" };
    if (opts?.inboxIds) msg.inbox_ids = opts.inboxIds;
    if (opts?.events) msg.events = opts.events;
    this.ws?.send(JSON.stringify(msg));
  }

  /** Register an event listener. */
  on(event: "event" | "close", handler: (data: any) => void): void {
    const list = this.listeners.get(event) || [];
    list.push(handler);
    this.listeners.set(event, list);
  }

  /** Send a keepalive ping. */
  ping(): void {
    this.ws?.send(JSON.stringify({ action: "ping" }));
  }

  /** Close the connection. */
  close(): void {
    this.ws?.close();
    this.ws = null;
  }
}
