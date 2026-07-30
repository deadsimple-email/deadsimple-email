# Changelog

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
