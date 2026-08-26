# Changelog

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
