# Dead Simple Email

<!-- mcp-name: email.deadsimple/dead-simple-email -->

Email infrastructure for AI agents. One call gives an agent a real, deliverable
inbox — no SMTP credentials, no DNS, no dashboard.

**[deadsimple.email](https://deadsimple.email)** · [Docs](https://deadsimple.email/docs.html) · [API reference](https://deadsimple.email/api-reference.html)

## Sign up with no human in the loop

An agent can provision its own account, API key and live inbox in a single
unauthenticated call:

```bash
curl -X POST https://api.deadsimple.email/v1/auth/agent-signup
```

That returns a trial account (1 inbox, 10 sends/hour, 25/day). Claim it later
with a verified email to move to the Free plan, keeping the same key and inboxes.

## MCP server

Listed in the [official MCP Registry](https://registry.modelcontextprotocol.io/v0/servers?search=deadsimple)
as `email.deadsimple/dead-simple-email`, and on
[Glama](https://glama.ai/mcp/connectors/email.deadsimple/dead-simple-email).

**Remote (recommended)** — nothing to install:

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

**Local (stdio):**

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

14 tools: `create_inbox`, `list_inboxes`, `delete_inbox`, `send_email`,
`read_messages`, `read_message`, `reply_to_message`, `forward_message`,
`wait_for_email`, `get_verification_code`, `get_verification_link`,
`list_threads`, `read_thread`, `get_usage`.

The one agents reach for most is **`get_verification_code`** — it pulls the OTP
or magic link out of the newest inbound message, so an agent can sign itself up
for a third-party service or clear a 2FA prompt without ever parsing an email
body.

## SDKs

| Language | Package | Source |
|---|---|---|
| Python | [`deadsimple-email`](https://pypi.org/project/deadsimple-email/) | [`python/`](python) |
| TypeScript | [`@deadsimple/email`](https://www.npmjs.com/package/@deadsimple/email) | [`node/`](node) |

```bash
pip install deadsimple-email
npm install @deadsimple/email
```

```python
from deadsimple import DeadSimple

dse = DeadSimple("dse_your_api_key")
inbox = dse.inboxes.create(display_name="Support Bot")
dse.messages.send(inbox.inbox_id, to=["someone@example.com"],
                  subject="Hello", text_body="Sent by an agent.")
```

Framework integrations for LangChain, CrewAI, LlamaIndex, AutoGen and OpenAI
Agents live in [`python/src/deadsimple/integrations/`](python/src/deadsimple/integrations).

## Repository layout

| Path | What |
|---|---|
| [`python/`](python) | Python SDK + MCP server |
| [`node/`](node) | TypeScript SDK |
| [`skills/`](skills) | Agent skill files for Claude Code, Cursor, Windsurf |
| [`mcp/`](mcp) | `server.json` manifest for the official MCP Registry |

## License

MIT
