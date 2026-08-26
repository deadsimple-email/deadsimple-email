"""Webhook signature verification, in both encodings the server sends."""
import hashlib
import hmac
import time

import pytest

from deadsimple.exceptions import ValidationError
from deadsimple.webhooks import verify_request, verify_signature

SECRET = "whsec_test_secret"
BODY = '{"event":"message.received","data":{"message_id":"msg_1"}}'


def _digest(body: str = BODY, timestamp: int | None = None, secret: str = SECRET) -> tuple[str, str]:
    ts = str(timestamp if timestamp is not None else int(time.time()))
    sig = hmac.new(secret.encode(), f"{ts}.{body}".encode(), hashlib.sha256).hexdigest()
    return ts, sig


def _headers(body: str = BODY, timestamp: int | None = None, both: bool = True) -> dict:
    ts, sig = _digest(body, timestamp)
    headers = {
        "Content-Type": "application/json",
        "X-DSE-Webhook-Id": "wh_1",
        "X-DSE-Webhook-Timestamp": ts,
        "X-DSE-Webhook-Signature": f"sha256={sig}",
    }
    if both:
        headers["X-DSE-Signature"] = f"t={ts},v1={sig}"
    return headers


def test_combined_header_verifies():
    ts, sig = _digest()
    assert verify_signature(BODY, f"t={ts},v1={sig}", SECRET) is True


def test_split_header_verifies_with_timestamp():
    ts, sig = _digest()
    assert verify_signature(BODY, f"sha256={sig}", SECRET, timestamp=ts) is True


def test_split_header_without_timestamp_is_rejected():
    _, sig = _digest()
    with pytest.raises(ValidationError) as exc:
        verify_signature(BODY, f"sha256={sig}", SECRET)
    assert exc.value.code == "missing_timestamp"


def test_bytes_and_str_payloads_agree():
    ts, sig = _digest()
    header = f"t={ts},v1={sig}"
    assert verify_signature(BODY, header, SECRET) is True
    assert verify_signature(BODY.encode(), header, SECRET) is True


def test_verify_request_reads_either_header():
    assert verify_request(BODY, _headers(), SECRET) is True

    split_only = _headers(both=False)
    assert verify_request(BODY, split_only, SECRET) is True

    combined_only = {k: v for k, v in _headers().items() if not k.startswith("X-DSE-Webhook-Sig")}
    assert verify_request(BODY, combined_only, SECRET) is True


def test_verify_request_is_case_insensitive():
    lowered = {k.lower(): v for k, v in _headers().items()}
    assert verify_request(BODY, lowered, SECRET) is True


def test_verify_request_without_any_signature_header():
    with pytest.raises(ValidationError) as exc:
        verify_request(BODY, {"Content-Type": "application/json"}, SECRET)
    assert exc.value.code == "missing_signature"


def test_tampered_body_fails():
    headers = _headers()
    with pytest.raises(ValidationError) as exc:
        verify_request(BODY + " ", headers, SECRET)
    assert exc.value.code == "invalid_signature"


def test_wrong_secret_fails():
    with pytest.raises(ValidationError) as exc:
        verify_request(BODY, _headers(), "whsec_other")
    assert exc.value.code == "invalid_signature"


def test_expired_signature_fails():
    old = int(time.time()) - 3600
    with pytest.raises(ValidationError) as exc:
        verify_request(BODY, _headers(timestamp=old), SECRET)
    assert exc.value.code == "signature_expired"


def test_expired_signature_passes_with_a_wider_tolerance():
    old = int(time.time()) - 3600
    assert verify_request(BODY, _headers(timestamp=old), SECRET, tolerance=7200) is True


def test_malformed_and_empty_signatures():
    with pytest.raises(ValidationError) as exc:
        verify_signature(BODY, "", SECRET)
    assert exc.value.code == "missing_signature"

    with pytest.raises(ValidationError) as exc:
        verify_signature(BODY, "not-a-signature", SECRET)
    assert exc.value.code == "invalid_signature"

    with pytest.raises(ValidationError) as exc:
        verify_signature(BODY, "t=abc,v1=deadbeef", SECRET)
    assert exc.value.code == "invalid_signature"
