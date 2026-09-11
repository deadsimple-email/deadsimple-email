import { describe, it, expect, vi, beforeEach } from "vitest";
import { DeadSimple, AuthenticationError, NotFoundError, RateLimitError, ValidationError } from "./index.js";
import { verifySignature, WebhookVerificationError } from "./webhooks.js";
import { createHmac } from "node:crypto";

const API_KEY = "dse_test_key";
const BASE = "https://api.deadsimple.email";

function wrap(data: unknown) {
  return {
    data,
    meta: { timestamp: "2025-01-01T00:00:00Z", request_id: "test" },
  };
}

// Mock fetch globally
const mockFetch = vi.fn();
vi.stubGlobal("fetch", mockFetch);

function mockResponse(status: number, body: unknown, headers?: Record<string, string>) {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json", ...headers },
  });
}

beforeEach(() => {
  mockFetch.mockReset();
});

// ── Client basics ────────────────────────────────────────────────────────────

describe("DeadSimple client", () => {
  it("throws on missing API key", () => {
    expect(() => new DeadSimple("")).toThrow(AuthenticationError);
  });

  it("constructs with valid key", () => {
    const client = new DeadSimple(API_KEY);
    expect(client).toBeInstanceOf(DeadSimple);
  });
});

// ── Inboxes ──────────────────────────────────────────────────────────────────

describe("inboxes", () => {
  it("creates an inbox", async () => {
    const inboxData = {
      inbox_id: "inb_123",
      email: "abc@deadsimple.email",
      local_part: "abc",
      domain: "deadsimple.email",
      display_name: "Test Bot",
      tags: [],
      status: "active",
      message_count: 0,
      created_at: "2025-01-01T00:00:00Z",
      updated_at: "2025-01-01T00:00:00Z",
    };
    mockFetch.mockResolvedValueOnce(mockResponse(201, wrap(inboxData)));

    const client = new DeadSimple(API_KEY);
    const inbox = await client.inboxes.create({ displayName: "Test Bot" });
    expect(inbox.inbox_id).toBe("inb_123");
    expect(inbox.email).toBe("abc@deadsimple.email");
  });

  it("lists inboxes", async () => {
    mockFetch.mockResolvedValueOnce(
      mockResponse(200, wrap({ inboxes: [], count: 0 }))
    );

    const client = new DeadSimple(API_KEY);
    const result = await client.inboxes.list();
    expect(result.count).toBe(0);
    expect(result.inboxes).toEqual([]);
  });

  it("deletes an inbox", async () => {
    mockFetch.mockResolvedValueOnce(new Response(null, { status: 204 }));

    const client = new DeadSimple(API_KEY);
    await client.inboxes.delete("inb_123"); // Should not throw
  });
});

// ── Messages ─────────────────────────────────────────────────────────────────

describe("messages", () => {
  it("sends a message", async () => {
    mockFetch.mockResolvedValueOnce(
      mockResponse(201, wrap({ message_id: "msg_456", status: "sent" }))
    );

    const client = new DeadSimple(API_KEY);
    const result = await client.messages.send({
      inboxId: "inb_123",
      to: "user@example.com",
      subject: "Test",
      textBody: "Hello",
    });
    expect(result.message_id).toBe("msg_456");
    expect(result.status).toBe("sent");
  });

  it("coerces string `to` to array", async () => {
    mockFetch.mockResolvedValueOnce(
      mockResponse(201, wrap({ message_id: "msg_789", status: "sent" }))
    );

    const client = new DeadSimple(API_KEY);
    await client.messages.send({
      inboxId: "inb_123",
      to: "single@example.com",
      subject: "Test",
    });

    const body = JSON.parse(
      (mockFetch.mock.calls[0][1] as RequestInit).body as string
    );
    expect(body.to).toEqual(["single@example.com"]);
  });
});

// ── Error handling ───────────────────────────────────────────────────────────

