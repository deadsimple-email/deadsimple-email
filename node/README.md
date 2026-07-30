# Dead Simple Email — TypeScript/Node.js SDK

The official TypeScript SDK for [Dead Simple Email](https://deadsimple.email), the email API for AI agents.

- **Fully typed** — TypeScript-first with complete type definitions
- **Zero dependencies** — uses native `fetch` (Node 18+)
- **Idempotency** — pass `idempotencyKey` to any create/send method for safe retries
- **Webhook verification** — HMAC-SHA256 signature validation built in
- **Full API coverage** — inboxes, messages, threads, webhooks, domains, API keys, workspaces, usage, attachments

## Install

```bash
npm install deadsimple-email
```

## Quick Start

```typescript
import { DeadSimple } from "deadsimple-email";

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

```typescript
import { verifySignature } from "deadsimple-email/webhooks";

// In your webhook handler (Express, Hono, etc.):
app.post("/webhook", (req, res) => {
  try {
    verifySignature({
      payload: req.body,
      signature: req.headers["x-dse-signature"],
      secret: "whsec_your_signing_secret",
    });
    // Valid — process the event
  } catch {
    res.status(401).send("Invalid signature");
  }
});
```

## Error Handling

```typescript
import {
  DeadSimple,
  NotFoundError,
  RateLimitError,
  ValidationError,
} from "deadsimple-email";

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

## License

MIT
