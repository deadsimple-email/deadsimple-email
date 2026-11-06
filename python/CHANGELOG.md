# Changelog

## 0.11.0

### Added
- MCP Events on the MCP server (`deadsimple.mcp`): `events/list`,
  `events/subscribe` and `events/unsubscribe` for `message.received` (filters
  `inbox_id`, `from_contains`, `subject_contains`) and `message.bounced`
  (`inbox_id`), so ChatGPT and OpenAI dots can be woken by new mail instead of
  polling. Advertised as the `events` capability. HTTP mode with mcp 2.x only.

### Changed
- The MCP server runs on mcp 2.x (protocol 2026-07-28, stateless, alongside
  the 1.x handshake) as well as 1.x. The `mcp` extra now allows `mcp>=1.26,<3`.
- `http_app()` takes `json_response=`; it is no longer read from
  `mcp.settings`, which mcp 2.x removed.
- On mcp 2.x, tool errors keep their message (a missing key, an API refusal)
  instead of the SDK's generic "Error executing tool".

## 0.10.0

### Added
- `client.calendar`: per-inbox calendar events (create, list, list_all, get,
  update, delete), `invite` to send the event as an ICS invitation, `rsvp` to
  answer one, and `feed` / `rotate_feed` for a subscribable ICS feed. Inbound
  invitations, updates, cancellations and replies are ingested automatically
  and surface as `calendar_event` on messages. MCP tools
  `list_calendar_events` and `create_calendar_event`.
- `client.metrics.get(from_=, to=, interval=, inbox_ids=)`: daily or hourly
  time series of sent, received, bounced, complained, opened, clicked,
  webhook deliveries and failures, and injection-flagged messages.
- Inbox-scoped API keys: `client.api_keys.create(name, inbox_ids=[...])` and
  `client.api_keys.get(key_id)`.
- Inbox-scoped webhooks: `client.webhooks.create(url, events, inbox_ids=[...])`,
  `client.webhooks.get(webhook_id)` and `client.webhooks.update(webhook_id, ...)`.
- `Message.injection_risk` and `Message.injection_score` from the inbound
  prompt-injection scanner; the MCP `read_message` and `read_messages` tools
  include them when the risk is medium or high.

## 0.9.1

### Changed
- `make_assertion` is exported from the package root, so a worker holding
  only the agent's private key can build a sign-in assertion without a client.
- README documents identity and pay-per-request.

## 0.9.0

### Added
- `client.identity`: Sign in with Dead Simple, the OpenID Connect provider at
  `https://id.deadsimple.email` where an agent's inbox is its login.
  `identity.sign_in(inbox_id, authorization_url)` completes an app's OIDC
  login with one call; `enroll_key`, `list_keys`, `delete_key` manage P-256
  keys for the signed-assertion path; `connections` lists the apps an inbox
  has signed in to; `register_client`, `list_clients`, `delete_client` manage
  your own relying-party registrations; `Identity.make_assertion` builds the
  ES256 assertion. Same surface on `AsyncDeadSimple`.
- MCP tool `sign_in_with_inbox(inbox_id, authorization_url)`.

## 0.7.0

### Added
- `reply()` and `reply_all()` take `send_at`, so an agent can schedule its own
  follow-up at the moment it answers instead of relying on an external cron.
  The MCP tools `reply_to_message` and `send_email` take it too.
- `messages.list()` takes `labels`, and the MCP `read_messages` tool takes
  `labels` and `direction`. A sweep for unanswered mail is now one call:

  ```python
  client.messages.list(inbox_id, labels=["state:unreplied"])
  ```

  `read_messages` also returns each message's labels.

## 0.6.0

### Added
- `reply()` and `reply_all()` take `cc`, `bcc` and `to`. A standing CC on every
  outbound no longer forces you off replies and onto a hand-built `Re:` subject:

  ```python
  client.messages.reply(
      inbox_id, message_id,
      text_body="Following up.",
      cc=["records@client.example"],
  )
  ```

  On `reply_all()`, `cc` adds to the original participants rather than
  replacing them.
- `send()` takes `in_reply_to` (and `references`), for a reply that also needs
  its own recipient list. It accepts either a `message_id` from the inbox or a
  raw Message-ID header, so an agent can pass the id it already holds.
- The MCP tool `reply_to_message` takes `cc`, `bcc`, `to` and `reply_all`;
  `send_email` takes `in_reply_to`.

### Fixed
- Replying to a message *you* sent now goes to the people it was addressed to.
  It previously replied to the From, which on your own mail is your own inbox,
  so the standard "sent this days ago, no answer, nudge them" follow-up mailed
  itself. `reply_all()` keeps the original Cc line in the same case.
