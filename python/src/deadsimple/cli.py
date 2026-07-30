"""Dead Simple Email CLI.

Usage:
    dse inboxes list
    dse inboxes create --name "My Bot"
    dse inboxes delete <inbox_id>
    dse send --inbox <inbox_id> --to user@example.com --subject "Hello" --body "Hi there"
    dse messages list <inbox_id>
    dse messages get <inbox_id> <message_id>
    dse webhooks list
    dse webhooks create --url https://example.com/hook --events message.received
    dse usage
    dse templates list
"""
from __future__ import annotations

import json
import os
import sys
from typing import NoReturn

from deadsimple.client import DeadSimple
from deadsimple.exceptions import DeadSimpleError


def _get_key() -> str:
    key = os.environ.get("DSE_API_KEY", "")
    if not key:
        print("Error: DSE_API_KEY environment variable is required.", file=sys.stderr)
        print("  export DSE_API_KEY=dse_your_api_key", file=sys.stderr)
        sys.exit(1)
    return key


def _client() -> DeadSimple:
    return DeadSimple(_get_key())


def _print_json(data: object) -> None:
    """Pretty-print as JSON."""
    if hasattr(data, "__dataclass_fields__"):
        import dataclasses
        data = dataclasses.asdict(data)  # type: ignore[arg-type]
    print(json.dumps(data, indent=2, default=str))


def _error(msg: str) -> NoReturn:
    print(f"Error: {msg}", file=sys.stderr)
    sys.exit(1)


# ── Commands ──────────────────────────────────────────────────────────────────


def cmd_inboxes(args: list[str]) -> None:
    if not args:
        _error("Usage: dse inboxes [list|create|get|delete]")

    sub = args[0]
    client = _client()

    if sub == "list":
        result = client.inboxes.list()
        for inbox in result.inboxes:
            status = "●" if inbox.status == "active" else "○"
            print(f"  {status} {inbox.email:<40} {inbox.display_name or '(unnamed)':<20} {inbox.message_count} msgs")
        print(f"\n{result.count} inbox(es)")

    elif sub == "create":
        name = _flag(args, "--name", "")
        inbox = client.inboxes.create(display_name=name)
        print(f"Created: {inbox.email}")
        print(f"  ID: {inbox.inbox_id}")

    elif sub == "get":
        if len(args) < 2:
            _error("Usage: dse inboxes get <inbox_id>")
        inbox = client.inboxes.get(args[1])
        _print_json(inbox)

    elif sub == "delete":
        if len(args) < 2:
            _error("Usage: dse inboxes delete <inbox_id>")
        client.inboxes.delete(args[1])
        print(f"Deleted: {args[1]}")

    else:
        _error(f"Unknown subcommand: {sub}")


def cmd_send(args: list[str]) -> None:
    inbox_id = _flag(args, "--inbox", "")
    to = _flag(args, "--to", "")
    subject = _flag(args, "--subject", "")
    body = _flag(args, "--body", "")

    if not inbox_id or not to or not subject:
        _error("Usage: dse send --inbox <id> --to <email> --subject <subject> --body <body>")

    client = _client()
    result = client.messages.send(inbox_id=inbox_id, to=to, subject=subject, text_body=body or "(no body)")
    print(f"Sent: {result.message_id} (status: {result.status})")


def cmd_messages(args: list[str]) -> None:
    if not args:
        _error("Usage: dse messages [list|get]")

    sub = args[0]
    client = _client()

    if sub == "list":
        if len(args) < 2:
            _error("Usage: dse messages list <inbox_id>")
        result = client.messages.list(args[1], limit=20)
        for msg in result.messages:
            direction = "←" if msg.direction == "inbound" else "→"
            print(f"  {direction} {msg.from_email:<35} {msg.subject:<40} {msg.message_id[:12]}...")
        print(f"\n{result.count} message(s)")

    elif sub == "get":
        if len(args) < 3:
            _error("Usage: dse messages get <inbox_id> <message_id>")
        msg = client.messages.get(args[1], args[2])
        print(f"From: {msg.from_name or msg.from_email}")
        print(f"To:   {', '.join(msg.to)}")
        print(f"Subject: {msg.subject}")
        print(f"Date: {msg.created_at or msg.received_at}")
        print("---")
        print(msg.latest_reply or msg.text_body or "(no text body)")

    else:
        _error(f"Unknown subcommand: {sub}")


