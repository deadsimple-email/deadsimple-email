"""Webhook signature verification."""

from __future__ import annotations

import hashlib
import hmac
import time

from deadsimple.exceptions import ValidationError


def verify_signature(
    payload: bytes | str,
    signature: str,
    secret: str,
    *,
    tolerance: int = 300,
) -> bool:
    """Verify a webhook signature from Dead Simple Email.

    Args:
        payload: The raw request body (bytes or string).
        signature: The ``X-DSE-Signature`` header value.
            Format: ``t=<timestamp>,v1=<hex_digest>``
        secret: Your webhook signing secret.
        tolerance: Maximum age in seconds (default 300 = 5 minutes).

    Returns:
        True if the signature is valid.

    Raises:
        ValidationError: If the signature is missing, malformed, expired, or invalid.

    Usage::

        from deadsimple.webhooks import verify_signature

        # In your webhook handler:
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

    # Parse "t=123456,v1=abcdef..."
    parts: dict[str, str] = {}
    for segment in signature.split(","):
        if "=" in segment:
            k, v = segment.split("=", 1)
            parts[k.strip()] = v.strip()

    timestamp_str = parts.get("t")
    expected_sig = parts.get("v1")

    if not timestamp_str or not expected_sig:
        raise ValidationError("Malformed signature header", code="invalid_signature")

    try:
        timestamp = int(timestamp_str)
    except ValueError:
        raise ValidationError("Invalid timestamp in signature", code="invalid_signature")

    # Check freshness
    age = abs(time.time() - timestamp)
    if age > tolerance:
        raise ValidationError(
            f"Signature expired ({int(age)}s old, tolerance is {tolerance}s)",
            code="signature_expired",
        )

    # Compute HMAC-SHA256 of "timestamp.payload"
    signed_content = f"{timestamp}.".encode("utf-8") + payload
    computed = hmac.new(secret.encode("utf-8"), signed_content, hashlib.sha256).hexdigest()

    if not hmac.compare_digest(computed, expected_sig):
        raise ValidationError("Signature mismatch", code="invalid_signature")

    return True