describe("error handling", () => {
  it("throws NotFoundError on 404", async () => {
    mockFetch.mockResolvedValueOnce(
      mockResponse(404, {
        error: { message: "Inbox not found", code: "not_found" },
      })
    );

    const client = new DeadSimple(API_KEY);
    await expect(client.inboxes.get("bad_id")).rejects.toThrow(NotFoundError);
  });

  it("throws ValidationError on 400", async () => {
    mockFetch.mockResolvedValueOnce(
      mockResponse(400, {
        error: {
          message: "Invalid email",
          code: "validation",
          details: [{ field: "to", message: "invalid" }],
        },
      })
    );

    const client = new DeadSimple(API_KEY);
    await expect(
      client.messages.send({
        inboxId: "inb_123",
        to: "bad",
        subject: "Test",
      })
    ).rejects.toThrow(ValidationError);
  });

  it("throws RateLimitError with retryAfter", async () => {
    mockFetch.mockResolvedValueOnce(
      mockResponse(
        429,
        { error: { message: "Too many requests", code: "rate_limit" } },
        { "Retry-After": "30" }
      )
    );

    const client = new DeadSimple(API_KEY);
    try {
      await client.inboxes.list();
      expect.unreachable();
    } catch (e) {
      expect(e).toBeInstanceOf(RateLimitError);
      expect((e as RateLimitError).retryAfter).toBe(30);
    }
  });

  it("throws AuthenticationError on 401", async () => {
    mockFetch.mockResolvedValueOnce(
      mockResponse(401, {
        error: { message: "Invalid API key", code: "unauthorized" },
      })
    );

    const client = new DeadSimple(API_KEY);
    await expect(client.inboxes.list()).rejects.toThrow(AuthenticationError);
  });
});

// ── Idempotency ──────────────────────────────────────────────────────────────

describe("idempotency", () => {
  it("sends Idempotency-Key header", async () => {
    const inboxData = {
      inbox_id: "inb_idem",
      email: "x@deadsimple.email",
      local_part: "x",
      domain: "deadsimple.email",
      display_name: "",
      tags: [],
      status: "active",
      message_count: 0,
      created_at: "2025-01-01T00:00:00Z",
      updated_at: "2025-01-01T00:00:00Z",
    };
    mockFetch.mockResolvedValueOnce(mockResponse(201, wrap(inboxData)));

    const client = new DeadSimple(API_KEY);
    await client.inboxes.create({ idempotencyKey: "unique-key-123" });

    const headers = (mockFetch.mock.calls[0][1] as RequestInit)
      .headers as Record<string, string>;
    expect(headers["Idempotency-Key"]).toBe("unique-key-123");
  });
});

// ── Webhook custom headers ───────────────────────────────────────────────────

