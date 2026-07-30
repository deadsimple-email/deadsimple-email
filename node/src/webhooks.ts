/**
 * Webhook signature verification for Dead Simple Email.
 *
 * @example
 * ```ts
 * import { verifySignature } from "deadsimple-email/webhooks";
 *
 * // In your webhook handler (e.g., Express, Hono):
 * verifySignature({
 *   payload: req.body,
 *   signature: req.headers["x-dse-signature"],
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

/**
 * Verify a webhook signature from Dead Simple Email.
 *
 * @param opts.payload - The raw request body (string or Buffer).
 * @param opts.signature - The `X-DSE-Signature` header value. Format: `t=<timestamp>,v1=<hex_digest>`
 * @param opts.secret - Your webhook signing secret.
 * @param opts.tolerance - Maximum age in seconds (default 300 = 5 minutes).
 * @returns `true` if the signature is valid.
 * @throws {WebhookVerificationError} If the signature is missing, malformed, expired, or invalid.
 */
export function verifySignature(opts: {
  payload: string | Buffer;
  signature: string;
  secret: string;
  tolerance?: number;
}): true {
  const { payload, signature, secret, tolerance = 300 } = opts;

  if (!signature) {
    throw new WebhookVerificationError(
      "Missing signature header",
      "missing_signature"
    );
  }

  // Parse "t=123456,v1=abcdef..."
  const parts: Record<string, string> = {};
  for (const segment of signature.split(",")) {
    const eqIdx = segment.indexOf("=");
    if (eqIdx > 0) {
      parts[segment.slice(0, eqIdx).trim()] = segment.slice(eqIdx + 1).trim();
    }
  }

  const timestampStr = parts.t;
  const expectedSig = parts.v1;

  if (!timestampStr || !expectedSig) {
    throw new WebhookVerificationError(
      "Malformed signature header",
      "invalid_signature"
    );
  }

  const timestamp = parseInt(timestampStr, 10);
  if (isNaN(timestamp)) {
    throw new WebhookVerificationError(
      "Invalid timestamp in signature",
      "invalid_signature"
    );
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
  const signedContent = Buffer.concat([
    Buffer.from(`${timestamp}.`),
    payloadBuf,
  ]);
  const computed = createHmac("sha256", secret)
    .update(signedContent)
    .digest("hex");

  // Timing-safe comparison
  const expectedBuf = Buffer.from(expectedSig, "utf-8");
  const computedBuf = Buffer.from(computed, "utf-8");

  if (
    expectedBuf.length !== computedBuf.length ||
    !timingSafeEqual(expectedBuf, computedBuf)
  ) {
    throw new WebhookVerificationError(
      "Signature mismatch",
      "invalid_signature"
    );
  }

  return true;
}
