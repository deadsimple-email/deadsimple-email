# Dead Simple Email — TypeScript/Node.js SDK

The official TypeScript SDK for [Dead Simple Email](https://deadsimple.email), the email API for AI agents.

- **Fully typed**: TypeScript-first with complete type definitions
- **Zero dependencies**: uses native `fetch` (Node 18+)
- **Idempotency**: pass `idempotencyKey` to any create/send method for safe retries
- **Webhook verification**: HMAC-SHA256 signature validation built in
- **Sign in with Dead Simple**: the inbox is the agent's OpenID Connect login, see [Identity](#identity-sign-in-with-an-inbox)
- **Full API coverage**: inboxes, messages, threads, webhooks, domains, API keys, workspaces, usage, attachments, identity
- **No API key?** Priced routes answer `402` and take USDC or a card inline, see [Pay per request](#no-api-key-pay-per-request)

## Install

```bash
npm install @deadsimple/email
```

## Quick Start

```typescript
import { DeadSimple } from "@deadsimple/email";

const client = new DeadSimple("dse_your_api_key");

// Create an inbox
const inbox = await client.inboxes.create({ displayName: "Support Bot" });
console.log(`Inbox: ${inbox.email}`);

// Send an email
const result = await client.messages.send({
  inboxId: inbox.inbox_id,
  to: "user@example.com",
  subject: "Hello from my AI agent",
  textBody: "This email was sent by an AI agent using Dead Simple Email.",
});
console.log(`Sent: ${result.message_id}`);

// Read received messages
const messages = await client.messages.list(inbox.inbox_id);
for (const msg of messages.messages) {
  console.log(`  ${msg.from_email}: ${msg.subject}`);
}

// Reply to a message
await client.messages.reply(inbox.inbox_id, messages.messages[0].message_id, {
  textBody: "Thanks for your email!",
});

// List conversation threads
const threads = await client.threads.list(inbox.inbox_id);
for (const t of threads.threads) {
  console.log(`  Thread: ${t.subject} (${t.message_count} messages)`);
}
```

## Bulk Operations

```typescript
const result = await client.inboxes.bulkCreate(
  Array.from({ length: 50 }, (_, i) => ({
    displayName: `Agent ${i}`,
    tags: ["batch-1"],
  }))
);
console.log(`Created ${result.created}, failed ${result.failed}`);
```

## Custom Domains

```typescript
const domain = await client.domains.add("mail.yourcompany.com");
for (const record of domain.dns_records) {
  console.log(`  ${record.type} ${record.name} -> ${record.value}`);
}

const status = await client.domains.verify(domain.domain_id);
console.log(`Status: ${status.status}`);
```

## Multi-Tenant Workspaces

```typescript
const workspace = await client.workspaces.create({
  name: "customer-acme",
  description: "Acme Corp",
});
console.log(`Workspace API key: ${workspace.api_key!.key}`);

// Use the workspace's scoped API key
const acmeClient = new DeadSimple(workspace.api_key!.key);
const acmeInbox = await acmeClient.inboxes.create({
  displayName: "Acme Support",
});
```

## Idempotent Requests

```typescript
const key = crypto.randomUUID();
const inbox = await client.inboxes.create({
  displayName: "Bot",
  idempotencyKey: key,
});
// Safe to retry — same key = same result
const same = await client.inboxes.create({
  displayName: "Bot",
  idempotencyKey: key,
});
```

## Webhook Signature Verification

Every delivery is signed with HMAC-SHA256 over `"<timestamp>.<raw_body>"`. Pass the
raw body and the request headers; `verifyRequest` reads whichever signature header
the delivery carried, checks freshness, and compares in constant time.

```typescript
import { verifyRequest } from "@deadsimple/email/webhooks";

// Keep the raw bytes: a parsed-and-restringified body will not verify.
app.use(express.json({ verify: (req, _res, buf) => { (req as any).rawBody = buf; } }));

app.post("/webhook", (req, res) => {
  try {
    verifyRequest({
      payload: (req as any).rawBody,
      headers: req.headers,
      secret: "whsec_your_signing_secret",
    });
  } catch {
    return res.status(401).send("Invalid signature");
  }
  res.sendStatus(200);   // return fast, then do the work
});
```

`verifyRequest` also accepts a fetch `Headers` object, for Hono, Next.js route
handlers, and workers. `verifySignature` is the lower-level form when you already
have the header value; pass `timestamp` alongside a `sha256=` signature, which
carries none of its own.

Deliveries are retried on non-2xx or timeout, so handlers must be idempotent. Key
on `message_id`, not on receipt.

## Custom delivery headers

If your endpoint enforces its own auth, register the headers it requires. They are
sent on every delivery attempt and every retry.

```typescript
const wh = await client.webhooks.create({
  url: "https://your-app.com/webhook",
  events: ["message.received"],
  headers: { Authorization: "Bearer your-endpoint-token" },
});

// Rotate later without recreating the webhook, which would change its secret.
await client.webhooks.setHeaders(wh.webhook_id, { Authorization: "Bearer rotated" });

await client.webhooks.getHeaders(wh.webhook_id); // names only, values masked
await client.webhooks.setHeaders(wh.webhook_id, {}); // clear them
```

Values are write-only: every response returns them masked. Up to 10 headers, 1024
characters per value, printable ASCII. `Content-Type`, `Host`, `User-Agent`,
hop-by-hop headers and `X-DSE-*` are reserved.

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
(`https://id.deadsimple.email/authorize?...`). Hand that URL to `signIn` and the
SDK authenticates as the inbox with the API key it already holds. With `follow`
(the default) the redirect back to the app is fetched as well, so the app has
exchanged the code by the time the promise resolves.

```typescript
const inbox = await client.inboxes.create({ displayName: "Research Bot" });

// 1. Start the app's login (submit its form / call its API) and capture the
//    https://id.deadsimple.email/authorize?... URL it sends you to.
const authorizationUrl =
  "https://id.deadsimple.email/authorize?response_type=code" +
  "&client_id=https%3A%2F%2Fapp.example.com" +
  "&redirect_uri=https%3A%2F%2Fapp.example.com%2Fapi%2Fauth%2Fcallback%2Fdeadsimple" +
  "&scope=openid%20email%20profile&state=xyz" +
  "&code_challenge=E9Melhoa2OwvFrEMTJguCHaoeK1t8URWbuGJSstw-cM&code_challenge_method=S256";

// 2. Sign in as the inbox. The app receives inbox.email as the account email.
const result = await client.identity.signIn(inbox.inbox_id, authorizationUrl);
console.log(result.client_name);   // "app.example.com"
console.log(result.final_url);     // where the app landed after exchanging the code
console.log(result.final_status);  // 200

// Drive fetch yourself instead (your own cookie jar or session):
const pending = await client.identity.signIn(inbox.inbox_id, authorizationUrl, {
  follow: false,
});
await fetch(pending.redirect_to, { redirect: "follow" }); // app callback with code + state

// Apps this inbox has signed in to
const { connections } = await client.identity.connections(inbox.inbox_id);
for (const c of connections) {
  console.log(`  ${c.client_name}: ${c.sign_in_count} sign-ins`);
}
```

### Signing in with a key the agent holds, not an API key

For a worker that should not hold mailbox access, enroll a P-256 public key on
the inbox once and keep the private key on the worker. At sign-in time the
worker signs a short-lived ES256 assertion over
`{ iss, sub: inboxId, aud: "https://id.deadsimple.email", iat, exp, jti }` with
a `kid` header (for example with `jose`) and posts it to `/authorize` as the
`assertion` field with `Accept: application/json`. Deleting the key revokes
sign-in without touching any API key, and `listKeys` shows `last_used_at` per
key so an idle one is easy to spot.

```typescript
// Once, from a process that holds the API key: enroll the worker's public key.
// openssl ecparam -name prime256v1 -genkey -noout -out worker.pem
// openssl ec -in worker.pem -pubout -out worker.pub.pem
const key = await client.identity.enrollKey(inbox.inbox_id, {
  publicKey: await fs.readFile("worker.pub.pem", "utf8"), // PEM or JWK
  name: "worker-7",
});
console.log(key.kid);

await client.identity.listKeys(inbox.inbox_id);         // { keys, total }
await client.identity.deleteKey(inbox.inbox_id, key.kid); // revoke
```

The assertion itself is plain JOSE, so the worker needs no SDK at all; the
[identity page](https://deadsimple.email/identity.html) shows the exact claims
and the `/authorize` request.

### Relying party: accept agents in your own app

If you are the app, point your auth library at
`https://id.deadsimple.email/.well-known/openid-configuration`. An open client
needs no registration at all: `client_id` is your https origin and PKCE carries
the security. Register a client when you want a `client_secret`, refresh
tokens, or the `owner_email` and `org` scopes that tell one operator running
many agents from many users.

```typescript
const rp = await client.identity.registerClient({
  clientName: "Acme SaaS",
  redirectUris: ["https://acme.example/auth/callback"],
  clientUri: "https://acme.example",
});
console.log(rp.client_id);      // dse_idc_...
console.log(rp.client_secret);  // dse_ics_..., shown once
console.log(rp.discovery_url);  // paste into Auth.js, Better Auth, Clerk, Auth0, ...

await client.identity.listClients();
await client.identity.deleteClient(rp.client_id);
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

This SDK does not sign payments. Use an x402 client such as
[`@x402/fetch`](https://www.npmjs.com/package/@x402/fetch), or an MPP client
such as [`mppx`](https://www.npmjs.com/package/mppx), for the paid call. The
first paid inbox from a wallet returns `credentials.api_key` in the response;
pass that key to `new DeadSimple(...)` and every method in this README works,
with reads and sends free within the plan. Routes, amounts and headers are on
the [pay-per-request page](https://deadsimple.email/pay-per-request.html).

## Error Handling

```typescript
import {
  DeadSimple,
  NotFoundError,
  RateLimitError,
  ValidationError,
} from "@deadsimple/email";

const client = new DeadSimple("dse_your_api_key");

try {
  await client.inboxes.get("nonexistent");
} catch (e) {
  if (e instanceof NotFoundError) {
    console.log("Inbox not found");
  } else if (e instanceof RateLimitError) {
    console.log(`Rate limited, retry in ${e.retryAfter}s`);
    await new Promise((r) => setTimeout(r, e.retryAfter * 1000));
  } else if (e instanceof ValidationError) {
    console.log(`Bad request: ${e.message}`);
    for (const d of e.details) {
      console.log(`  ${d.field}: ${d.message}`);
    }
  }
}
```

## All Resources

| Resource | Methods |
|----------|---------|
| `client.inboxes` | `create`, `bulkCreate`, `list`, `get`, `update`, `delete` |
| `client.messages` | `send`, `list`, `get`, `reply`, `replyAll`, `forward` |
| `client.threads` | `list`, `get` |
| `client.webhooks` | `create`, `list`, `delete` |
| `client.domains` | `add`, `list`, `verify`, `delete` |
| `client.apiKeys` | `create`, `list`, `delete` |
| `client.workspaces` | `create`, `list`, `get`, `update`, `delete` |
| `client.usage` | `get` |
| `client.attachments` | `getUrl` |
| `client.identity` | `signIn`, `enrollKey`, `listKeys`, `deleteKey`, `connections`, `registerClient`, `listClients`, `deleteClient` |

## License

MIT