def cmd_webhooks(args: list[str]) -> None:
    if not args:
        _error("Usage: dse webhooks [list|create|delete]")

    sub = args[0]
    client = _client()

    if sub == "list":
        result = client.webhooks.list()
        for wh in result.webhooks:
            status = "●" if wh.is_active else "○"
            events = ", ".join(wh.events)
            print(f"  {status} {wh.url:<50} [{events}]  {wh.webhook_id[:12]}...")
        print(f"\n{result.count} webhook(s)")

    elif sub == "create":
        url = _flag(args, "--url", "")
        events_str = _flag(args, "--events", "message.received")
        if not url:
            _error("Usage: dse webhooks create --url <url> [--events event1,event2]")
        events = [e.strip() for e in events_str.split(",")]
        wh = client.webhooks.create(url=url, events=events)
        print(f"Created webhook: {wh.webhook_id}")
        if wh.signing_secret:
            print(f"  Signing secret: {wh.signing_secret}")
            print("  (Save this — it won't be shown again)")

    elif sub == "delete":
        if len(args) < 2:
            _error("Usage: dse webhooks delete <webhook_id>")
        client.webhooks.delete(args[1])
        print(f"Deleted: {args[1]}")

    else:
        _error(f"Unknown subcommand: {sub}")


def cmd_usage(args: list[str]) -> None:
    client = _client()
    usage = client.usage.get()
    print(f"Plan: {usage.plan_name}")
    print(f"Inboxes:   {usage.inboxes.get('used', 0)} / {usage.inboxes.get('limit', 0)}")
    print(f"Emails:    {usage.emails.get('sent_this_month', 0) + usage.emails.get('received_this_month', 0)} / {usage.emails.get('monthly_limit', 0)} this month")
    print(f"  Sent today:     {usage.emails.get('sent_today', 0)}")
    print(f"  Received today: {usage.emails.get('received_today', 0)}")
    print(f"Webhooks:  {usage.webhooks}")
    print(f"Domains:   {usage.custom_domains.get('used', 0)} / {usage.custom_domains.get('limit', 0)}")


def cmd_templates(args: list[str]) -> None:
    if not args:
        _error("Usage: dse templates [list|create|get|delete]")

    sub = args[0]
    client = _client()

    if sub == "list":
        result = client.templates.list()
        for t in result.get("templates", []):
            vars_str = ", ".join(t.get("variables", []))
            print(f"  {t['name']:<30} vars: {vars_str or '(none)':<30} {t['template_id'][:12]}...")
        print(f"\n{result.get('count', 0)} template(s)")

    elif sub == "create":
        name = _flag(args, "--name", "")
        subject = _flag(args, "--subject", "")
        body = _flag(args, "--body", "")
        if not name:
            _error("Usage: dse templates create --name <name> --subject <subject> --body <body>")
        result = client.templates.create(name, subject=subject, text_body=body)
        print(f"Created template: {result.get('template_id')}")
        if result.get("variables"):
            print(f"  Variables: {', '.join(result['variables'])}")

    elif sub == "delete":
        if len(args) < 2:
            _error("Usage: dse templates delete <template_id>")
        client.templates.delete(args[1])
        print(f"Deleted: {args[1]}")

    else:
        _error(f"Unknown subcommand: {sub}")


# ── Helpers ───────────────────────────────────────────────────────────────────


def _flag(args: list[str], name: str, default: str) -> str:
    """Extract --flag value from args list."""
    for i, arg in enumerate(args):
        if arg == name and i + 1 < len(args):
            return args[i + 1]
    return default


COMMANDS = {
    "inboxes": cmd_inboxes,
    "send": cmd_send,
    "messages": cmd_messages,
    "webhooks": cmd_webhooks,
    "usage": cmd_usage,
    "templates": cmd_templates,
}


def main() -> None:
    args = sys.argv[1:]

    if not args or args[0] in ("-h", "--help", "help"):
        print("Dead Simple Email CLI")
        print()
        print("Usage: dse <command> [args]")
        print()
        print("Commands:")
        print("  inboxes    Manage inboxes (list, create, get, delete)")
        print("  send       Send an email")
        print("  messages   Read messages (list, get)")
        print("  webhooks   Manage webhooks (list, create, delete)")
        print("  templates  Manage email templates (list, create, delete)")
        print("  usage      Show account usage metrics")
        print()
        print("Environment:")
        print("  DSE_API_KEY    Your API key (required)")
        print()
        print("Examples:")
        print('  dse inboxes create --name "Support Bot"')
        print("  dse send --inbox inb_xxx --to user@example.com --subject Hi --body Hello")
        print("  dse messages list inb_xxx")
        print("  dse usage")
        sys.exit(0)

    cmd_name = args[0]
    cmd_args = args[1:]

    handler = COMMANDS.get(cmd_name)
    if not handler:
        _error(f"Unknown command: {cmd_name}. Run 'dse --help' for usage.")

    try:
        handler(cmd_args)
    except DeadSimpleError as e:
        print(f"API Error: {e.message}", file=sys.stderr)
        if e.details:
            for d in e.details:
                print(f"  {d.get('field', '?')}: {d.get('message', '')}", file=sys.stderr)
        sys.exit(1)
    except KeyboardInterrupt:
        sys.exit(130)


if __name__ == "__main__":
    main()
