# Installing Dead Simple Email (for coding agents)

There is nothing to clone, build, or run locally. The server is hosted.

## 1. Get an API key

No signup form, no dashboard, no email verification:

```bash
curl -X POST https://api.deadsimple.email/v1/auth/agent-signup
```

The response contains `api_key` (starts with `dse_`) and a ready-to-use inbox.
Store the key — it is shown once. If the caller already has a key, skip this.

Optional: pass a random 24+ character `Idempotency-Key` header so a retry after a
dropped connection returns the same credentials instead of creating a second
account.

## 2. Add the server

Use the remote endpoint. Substitute the key from step 1:

```json
{
  "mcpServers": {
    "dead-simple-email": {
      "type": "http",
      "url": "https://api.deadsimple.email/mcp",
      "headers": { "Authorization": "Bearer dse_your_api_key" }
    }
  }
}
```

That is the whole installation. No `command`, no `args`, no runtime.

## 3. Verify

Call `list_inboxes`. A fresh account returns the one inbox created during signup.

## Local alternative (only if a stdio server is required)

```bash
pip install deadsimple-email
```

```json
{
  "mcpServers": {
    "deadsimple": {
      "command": "python",
      "args": ["-m", "deadsimple.mcp"],
      "env": { "DSE_API_KEY": "dse_your_api_key" }
    }
  }
}
```

## Notes

- Trial accounts allow 1 inbox and 10 sends/hour, 25/day. A `429` with code
  `trial_send_limit_exceeded` is a quota signal, not a transient error — do not
  blindly retry. Lift it with `POST /v1/auth/claim` using an email a human owns.
- `delete_inbox` is the only destructive tool; every read tool is annotated
  `readOnlyHint`.
