# Dead Simple Email

Email API for AI agents. Create inboxes, send/receive email, manage threads and webhooks.

## Setup

1. Install the Python SDK: `pip install deadsimple-email`
2. Set your API key: `export DSE_API_KEY=dse_your_api_key`
3. The MCP server starts automatically when this skill is activated

## Available Tools

### Inbox Management
- **create_inbox** — Create a new email inbox with optional display name and tags
- **list_inboxes** — List all inboxes in the account
- **delete_inbox** — Delete an inbox and all its messages

### Sending Email
- **send_email** — Send an email from an inbox (to, subject, body, cc, bcc). Pass `in_reply_to` to thread it onto an existing conversation
- **reply_to_message** — Reply to a message with automatic threading (cc, bcc, to, reply_all). Works on messages you sent too, where it replies to the original recipients rather than to yourself
- **forward_message** — Forward a message to new recipients

### Reading Email
- **read_messages** — List recent messages in an inbox
- **read_message** — Read a single message with full body content

### Signup and verification
- **wait_for_email** — Block until a matching message arrives (only counts mail arriving after the call)
- **get_verification_code** — Wait for a verification email and return the extracted one-time code
- **get_verification_link** — Wait for a verification email and return the extracted confirmation link

### Threads
- **list_threads** — List conversation threads in an inbox
- **read_thread** — Read all messages in a conversation thread

### Account
- **get_usage** — Get account usage metrics (inboxes, emails, plan limits)

### Identity
- **sign_in_with_inbox**: Sign in to a third-party app with the inbox as the agent's identity (Sign in with Dead Simple, an OpenID Connect provider at https://id.deadsimple.email). Parameters: `inbox_id`, `authorization_url` (the app's `https://id.deadsimple.email/authorize?...` URL, passed exactly as produced), `follow=true` to fetch the redirect so the login completes

## Quick Start

```
Create an inbox, then send a test email:
1. create_inbox with display_name="My Agent"
2. send_email with the inbox_id, to="user@example.com", subject="Hello", body="Sent by an AI agent"
```

## API Key

Get your API key at https://app.deadsimple.email/dashboard/settings

## Links

- Documentation: https://deadsimple.email/docs
- Dashboard: https://app.deadsimple.email
- Python SDK: https://pypi.org/project/deadsimple-email/
- Sign in with Dead Simple: https://deadsimple.email/identity.html
- Pay per request (no API key): https://deadsimple.email/pay-per-request.html
