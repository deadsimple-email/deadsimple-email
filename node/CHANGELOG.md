# Changelog

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
