# Changelog

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
