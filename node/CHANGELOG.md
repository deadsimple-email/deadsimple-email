# Changelog

## 1.5.1

### Changed
- README documents identity and pay-per-request.

## 1.5.0

### Added
- `client.identity`: Sign in with Dead Simple, the OpenID Connect provider at
  `https://id.deadsimple.email` where an agent's inbox is its login.
  `identity.signIn(inboxId, authorizationUrl)` completes an app's OIDC login
  with one call; `enrollKey`, `listKeys`, `deleteKey` manage P-256 keys for
  the signed-assertion path; `connections` lists the apps an inbox has signed
  in to; `registerClient`, `listClients`, `deleteClient` manage your own
  relying-party registrations. Types `IdentitySignInResult`, `IdentityKey`,
  `IdentityConnection`, `IdentityClient` are exported.

## 1.3.0

### Added
- `reply()` and `replyAll()` take `sendAt` to schedule a reply.
- `messages.list()` takes `labels`, narrowing to messages carrying every label
  given.

## 1.2.0

### Added
- `reply()` and `replyAll()` take `cc`, `bcc` and `to`, so a standing CC can
  ride every reply:

  ```ts
  await client.messages.reply(inboxId, messageId, {
    textBody: "Following up.",
    cc: ["records@client.example"],
  });
  ```

  On `replyAll()`, `cc` adds to the original participants rather than
  replacing them.
- `send()` takes `inReplyTo` (and `references`), accepting either a `messageId`
  from the inbox or a raw Message-ID header.

### Fixed
- Replying to a message you sent now goes to the people it was addressed to,
  rather than to its From, which is your own inbox.
- Threading matches both the Message-ID column we write on outbound mail and
  the one we write on inbound, then the References chain, so replies join the
  conversation they belong to instead of each opening a new thread.

## 1.1.0

### Added
- Image and file sending. `messages.send()`, `reply()`, `replyAll()` and
  `forward()` take `images` (rendered in the body) and `attachments`
  (delivered as downloads). Each entry is a local path, an https URL, a
  `Uint8Array`, or a reference from `attachments.upload()`:

  ```ts
  await client.messages.send({
    inboxId: inbox.inbox_id,
    to: "contractor@example.com",
    subject: "Site photos",
    textBody: "Photos below.",
    images: ["/abs/path/door.jpg", "https://example.com/ceiling.jpg"],
  });
  ```

- `attachments.upload()` stages a file and returns a reference reusable across
  messages. Files upload out of band, so full-size photos work: a send request
  itself cannot carry more than a few megabytes.

### Fixed
- Google Drive share links (`/file/d/<id>/view`) are rewritten to their direct
  download form. Fetched verbatim they return an HTML viewer page, which would
  otherwise be attached as though it were the photo. A link that still returns
  HTML now throws an error naming link-sharing as the cause.

## 1.0.1

Documentation only; no API change.

- Document custom webhook delivery headers (`headers` on `webhooks.create`, plus
  `webhooks.getHeaders` / `webhooks.setHeaders`). These shipped in 1.0.0 but were
  only documented in the Python and Go SDKs.
- Rewrite the webhook verification example to use `verifyRequest`, and show how to
  retain the raw body. The previous example passed `req.body`, which is the parsed
  object and never verifies.


## 1.0.0

Republished under the `@deadsimple` organization scope. The package is now
`@deadsimple/email`; the old unscoped `deadsimple-email` name is retired.

```
npm install @deadsimple/email
```

Functionally identical to 0.3.0. Version reset to 1.0.0 because the scoped
package starts its own history.


## 0.3.0

### Fixed
- Webhook signature verification never matched a real delivery. `verifySignature`
  parsed an `X-DSE-Signature: t=<unix>,v1=<hex>` header; the API sent
  `X-DSE-Webhook-Signature: sha256=<hex>` with the timestamp in its own header.
  The HMAC and the signed content were identical, so only the encoding disagreed.
  The API now sends both forms, and `verifySignature` accepts either. Pass
  `timestamp` alongside a `sha256=` signature, which carries none of its own.

### Added
- `verifyRequest({ payload, headers, secret })` — reads whichever signature header
  the delivery carried, so a handler does not have to know which form it got.
  Header lookup is case-insensitive and accepts Node's `string[]` values or a
  fetch `Headers` object.

## 0.2.0

### Added
- New resources: `drafts` (CRUD + send), `filters`, `templates`.
- `inboxes.bulkDelete()`.
- `messages.waitFor()` — block until a new inbound message matching
  sender/subject arrives, for signup/OTP flows.
- `messages.list()` filters: `q`, `direction`, `fromEmail`.
- Types: `Draft`, `DraftList`, `BulkDeleteResult`, `MessageFull.extracted`
  (verification code / magic link), `Attachment.extracted_text`.

## 0.1.1
- Initial public release.
