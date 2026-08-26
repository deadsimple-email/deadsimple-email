import { describe, expect, it } from "vitest";
import { createHmac } from "node:crypto";
import { verifyRequest, verifySignature, WebhookVerificationError } from "./webhooks";

const SECRET = "whsec_test_secret";
const BODY = '{"event":"message.received","data":{"message_id":"msg_1"}}';

function sign(body = BODY, timestamp?: number, secret = SECRET) {
  const ts = String(timestamp ?? Math.floor(Date.now() / 1000));
  const digest = createHmac("sha256", secret).update(`${ts}.${body}`).digest("hex");
  return { ts, digest };
}

function headers(body = BODY, timestamp?: number, both = true) {
  const { ts, digest } = sign(body, timestamp);
  const out: Record<string, string> = {
    "Content-Type": "application/json",
    "X-DSE-Webhook-Id": "wh_1",
    "X-DSE-Webhook-Timestamp": ts,
    "X-DSE-Webhook-Signature": `sha256=${digest}`,
  };
  if (both) out["X-DSE-Signature"] = `t=${ts},v1=${digest}`;
  return out;
}

function codeOf(fn: () => unknown): string {
  try {
    fn();
  } catch (err) {
    return (err as WebhookVerificationError).code;
  }
  throw new Error("expected a throw");
}

describe("verifySignature", () => {
  it("accepts the combined t=,v1= header", () => {
    const { ts, digest } = sign();
    expect(verifySignature({ payload: BODY, signature: `t=${ts},v1=${digest}`, secret: SECRET })).toBe(true);
  });

  it("accepts the sha256= header when given the timestamp", () => {
    const { ts, digest } = sign();
    expect(
      verifySignature({ payload: BODY, signature: `sha256=${digest}`, secret: SECRET, timestamp: ts })
    ).toBe(true);
  });

  it("rejects a sha256= header with no timestamp", () => {
    const { digest } = sign();
    expect(codeOf(() => verifySignature({ payload: BODY, signature: `sha256=${digest}`, secret: SECRET }))).toBe(
      "missing_timestamp"
    );
  });

  it("treats string and Buffer payloads the same", () => {
    const { ts, digest } = sign();
    const signature = `t=${ts},v1=${digest}`;
    expect(verifySignature({ payload: BODY, signature, secret: SECRET })).toBe(true);
    expect(verifySignature({ payload: Buffer.from(BODY), signature, secret: SECRET })).toBe(true);
  });

  it("rejects missing and malformed signatures", () => {
    expect(codeOf(() => verifySignature({ payload: BODY, signature: "", secret: SECRET }))).toBe("missing_signature");
    expect(codeOf(() => verifySignature({ payload: BODY, signature: "nonsense", secret: SECRET }))).toBe(
      "invalid_signature"
    );
    expect(codeOf(() => verifySignature({ payload: BODY, signature: "t=abc,v1=dead", secret: SECRET }))).toBe(
      "invalid_signature"
    );
  });
});

describe("verifyRequest", () => {
  it("reads either header", () => {
    expect(verifyRequest({ payload: BODY, headers: headers(), secret: SECRET })).toBe(true);
    expect(verifyRequest({ payload: BODY, headers: headers(BODY, undefined, false), secret: SECRET })).toBe(true);
  });

  it("is case-insensitive and handles string[] header values", () => {
    const lowered: Record<string, string | string[]> = {};
    for (const [k, v] of Object.entries(headers())) lowered[k.toLowerCase()] = [v];
    expect(verifyRequest({ payload: BODY, headers: lowered, secret: SECRET })).toBe(true);
  });

  it("accepts a fetch Headers object", () => {
    expect(verifyRequest({ payload: BODY, headers: new Headers(headers()), secret: SECRET })).toBe(true);
  });

  it("rejects a tampered body", () => {
    expect(codeOf(() => verifyRequest({ payload: `${BODY} `, headers: headers(), secret: SECRET }))).toBe(
      "invalid_signature"
    );
  });

  it("rejects the wrong secret", () => {
    expect(codeOf(() => verifyRequest({ payload: BODY, headers: headers(), secret: "whsec_other" }))).toBe(
      "invalid_signature"
    );
  });

  it("rejects a replayed delivery, unless the tolerance is widened", () => {
    const old = Math.floor(Date.now() / 1000) - 3600;
    expect(codeOf(() => verifyRequest({ payload: BODY, headers: headers(BODY, old), secret: SECRET }))).toBe(
      "signature_expired"
    );
    expect(verifyRequest({ payload: BODY, headers: headers(BODY, old), secret: SECRET, tolerance: 7200 })).toBe(true);
  });

  it("rejects a request with no signature header at all", () => {
    expect(
      codeOf(() => verifyRequest({ payload: BODY, headers: { "Content-Type": "application/json" }, secret: SECRET }))
    ).toBe("missing_signature");
  });
});
