# Dead Simple Email — Python SDK

<!-- mcp-name: email.deadsimple/dead-simple-email -->

The official Python SDK for [Dead Simple Email](https://deadsimple.email), the email API for AI agents.

- **Typed responses**: dataclass models with IDE autocompletion, not raw dicts
- **Sync + async**: `DeadSimple` for synchronous code, `AsyncDeadSimple` for async/await
- **Idempotency**: pass `idempotency_key` to any create/send method for safe retries
- **Webhook verification**: HMAC-SHA256 signature validation built in
- **Sign in with Dead Simple**: the inbox is the agent's OpenID Connect login, see [Identity](#identity-sign-in-with-an-inbox)
- **Full API coverage**: inboxes, messages, threads, webhooks, domains, API keys, workspaces, usage, attachments, identity
- **No API key?** Priced routes answer `402` and take USDC or a card inline, see [Pay per request](#no-api-key-pay-per-request)

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
    # Optional: headers your endpoint requires, sent on every attempt and retry
    headers={"Authorization": "Bearer your-endpoint-token"},
)
print(f"Webhook secret: {webhook.signing_secret}")

# Rotate or clear those headers later
client.webhooks.set_headers(webhook.webhook_id, {"Authorization": "Bearer rotated"})
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

## Identity: sign in with an inbox

[Sign in with Dead Simple](https://deadsimple.email/identity.html) is a free
OpenID Connect provider at `https://id.deadsimple.email` where the identity is
an agent's inbox. Any app that accepts a generic OIDC provider (Auth.js, Better
Auth, Clerk, Auth0, ...) can let your agent sign up and sign in. The app gets a
stable `sub` (the `inbox_id`), the inbox address as a verified email and, for
registered apps, the verified human owner behind the agent. Verification mail
from the app lands in the same inbox, so the whole loop stays headless.

### Signing an agent in

An app's "Sign in with Dead Simple" button points at an authorization URL
(`https://id.deadsimple.email/authorize?...`). Hand that URL to `sign_in` and
the SDK authenticates as the inbox with the API key it already holds. With
`follow=True` (the default) the redirect back to the app is fetched as well, so
the app has exchanged the code by the time the call returns.

```python
inbox = client.inboxes.create(display_name="Research Bot")

# 1. Start the app's login (submit its form / call its API) and capture the
#    https://id.deadsimple.email/authorize?... URL it sends you to.
authorization_url = (
    "https://id.deadsimple.email/authorize?response_type=code"
    "&client_id=https%3A%2F%2Fapp.example.com"
    "&redirect_uri=https%3A%2F%2Fapp.example.com%2Fapi%2Fauth%2Fcallback%2Fdeadsimple"
    "&scope=openid%20email%20profile&state=xyz"
    "&code_challenge=E9Melhoa2OwvFrEMTJguCHaoeK1t8URWbuGJSstw-cM&code_challenge_method=S256"
)

# 2. Sign in as the inbox. The app receives inbox.email as the account email.
result = client.identity.sign_in(inbox.inbox_id, authorization_url)
print(result["client_name"])    # "app.example.com"
print(result["final_url"])      # where the app landed after exchanging the code
print(result["final_status"])   # 200

# Drive the HTTP client yourself instead (your own cookies or session):
result = client.identity.sign_in(inbox.inbox_id, authorization_url, follow=False)
session.get(result["redirect_to"])   # the app's callback URL with code and state

# Apps this inbox has signed in to
for c in client.identity.connections(inbox.inbox_id)["connections"]:
    print(f"  {c['client_name']}: {c['sign_in_count']} sign-ins")
```

`AsyncDeadSimple` exposes the same methods under `await client.identity...`.

### Signing in with a key the agent holds, not an API key

For a worker that should not hold mailbox access, enroll a P-256 public key on
the inbox once and keep the private key on the worker. At sign-in time the
worker signs a short-lived ES256 assertion and posts it to `/authorize` itself.
Deleting the key revokes sign-in without touching any API key, and `list_keys`
shows `last_used_at` per key so an idle one is easy to spot. Building the
assertion needs `pip install "pyjwt[crypto]"`.

```python
# Once, from a process that holds the API key: enroll the worker's public key.
# openssl ecparam -name prime256v1 -genkey -noout -out worker.pem
# openssl ec -in worker.pem -pubout -out worker.pub.pem
key = client.identity.enroll_key(
    inbox.inbox_id,
    public_key=open("worker.pub.pem").read(),   # PEM or JWK, both accepted
    name="worker-7",
)
print(key["kid"])

client.identity.list_keys(inbox.inbox_id)          # {"keys": [...], "total": 1}
client.identity.delete_key(inbox.inbox_id, kid)    # revoke
```

```python
# Later, on the worker, with only worker.pem, the kid and the inbox_id.
# make_assertion is a static helper and needs no client or API key.
from urllib.parse import parse_qsl, urlparse
import httpx
from deadsimple import make_assertion

params = dict(parse_qsl(urlparse(authorization_url).query))
assertion = make_assertion(
    inbox_id,
    open("worker.pem").read(),
    kid,
    client_id=params["client_id"],               # optional bindings; when present
    code_challenge=params["code_challenge"],     # they must match the request
    ttl=120,                                     # capped at 600 seconds
)

r = httpx.post(
    "https://id.deadsimple.email/authorize",
    data={**params, "assertion": assertion},
    headers={"Accept": "application/json"},
)
redirect_to = r.json()["redirect_to"]
httpx.get(redirect_to, follow_redirects=True)     # the app exchanges the code
```

### Relying party: accept agents in your own app

If you are the app, point your auth library at
`https://id.deadsimple.email/.well-known/openid-configuration`. An open client
needs no registration at all: `client_id` is your https origin and PKCE carries
the security. Register a client when you want a `client_secret`, refresh
tokens, or the `owner_email` and `org` scopes that tell one operator running
many agents from many users.

```python
rp = client.identity.register_client(
    "Acme SaaS",
    ["https://acme.example/auth/callback"],
    client_uri="https://acme.example",
)
print(rp["client_id"])       # dse_idc_...
print(rp["client_secret"])   # dse_ics_..., shown once
print(rp["discovery_url"])   # paste into Auth.js, Better Auth, Clerk, Auth0, ...

client.identity.list_clients()
client.identity.delete_client(rp["client_id"])
```

Trial keys from agent self-signup cannot register clients. Framework snippets
for Auth.js, Better Auth, Clerk, Supabase and Auth0 are on the
[identity page](https://deadsimple.email/identity.html).

## No API key? Pay per request

An agent with a wallet and no account can still use the API. Call a priced
route with no `Authorization` header and it answers `402 Payment Required`
with a `PAYMENT-REQUIRED` header (x402: USDC on Base, Polygon or Solana) and,
for inbox creation, a `WWW-Authenticate: Payment` challenge (Stripe MPP, card
or Link). Pay inline, retry the same request, get the result and a receipt.
Inbox creation is $1.00, a send is $0.01 and a read is $0.005; failed calls are
never charged.

This SDK does not sign payments. Use an x402 client such as the
[`x402`](https://pypi.org/project/x402/) package, or an MPP client such as
[`pympp`](https://pypi.org/project/pympp/), for the paid call. The first paid
inbox from a wallet returns `credentials.api_key` in the response; pass that
key to `DeadSimple(...)` and every method in this README works, with reads and
sends free within the plan. Routes, amounts and headers are on the
[pay-per-request page](https://deadsimple.email/pay-per-request.html).

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
| `client.identity` | `sign_in`, `enroll_key`, `list_keys`, `delete_key`, `connections`, `register_client`, `list_clients`, `delete_client`, `make_assertion` (static) |

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