describe("webhook custom headers", () => {
  const webhookData = {
    webhook_id: "wh_001",
    url: "https://example.com/hook",
    events: ["message.received"],
    description: "",
    is_active: true,
    created_at: "2025-01-01T00:00:00Z",
    failure_count: 0,
  };

  function bodyOf(callIndex: number) {
    return JSON.parse(
      (mockFetch.mock.calls[callIndex][1] as RequestInit).body as string
    );
  }

  it("sends custom headers on create and returns them masked", async () => {
    mockFetch.mockResolvedValueOnce(
      mockResponse(201, wrap({ ...webhookData, headers: { Authorization: "***3456" } }))
    );

    const client = new DeadSimple(API_KEY);
    const wh = await client.webhooks.create({
      url: "https://example.com/hook",
      events: ["message.received"],
      headers: { Authorization: "Bearer tok_abcdef123456" },
    });

    expect(bodyOf(0).headers).toEqual({ Authorization: "Bearer tok_abcdef123456" });
    expect(wh.headers).toEqual({ Authorization: "***3456" });
  });

  it("omits the headers key when none are given", async () => {
    mockFetch.mockResolvedValueOnce(mockResponse(201, wrap(webhookData)));

    const client = new DeadSimple(API_KEY);
    await client.webhooks.create({
      url: "https://example.com/hook",
      events: ["message.received"],
    });

    expect(bodyOf(0)).not.toHaveProperty("headers");
  });

  it("reads masked headers", async () => {
    mockFetch.mockResolvedValueOnce(
      mockResponse(200, wrap({ webhook_id: "wh_001", headers: { Authorization: "***3456" } }))
    );

    const client = new DeadSimple(API_KEY);
    await expect(client.webhooks.getHeaders("wh_001")).resolves.toEqual({
      Authorization: "***3456",
    });
    expect(mockFetch.mock.calls[0][0]).toBe(`${BASE}/v1/webhooks/wh_001/headers`);
  });

  it("replaces headers with a PUT", async () => {
    mockFetch.mockResolvedValueOnce(
      mockResponse(200, wrap({ webhook_id: "wh_001", headers: { Authorization: "***9999" } }))
    );

    const client = new DeadSimple(API_KEY);
    const result = await client.webhooks.setHeaders("wh_001", {
      Authorization: "Bearer rotated_9999",
    });

    expect((mockFetch.mock.calls[0][1] as RequestInit).method).toBe("PUT");
    expect(bodyOf(0)).toEqual({ headers: { Authorization: "Bearer rotated_9999" } });
    expect(result).toEqual({ Authorization: "***9999" });
  });

  it("clears headers with an empty map", async () => {
    mockFetch.mockResolvedValueOnce(
      mockResponse(200, wrap({ webhook_id: "wh_001", headers: {} }))
    );

    const client = new DeadSimple(API_KEY);
    await expect(client.webhooks.setHeaders("wh_001", {})).resolves.toEqual({});
    expect(bodyOf(0)).toEqual({ headers: {} });
  });

  it("defaults to an empty map when the API omits headers", async () => {
    mockFetch.mockResolvedValueOnce(mockResponse(200, wrap({ webhook_id: "wh_001" })));

    const client = new DeadSimple(API_KEY);
    await expect(client.webhooks.getHeaders("wh_001")).resolves.toEqual({});
  });
});

// ── Webhook verification ─────────────────────────────────────────────────────

describe("webhook verification", () => {
  it("verifies a valid signature", () => {
    const secret = "whsec_test_secret";
    const payload = '{"event": "message.received"}';
    const ts = Math.floor(Date.now() / 1000);
    const sig = createHmac("sha256", secret)
      .update(`${ts}.${payload}`)
      .digest("hex");
    const header = `t=${ts},v1=${sig}`;

    expect(
      verifySignature({ payload, signature: header, secret })
    ).toBe(true);
  });

  it("rejects invalid signature", () => {
    const ts = Math.floor(Date.now() / 1000);
    expect(() =>
      verifySignature({
        payload: "payload",
        signature: `t=${ts},v1=badsig`,
        secret: "secret",
      })
    ).toThrow(WebhookVerificationError);
  });

  it("rejects expired signature", () => {
    const secret = "whsec_test";
    const payload = "payload";
    const ts = 1000000; // Very old
    const sig = createHmac("sha256", secret)
      .update(`${ts}.${payload}`)
      .digest("hex");

    expect(() =>
      verifySignature({
        payload,
        signature: `t=${ts},v1=${sig}`,
        secret,
        tolerance: 60,
      })
    ).toThrow(/expired/);
  });

  it("rejects missing signature", () => {
    expect(() =>
      verifySignature({ payload: "x", signature: "", secret: "s" })
    ).toThrow(/Missing/);
  });
});

// ── Parity: drafts, filters, templates, bulkDelete, waitFor ───────────────────

