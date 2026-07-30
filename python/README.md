# Dead Simple Email — Python SDK

<!-- mcp-name: email.deadsimple/dead-simple-email -->

The official Python SDK for [Dead Simple Email](https://deadsimple.email), the email API for AI agents.

- **Typed responses** — dataclass models with IDE autocompletion, not raw dicts
- **Sync + async** — `DeadSimple` for synchronous code, `AsyncDeadSimple` for async/await
- **Idempotency** — pass `idempotency_key` to any create/send method for safe retries
- **Webhook verification** — HMAC-SHA256 signature validation built in
- **Full API coverage** — inboxes, messages, threads, webhooks, domains, API keys, workspaces, usage, attachments

## Install

```bash
pip install deadsimple-email
```

## Quick Start

```python
from deadsimple import DeadSimple

client = DeadSimple("dse_your_api_key")

# Create an inbox
inbox = client.inboxes.create(display_name="Support Bot")
print(f"Inbox: {inbox.email}")

# Send an email
result = client.messages.send(
    inbox_id=inbox.inbox_id,
    to="user@example.com",
    subject="Hello from my AI agent",
    text_body="This email was sent by an AI agent using Dead Simple Email.",
)
print(f"Sent: {result.message_id}")

# Read received messages
messages = client.messages.list(inbox_id=inbox.inbox_id)
for msg in messages.messages:
    print(f"  {msg.from_email}: {msg.subject}")

# Reply to a message
client.messages.reply(
    inbox_id=inbox.inbox_id,
    message_id=messages.messages[0].message_id,
    text_body="Thanks for your email!",
)

# List conversation threads
threads = client.threads.list(inbox_id=inbox.inbox_id)
for t in threads.threads:
    print(f"  Thread: {t.subject} ({t.message_count} messages)")

# Register a webhook for real-time notifications
webhook = client.webhooks.create(
    url="https://your-app.com/webhook",
    events=["message.received"],
)
print(f"Webhook secret: {webhook.signing_secret}")
```

## Agent Self-Onboarding (OTP / magic links)

Give an agent a real inbox and it can sign *itself* up for other services —
receive the confirmation email, pull the code or link, and finish the flow with
no human and no MIME parsing. Every inbound email is also scanned for prompt
injection, so the agent knows what's safe to act on.

```python
from datetime import datetime, timezone

inbox = client.inboxes.create(display_name="Signup Bot")

# 1. Kick off the signup on the target service using inbox.email ...
#    (fill the form / call their API with inbox.email)

# 2. Wait for the verification email and get the code in one call.
#    `since` ignores any older code already sitting in the inbox.
started = datetime.now(timezone.utc).isoformat()
result = client.inboxes.wait_for_verification(
    inbox.inbox_id,
    from_contains="stripe.com",   # optional: only this sender
    since=started,
    timeout=90,
)

if result:
    print("Code:", result["verification_code"])   # e.g. "482913"
    print("Link:", result["magic_link_url"])       # magic link, if any
    # 3. Submit the code / open the link to finish signing up.
```

`get_verification()` is the non-blocking version — it returns immediately with
`found=False` if nothing has arrived yet, so you can poll on your own schedule.
Both wrap `GET /v1/inboxes/{id}/verification`, which works from any language.

## Async Usage

```python
from deadsimple import AsyncDeadSimple

async with AsyncDeadSimple("dse_your_api_key") as client:
    inbox = await client.inboxes.create(display_name="Async Bot")
    await client.messages.send(
        inbox_id=inbox.inbox_id,
        to="user@example.com",
        subject="Hello from async",
        text_body="Sent asynchronously.",
    )
```

## Bulk Operations

```python
# Create 50 inboxes at once
result = client.inboxes.bulk_create([
    {"display_name": f"Agent {i}", "tags": ["batch-1"]}
    for i in range(50)
])
print(f"Created {result.created}, failed {result.failed}")
```

## Custom Domains

```python
# Add your domain
domain = client.domains.add("mail.yourcompany.com")

# Shows DNS records to configure
for record in domain.dns_records:
    print(f"  {record['type']} {record['name']} -> {record['value']}")

# Check verification
status = client.domains.verify(domain.domain_id)
print(f"Status: {status.status}")
```

## Multi-Tenant Workspaces

```python
# Create an isolated namespace for a customer
workspace = client.workspaces.create(name="customer-acme", description="Acme Corp")
print(f"Workspace API key: {workspace.api_key['key']}")

# Use the workspace's scoped API key for isolated access
acme_client = DeadSimple(workspace.api_key["key"])
acme_inbox = acme_client.inboxes.create(display_name="Acme Support")
```

## Idempotent Requests

```python
import uuid

# Safe to retry — same key = same result, no duplicates
key = str(uuid.uuid4())
inbox = client.inboxes.create(display_name="Bot", idempotency_key=key)
inbox_again = client.inboxes.create(display_name="Bot", idempotency_key=key)  # Returns same inbox
```

## Webhook Signature Verification

```python
from deadsimple.webhooks import verify_signature

# In your webhook handler (e.g., Flask, FastAPI):
try:
    verify_signature(
        payload=request.body,
        signature=request.headers["X-DSE-Signature"],
        secret="whsec_your_signing_secret",
    )
    # Signature valid — process the event
except Exception:
    # Signature invalid — reject the request
    return Response(status_code=401)
```

## Usage Metrics

```python
usage = client.usage.get()
print(f"Plan: {usage.plan_name}")
print(f"Inboxes: {usage.inboxes['used']} / {usage.inboxes['limit']}")
print(f"Emails this month: {usage.emails['sent_this_month']}")
```

## Error Handling

```python
from deadsimple import DeadSimple, RateLimitError, NotFoundError, ValidationError
import time

client = DeadSimple("dse_your_api_key")

try:
    inbox = client.inboxes.get("nonexistent")
except NotFoundError:
    print("Inbox not found")
except RateLimitError as e:
    print(f"Rate limited, retry in {e.retry_after}s")
    time.sleep(e.retry_after)
except ValidationError as e:
    print(f"Bad request: {e.message}")
    for detail in e.details:
        print(f"  {detail['field']}: {detail['message']}")
```

## All Resources

| Resource | Methods |
|----------|---------|
| `client.inboxes` | `create`, `bulk_create`, `list`, `get`, `update`, `delete` |
| `client.messages` | `send`, `list`, `get`, `reply`, `reply_all`, `forward` |
| `client.threads` | `list`, `get` |
| `client.webhooks` | `create`, `list`, `delete` |
| `client.domains` | `add`, `list`, `verify`, `delete` |
| `client.api_keys` | `create`, `list`, `delete` |
| `client.workspaces` | `create`, `list`, `get`, `update`, `delete` |
| `client.usage` | `get` |
| `client.attachments` | `get_url` |

## Pricing

| Plan | Price | Inboxes | Emails/mo |
|------|-------|---------|-----------|
| Free | $0 | 5 | 5,000 |
| Hobby | $5/mo | 15 | 15,000 |
| Pro | $29/mo | 100 | 100,000 |
| Scale | $99/mo | 500 | 500,000 |

Webhook signing included on **all plans** (competitors charge $200/mo).

## License

MIT
