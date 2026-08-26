"""Webhook signature verification.

Dead Simple Email signs every webhook delivery with HMAC-SHA256 over
``"<timestamp>.<raw_body>"`` using the per-webhook signing secret, and sends the
result in two equivalent forms:

- ``X-DSE-Webhook-Signature: sha256=<hex>`` with ``X-DSE-Webhook-Timestamp: <unix>``
- ``X-DSE-Signature: t=<unix>,v1=<hex>``

Both are accepted here. :func:`verify_request` reads whichever is present, which
is the easiest correct thing to call from a request handler.
"""

from __future__ import annotations

import hashlib
import hmac
import time
from typing import Any, Mapping

from deadsimple.exceptions import ValidationError

__all__ = ["verify_signature", "verify_request"]

_SIGNATURE_HEADER = "x-dse-signature"
_WEBHOOK_SIGNATURE_HEADER = "x-dse-webhook-signature"
_WEBHOOK_TIMESTAMP_HEADER = "x-dse-webhook-timestamp"


def _parse(signature: str, timestamp: str | int | None) -> tuple[str, str]:
    """Return (timestamp, hex_digest) from either signature encoding."""
    signature = signature.strip()

    # "sha256=<hex>", paired with a separate timestamp header.
    if signature.startswith("sha256="):
        if timestamp is None:
            raise ValidationError(
                "A sha256= signature needs the X-DSE-Webhook-Timestamp header; "
                "pass timestamp= or use verify_request()",
                code="missing_timestamp",
            )
        return str(timestamp).strip(), signature[len("sha256="):].strip()

    # "t=<unix>,v1=<hex>"
    parts: dict[str, str] = {}
    for segment in signature.split(","):
        if "=" in segment:
            key, value = segment.split("=", 1)
            parts[key.strip()] = value.strip()

    parsed_ts = parts.get("t") or (str(timestamp) if timestamp is not None else None)
    digest = parts.get("v1")
    if not parsed_ts or not digest:
        raise ValidationError("Malformed signature header", code="invalid_signature")
    return parsed_ts, digest


def verify_signature(
    payload: bytes | str,
    signature: str,
    secret: str,
    *,
    timestamp: str | int | None = None,
    tolerance: int = 300,
) -> bool:
    """Verify a webhook signature from Dead Simple Email.

    Args:
        payload: The raw request body, before any JSON parsing. Re-serializing
            changes the bytes and the digest will not match.
        signature: Either the ``X-DSE-Signature`` value (``t=<unix>,v1=<hex>``)
            or the ``X-DSE-Webhook-Signature`` value (``sha256=<hex>``).
        secret: The signing secret returned when the webhook was registered.
        timestamp: The ``X-DSE-Webhook-Timestamp`` value. Required only when
            ``signature`` is the ``sha256=`` form, which carries no timestamp.
        tolerance: Maximum accepted age in seconds (default 300).

    Returns:
        True if the signature is valid.

    Raises:
        ValidationError: If the signature is missing, malformed, expired, or invalid.

    Usage::

        from deadsimple.webhooks import verify_signature

        verify_signature(
            payload=request.body,
            signature=request.headers["X-DSE-Signature"],
            secret="whsec_...",
        )
    """
    if isinstance(payload, str):
        payload = payload.encode("utf-8")

    if not signature:
        raise ValidationError("Missing signature header", code="missing_signature")

    timestamp_str, expected_sig = _parse(signature, timestamp)

    try:
        parsed_timestamp = int(timestamp_str)
    except ValueError:
        raise ValidationError("Invalid timestamp in signature", code="invalid_signature")

    age = abs(time.time() - parsed_timestamp)
    if age > tolerance:
        raise ValidationError(
            f"Signature expired ({int(age)}s old, tolerance is {tolerance}s)",
            code="signature_expired",
        )

    signed_content = f"{parsed_timestamp}.".encode("utf-8") + payload
    computed = hmac.new(secret.encode("utf-8"), signed_content, hashlib.sha256).hexdigest()

    if not hmac.compare_digest(computed, expected_sig):
        raise ValidationError("Signature mismatch", code="invalid_signature")

    return True


def verify_request(
    payload: bytes | str,
    headers: Mapping[str, Any],
    secret: str,
    *,
    tolerance: int = 300,
) -> bool:
    """Verify a webhook from a request's raw body and headers.

    Reads whichever signature header is present, so it works regardless of which
    form the delivery used. Header lookup is case-insensitive.

    Usage::

        from deadsimple.webhooks import verify_request

        verify_request(payload=request.body, headers=request.headers, secret="whsec_...")
    """
    lowered = {str(k).lower(): v for k, v in dict(headers).items()}

    combined = lowered.get(_SIGNATURE_HEADER)
    if combined:
        return verify_signature(payload, str(combined), secret, tolerance=tolerance)

    split = lowered.get(_WEBHOOK_SIGNATURE_HEADER)
    if split:
        return verify_signature(
            payload,
            str(split),
            secret,
            timestamp=lowered.get(_WEBHOOK_TIMESTAMP_HEADER),
            tolerance=tolerance,
        )

    raise ValidationError("Missing signature header", code="missing_signature")