describe("parity resources", () => {
  it("creates a draft", async () => {
    const draft = { draft_id: "d1", inbox_id: "inb_1", to: ["a@x.com"], subject: "Hi", text_body: "yo", html_body: "", created_at: "", updated_at: "" };
    mockFetch.mockResolvedValueOnce(mockResponse(201, wrap(draft)));
    const client = new DeadSimple(API_KEY);
    const out = await client.drafts.create("inb_1", { to: "a@x.com", subject: "Hi", textBody: "yo" });
    expect(out.draft_id).toBe("d1");
    const [url, opts] = mockFetch.mock.calls[0];
    expect(url).toBe(`${BASE}/v1/inboxes/inb_1/drafts`);
    expect(JSON.parse(opts.body).to).toEqual(["a@x.com"]);
  });

  it("sends a draft", async () => {
    mockFetch.mockResolvedValueOnce(mockResponse(200, wrap({ message_id: "m1", status: "sent" })));
    const client = new DeadSimple(API_KEY);
    const out = await client.drafts.send("inb_1", "d1");
    expect(out.status).toBe("sent");
    expect(mockFetch.mock.calls[0][0]).toBe(`${BASE}/v1/inboxes/inb_1/drafts/d1/send`);
  });

  it("creates a filter", async () => {
    mockFetch.mockResolvedValueOnce(mockResponse(201, wrap({ filter_id: "f1" })));
    const client = new DeadSimple(API_KEY);
    await client.filters.create("inb_1", { action: "block", criteria: "domain", value: "evil.com" });
    const [url, opts] = mockFetch.mock.calls[0];
    expect(url).toBe(`${BASE}/v1/inboxes/inb_1/filters`);
    expect(JSON.parse(opts.body).action).toBe("block");
  });

  it("creates a template", async () => {
    mockFetch.mockResolvedValueOnce(mockResponse(201, wrap({ template_id: "t1" })));
    const client = new DeadSimple(API_KEY);
    await client.templates.create({ name: "welcome", subject: "Hi {{name}}" });
    expect(mockFetch.mock.calls[0][0]).toBe(`${BASE}/v1/templates`);
  });

  it("bulk deletes inboxes", async () => {
    mockFetch.mockResolvedValueOnce(mockResponse(200, wrap({ results: [], deleted: 2, failed: 0, total: 2 })));
    const client = new DeadSimple(API_KEY);
    const out = await client.inboxes.bulkDelete(["a", "b"]);
    expect(out.deleted).toBe(2);
    const [url, opts] = mockFetch.mock.calls[0];
    expect(url).toBe(`${BASE}/v1/inboxes/bulk`);
    expect(opts.method).toBe("DELETE");
    expect(JSON.parse(opts.body).inbox_ids).toEqual(["a", "b"]);
  });

  it("waitFor returns a new inbound message with extracted data", async () => {
    const m = (id: string) => ({ message_id: id, inbox_id: "inb_1", thread_id: "t", direction: "inbound", from_email: "noreply@acme.com", from_name: "", to: [], cc: [], subject: "Verify", labels: [], status: "received", snippet: "", attachments: [], created_at: "", received_at: "" });
    // baseline (empty) then a new message m2
    mockFetch
      .mockResolvedValueOnce(mockResponse(200, wrap({ messages: [], count: 0 })))
      .mockResolvedValueOnce(mockResponse(200, wrap({ messages: [m("m2")], count: 1 })))
      .mockResolvedValueOnce(mockResponse(200, wrap({ ...m("m2"), text_body: "code 999", extracted: { verification_code: "999" } })));
    const client = new DeadSimple(API_KEY);
    const msg = await client.messages.waitFor("inb_1", { timeoutMs: 5000, pollIntervalMs: 0 });
    expect(msg?.message_id).toBe("m2");
    expect(msg?.extracted?.verification_code).toBe("999");
  });

  it("waitFor resolves null on timeout", async () => {
    // Fresh Response per call — a Response body can only be read once.
    mockFetch.mockImplementation(() =>
      Promise.resolve(mockResponse(200, wrap({ messages: [], count: 0 })))
    );
    const client = new DeadSimple(API_KEY);
    const msg = await client.messages.waitFor("inb_1", { timeoutMs: 10, pollIntervalMs: 0 });
    expect(msg).toBeNull();
  });
});

// ── Attachments & inline images ──────────────────────────────────────────────

