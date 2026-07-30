"""Shared formatting helpers for framework integrations.

Keeps the wait_for_email / verification-code tool output consistent across
LangChain, CrewAI, LlamaIndex, AutoGen, and OpenAI Agents.
"""
from __future__ import annotations

from typing import Any


def describe_email(msg: Any, timeout_seconds: int) -> str:
    """Render a waited-for message (or a timeout notice) for an agent."""
    if not msg:
        return f"No matching email arrived within {timeout_seconds}s."
    body = getattr(msg, "latest_reply", "") or getattr(msg, "text_body", "") or "(no text body)"
    extracted = getattr(msg, "extracted", {}) or {}
    extra = ""
    if extracted.get("verification_code"):
        extra += f"\nVerification code: {extracted['verification_code']}"
    if extracted.get("magic_link_url"):
        extra += f"\nMagic link: {extracted['magic_link_url']}"
    return (
        f"From: {msg.from_email}\n"
        f"Subject: {msg.subject}\n"
        f"---\n{body}{extra}"
    )


def describe_verification(msg: Any, timeout_seconds: int) -> str:
    """Render the extracted verification code / magic link (or a notice)."""
    if not msg:
        return f"No email arrived within {timeout_seconds}s."
    extracted = getattr(msg, "extracted", {}) or {}
    code = extracted.get("verification_code")
    link = extracted.get("magic_link_url")
    if not code and not link:
        return f"Email received from {msg.from_email} but no verification code or link was found."
    parts = []
    if code:
        parts.append(f"code: {code}")
    if link:
        parts.append(f"link: {link}")
    return " | ".join(parts)
