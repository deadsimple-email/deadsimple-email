"""Tests for framework integrations — the framework-agnostic paths.

Covers the shared formatting helpers plus the OpenAI Agents and AutoGen
integrations, which expose their tools without importing a heavy framework.
"""
from __future__ import annotations

import json
from types import SimpleNamespace

from deadsimple.integrations import _common


def _fake_msg(code=None, link=None, subject="Verify", frm="noreply@acme.com"):
    return SimpleNamespace(
        from_email=frm, subject=subject, latest_reply="Your code is 123456", text_body="",
        extracted={k: v for k, v in (("verification_code", code), ("magic_link_url", link)) if v},
    )


# ── shared helpers ────────────────────────────────────────────────────────────

def test_describe_email_timeout():
    assert "within 30s" in _common.describe_email(None, 30)


def test_describe_email_includes_extracted():
    out = _common.describe_email(_fake_msg(code="999", link="https://a.co/x"), 60)
    assert "noreply@acme.com" in out
    assert "Verification code: 999" in out
    assert "Magic link: https://a.co/x" in out


def test_describe_verification_code_and_link():
    out = _common.describe_verification(_fake_msg(code="999", link="https://a.co/x"), 60)
    assert "code: 999" in out and "link: https://a.co/x" in out


def test_describe_verification_none_found():
    out = _common.describe_verification(_fake_msg(), 60)
    assert "no verification code or link" in out


# ── OpenAI Agents integration ─────────────────────────────────────────────────

def test_openai_agents_definitions_include_new_tools():
    from deadsimple.integrations import openai_agents

    names = {d["function"]["name"] for d in openai_agents.get_function_definitions()}
    assert {"wait_for_email", "get_verification_code"} <= names
    assert {"wait_for_email", "get_verification_code"} <= set(openai_agents.TOOL_MAP)


def test_openai_agents_handle_tool_call_dispatches(monkeypatch):
    from deadsimple.integrations import openai_agents

    fake_client = SimpleNamespace(
        messages=SimpleNamespace(wait_for=lambda *a, **k: _fake_msg(code="777"))
    )
    monkeypatch.setattr(openai_agents, "_client", fake_client)

    out = json.loads(openai_agents.handle_tool_call("get_verification_code", {"inbox_id": "inb_1"}))
    assert out["verification_code"] == "777"


# ── AutoGen integration ───────────────────────────────────────────────────────

def test_autogen_exposes_new_tools():
    from deadsimple.integrations import autogen

    names = {fn.__name__ for fn in autogen.get_tools()}
    assert {"wait_for_email", "get_verification_code"} <= names