- Threading matched only one of the two columns our Message-IDs live in, so a
  reply arriving from a normal mail client to something we sent started a new
  thread instead of continuing the conversation, and our own replies to mail we
  received did the same. Both directions match now, In-Reply-To first and then
  the References chain, with a normalized-subject plus shared-participant
  fallback for mail that carries no threading headers at all. `list_threads`
  and `GET /v1/threads` group on the result, so they stop returning one thread
  per message.

## 0.5.0

### Added
- Image and file sending. `messages.send()`, `reply()`, `reply_all()` and
  `forward()` take `images=` (rendered in the body) and `attachments=`
  (delivered as downloads). Each entry is a local path, an https URL, raw
  bytes, or a reference from `attachments.upload()`:

  ```python
  client.messages.send(
      inbox_id=inbox.inbox_id,
      to="contractor@example.com",
      subject="Site photos",
      text_body="Photos below.",
      images=["/abs/path/door.jpg", "https://example.com/ceiling.jpg"],
  )
  ```

- `attachments.upload()` stages a file and returns a reference reusable across
  messages. Files upload out of band, so full-size photos work: a send request
  itself cannot carry more than a few megabytes.
- The MCP tools `send_email`, `reply_to_message` and `forward_message` take
  `images` and `attachments` as lists of paths or URLs.

### Fixed
- Google Drive share links (`/file/d/<id>/view`) are rewritten to their direct
  download form. Fetched verbatim they return an HTML viewer page, which would
  otherwise be attached as though it were the photo. A link that still returns
  HTML now raises a clear error naming link-sharing as the cause.

## 0.4.0

### Added
- Custom headers on webhook delivery. `webhooks.create(..., headers={...})`
  registers headers that the API sends on every delivery attempt and every
  retry, for endpoints that enforce their own auth:

  ```python
  client.webhooks.create(
      url="https://your-app.com/webhook",
      events=["message.received"],
      headers={"Authorization": "Bearer your-endpoint-token"},
  )
  ```

- `webhooks.get_headers(webhook_id)` and `webhooks.set_headers(webhook_id, headers)`
  read and replace the headers on an existing webhook, so rotating a token no
  longer means recreating the webhook and losing its signing secret. Pass `{}`
  to clear them.
- `Webhook.headers` carries the header names back. Values are write-only: the
  API masks them in every response.

## 0.3.0

### Fixed
- Webhook signature verification never matched a real delivery. The API sent
  `X-DSE-Webhook-Signature: sha256=<digest>` with the timestamp in its own
  header; `verify_signature` parsed `X-DSE-Signature: t=<unix>,v1=<hex>`. Same
  HMAC over the same content, different encoding. Deliveries now carry both
  forms and `verify_signature` accepts either.

### Added
- `verify_request(payload, headers, secret)` — reads whichever signature header
  the delivery carried, so a handler does not need to know which form it got.

## 0.2.2

### Fixed
- Pin `mcp>=1.26,<2` for the `[mcp]` extra. `mcp` 2.0.0 removed
  `mcp.server.fastmcp` (renamed to `mcpserver`), so the previous `mcp>=1.0`
  floor resolved to 2.0 and broke `import deadsimple.mcp` for anyone installing
  fresh.

### Added
- Every MCP tool now carries a `title` and the applicable `readOnlyHint` /
  `destructiveHint` / `idempotentHint` / `openWorldHint`. `delete_inbox` is the
  only tool marked destructive. Required by the Claude Connectors Directory and
  used by directory quality scores.
- `DSE_MCP_ALLOWED_HOSTS` for hosting the remote transport under a real domain.

## 0.2.1

### Added
- Remote MCP transport: `python -m deadsimple.mcp --transport streamable-http`
  serves many callers from one process. Each caller supplies its own key per
  request via `Authorization: Bearer dse_...`; `DSE_API_KEY` is ignored in HTTP
  mode so one caller can never be served with another's credentials.
- `server.json` for the official MCP Registry (`email.deadsimple/dead-simple-email`).

### Changed
- stdio mode is unchanged and remains the default.

## 0.2.0

### Added
- `messages.wait_for()` (sync + async) — block until a new inbound message
  matching sender/subject arrives, for signup/OTP flows.
- MCP tools: `wait_for_email`, `get_verification_code`, `get_verification_link`.
- `MessageFull.extracted` — auto-extracted verification code / magic link.
- `Attachment.extracted_text` — readable text for PDF/XLSX/DOCX/CSV/… attachments.
- `inboxes.bulk_delete()` (sync + async).
- Async client parity: `drafts`, `filters`, `templates` resources; message list
  filters (`direction`/`q`/`from_email`).
- Framework integrations (LangChain, CrewAI, LlamaIndex, AutoGen, OpenAI Agents)
  gained `wait_for_email` and `get_verification_code` tools.

## 0.1.1
- Initial public release.