describe("outbound attachments", () => {
  it("uploads images and marks them inline", async () => {
    mockFetch
      .mockResolvedValueOnce(mockResponse(201, wrap({
        attachment_id: "att_1", upload_url: "https://s3.example/put",
      })))
      .mockResolvedValueOnce(new Response(null, { status: 200 }))
      .mockResolvedValueOnce(mockResponse(201, wrap({
        message_id: "m1", status: "sent",
      })));

    const client = new DeadSimple(API_KEY);
    await client.messages.send({
      inboxId: "inb_1", to: "a@b.com", subject: "Photos", textBody: "see below",
      images: [new Uint8Array([1, 2, 3])],
    });

    const sendCall = mockFetch.mock.calls[2];
    const body = JSON.parse((sendCall[1] as RequestInit).body as string);
    expect(body.attachments).toEqual([{ attachment_id: "att_1", inline: true }]);
  });

  it("supports images on reply", async () => {
    mockFetch
      .mockResolvedValueOnce(mockResponse(201, wrap({
        attachment_id: "att_r", upload_url: "https://s3.example/r",
      })))
      .mockResolvedValueOnce(new Response(null, { status: 200 }))
      .mockResolvedValueOnce(mockResponse(201, wrap({ message_id: "m2", status: "sent" })));

    const client = new DeadSimple(API_KEY);
    await client.messages.reply("inb_1", "m_1", {
      textBody: "see photo", images: [new Uint8Array([9])],
    });

    const body = JSON.parse((mockFetch.mock.calls[2][1] as RequestInit).body as string);
    expect(body.attachments).toEqual([{ attachment_id: "att_r", inline: true }]);
  });

  it("sends no attachments key when none are given", async () => {
    mockFetch.mockResolvedValueOnce(mockResponse(201, wrap({ message_id: "m3", status: "sent" })));
    await new DeadSimple(API_KEY).messages.send({
      inboxId: "inb_1", to: "a@b.com", subject: "s", textBody: "t",
    });
    const body = JSON.parse((mockFetch.mock.calls[0][1] as RequestInit).body as string);
    expect(body).not.toHaveProperty("attachments");
  });
});

// ── Calendar invites ─────────────────────────────────────────────────────────
// An attached .ics is a file, not an invitation. These cover the option
// reaching the API and the uid coming back, which a later reschedule or
// cancellation is matched on.

describe("calendar invites", () => {
  it("passes the invite through and returns the uid", async () => {
    mockFetch.mockResolvedValueOnce(mockResponse(201, wrap({
      message_id: "m4", status: "sent", calendar_uid: "u1@deadsimple.email",
    })));

    const client = new DeadSimple(API_KEY);
    const result = await client.messages.send({
      inboxId: "inb_1", to: "t@x.com", subject: "Roof inspection",
      textBody: "Tuesday at 3.",
      calendarInvite: {
        title: "Roof inspection", start: "2026-09-15T15:00:00Z", duration_minutes: 45,
      },
    });

    const body = JSON.parse((mockFetch.mock.calls[0][1] as RequestInit).body as string);
    expect(body.calendar_invite.title).toBe("Roof inspection");
    expect(body.calendar_invite.start).toBe("2026-09-15T15:00:00Z");
    expect(result.calendar_uid).toBe("u1@deadsimple.email");
  });

  it("sends no calendar key when none is given", async () => {
    mockFetch.mockResolvedValueOnce(mockResponse(201, wrap({
      message_id: "m5", status: "sent",
    })));
    await new DeadSimple(API_KEY).messages.send({
      inboxId: "inb_1", to: "a@b.com", subject: "s", textBody: "t",
    });
    const body = JSON.parse((mockFetch.mock.calls[0][1] as RequestInit).body as string);
    expect(body).not.toHaveProperty("calendar_invite");
  });

  it("carries an invite on a reply", async () => {
    mockFetch.mockResolvedValueOnce(mockResponse(201, wrap({
      message_id: "m6", status: "sent", calendar_uid: "u2@deadsimple.email",
    })));
    await new DeadSimple(API_KEY).messages.reply("inb_1", "m1", {
      textBody: "Tuesday works.",
      calendarInvite: { title: "Site visit", start: "2026-09-15T15:00:00Z" },
    });
    const body = JSON.parse((mockFetch.mock.calls[0][1] as RequestInit).body as string);
    expect(body.calendar_invite.title).toBe("Site visit");
  });
});
