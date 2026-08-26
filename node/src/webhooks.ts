/**
 * Webhook signature verification for Dead Simple Email.
 *
 * Every delivery is signed with HMAC-SHA256 over `"<timestamp>.<raw_body>"` using
 * the per-webhook signing secret, and sent in two equivalent forms:
 *
 * - `X-DSE-Webhook-Signature: sha256=<hex>` with `X-DSE-Webhook-Timestamp: <unix>`
 * - `X-DSE-Signature: t=<unix>,v1=<hex>`
 *
 * Both are accepted. `verifyRequest` reads whichever is present, which is the
 * easiest correct thing to call from a handler.
 *
 * @example
 * ```ts
 * import { verifyRequest } from "deadsimple-email/webhooks";
 *
 * // In your webhook handler (e.g., Express, Hono):
 * verifyRequest({
 *   payload: req.rawBody,
 *   headers: req.headers,
 *   secret: "whsec_your_signing_secret",
 * });
 * ```
 */

import { createHmac, timingSafeEqual } from "node:crypto";

export class WebhookVerificationError extends Error {
  code: string;
  constructor(message: string, code: string) {
    super(message);
    this.name = "WebhookVerificationError";
    this.code = code;
  }
}

const SIGNATURE_HEADER = "x-dse-signature";
const WEBHOOK_SIGNATURE_HEADER = "x-dse-webhook-signature";
const WEBHOOK_TIMESTAMP_HEADER = "x-dse-webhook-timestamp";

/** Pull (timestamp, hex digest) out of either signature encoding. */
function parseSignature(
  signature: string,
  timestamp?: string | number
): { timestamp: string; digest: string } {
  const value = signature.trim();

  // "sha256=<hex>", paired with a separate timestamp header.
  if (value.startsWith("sha256=")) {
    if (timestamp === undefined || timestamp === null || timestamp === "") {
      throw new WebhookVerificationError(
        "A sha256= signature needs the X-DSE-Webhook-Timestamp header; pass timestamp or use verifyRequest()",
        "missing_timestamp"
      );
    }
    return { timestamp: String(timestamp).trim(), digest: value.slice("sha256=".length).trim() };
  }

  // "t=<unix>,v1=<hex>"
  const parts: Record<string, string> = {};
  for (const segment of value.split(",")) {
    const eqIdx = segment.indexOf("=");
    if (eqIdx > 0) {
      parts[segment.slice(0, eqIdx).trim()] = segment.slice(eqIdx + 1).trim();
    }
  }

  const ts = parts.t ?? (timestamp !== undefined ? String(timestamp) : undefined);
  const digest = parts.v1;
  if (!ts || !digest) {
    throw new WebhookVerificationError("Malformed signature header", "invalid_signature");
  }
  return { timestamp: ts, digest };
}

/**
 * Verify a webhook signature from Dead Simple Email.
 *
 * @param opts.payload - The raw request body (string or Buffer), before JSON parsing.
 * @param opts.signature - Either `X-DSE-Signature` (`t=<unix>,v1=<hex>`) or
 *   `X-DSE-Webhook-Signature` (`sha256=<hex>`).
 * @param opts.secret - Your webhook signing secret.
 * @param opts.timestamp - The `X-DSE-Webhook-Timestamp` value. Required only for
 *   the `sha256=` form, which carries no timestamp of its own.
 * @param opts.tolerance - Maximum age in seconds (default 300 = 5 minutes).
 * @returns `true` if the signature is valid.
 * @throws {WebhookVerificationError} If the signature is missing, malformed, expired, or invalid.
 */
export function verifySignature(opts: {
  payload: string | Buffer;
  signature: string;
  secret: string;
  timestamp?: string | number;
  tolerance?: number;
}): true {
  const { payload, signature, secret, tolerance = 300 } = opts;

  if (!signature) {
    throw new WebhookVerificationError("Missing signature header", "missing_signature");
  }

  const { timestamp: timestampStr, digest: expectedSig } = parseSignature(
    signature,
    opts.timestamp
  );

  const timestamp = parseInt(timestampStr, 10);
  if (isNaN(timestamp)) {
    throw new WebhookVerificationError("Invalid timestamp in signature", "invalid_signature");
  }

  // Check freshness
  const age = Math.abs(Date.now() / 1000 - timestamp);
  if (age > tolerance) {
    throw new WebhookVerificationError(
      `Signature expired (${Math.floor(age)}s old, tolerance is ${tolerance}s)`,
      "signature_expired"
    );
  }

  // Compute HMAC-SHA256 of "timestamp.payload"
  const payloadBuf =
    typeof payload === "string" ? Buffer.from(payload, "utf-8") : payload;
  const signedContent = Buffer.concat([Buffer.from(`${timestamp}.`), payloadBuf]);
  const computed = createHmac("sha256", secret).update(signedContent).digest("hex");

  // Timing-safe comparison
  const expectedBuf = Buffer.from(expectedSig, "utf-8");
  const computedBuf = Buffer.from(computed, "utf-8");

  if (
    expectedBuf.length !== computedBuf.length ||
    !timingSafeEqual(expectedBuf, computedBuf)
  ) {
    throw new WebhookVerificationError("Signature mismatch", "invalid_signature");
  }

  return true;
}

/**
 * Verify a webhook from a request's raw body and headers.
 *
 * Reads whichever signature header is present, so it works regardless of which
 * form the delivery used. Header lookup is case-insensitive, and Node's
 * `string[]` header values are handled.
 *
 * @throws {WebhookVerificationError} If no signature header is present, or verification fails.
 */
export function verifyRequest(opts: {
  payload: string | Buffer;
  headers: Record<string, string | string[] | undefined> | Headers;
  secret: string;
  tolerance?: number;
}): true {
  const { payload, headers, secret, tolerance } = opts;

  const lowered: Record<string, string> = {};
  if (typeof (headers as Headers).forEach === "function" && !Array.isArray(headers)) {
    (headers as Headers).forEach((value, key) => {
      lowered[key.toLowerCase()] = value;
    });
  } else {
    for (const [key, value] of Object.entries(
      headers as Record<string, string | string[] | undefined>
    )) {
      if (value === undefined) continue;
      lowered[key.toLowerCase()] = Array.isArray(value) ? value[0] : value;
    }
  }

  const combined = lowered[SIGNATURE_HEADER];
  if (combined) {
    return verifySignature({ payload, signature: combined, secret, tolerance });
  }

  const split = lowered[WEBHOOK_SIGNATURE_HEADER];
  if (split) {
    return verifySignature({
      payload,
      signature: split,
      secret,
      timestamp: lowered[WEBHOOK_TIMESTAMP_HEADER],
      tolerance,
    });
  }

  throw new WebhookVerificationError("Missing signature header", "missing_signature");
}
