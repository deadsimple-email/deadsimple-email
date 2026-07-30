# MCP Registry manifest

`server.json` is the manifest published to the
[official MCP Registry](https://modelcontextprotocol.io/registry/about) as
`email.deadsimple/dead-simple-email`.

It advertises two ways to run the server:

- **PyPI package** `deadsimple-email` over stdio
- **Remote** Streamable HTTP endpoint at `https://api.deadsimple.email/mcp`

Auth differs by transport, deliberately:

| Transport | Key source | Why |
|---|---|---|
| stdio | `DSE_API_KEY` env var | one process per caller |
| streamable-http | `Authorization: Bearer` **per request** | one process serves many callers, so an environment fallback would risk serving one caller with another's credentials |

Run the remote transport yourself with:

```bash
DSE_MCP_ALLOWED_HOSTS=your.host python -m deadsimple.mcp \
    --transport streamable-http --port 8000
```

`DSE_MCP_ALLOWED_HOSTS` is required when hosting under a real domain — MCP's
DNS-rebinding protection rejects any `Host` not on its allowlist, which defaults
to localhost only.
