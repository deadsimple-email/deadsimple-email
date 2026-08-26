/**
 * Vercel AI SDK integration for Dead Simple Email.
 *
 * @example
 * ```ts
 * import { generateText } from "ai";
 * import { openai } from "@ai-sdk/openai";
 * import { getTools } from "@deadsimple/email/ai";
 *
 * const tools = getTools("dse_your_api_key");
 * const result = await generateText({
 *   model: openai("gpt-4o"),
 *   tools,
 *   prompt: "Create an inbox and send a test email",
 * });
 * ```
 */

import { DeadSimple } from "./client.js";
import type { SendResult, Inbox } from "./types.js";

let _client: DeadSimple | null = null;

function getClient(apiKey?: string): DeadSimple {
  if (!_client) {
    const key = apiKey || process.env.DSE_API_KEY || "";
    if (!key) throw new Error("DSE_API_KEY is required");
    _client = new DeadSimple(key);
  }
  return _client;
}

/**
 * Get Vercel AI SDK-compatible tool definitions.
 *
 * These work with `generateText`, `streamText`, and `generateObject` from the `ai` package.
 */
export function getTools(apiKey?: string): Record<string, unknown> {
  // Lazy-import to avoid requiring 'ai' as a hard dependency
  // eslint-disable-next-line @typescript-eslint/no-var-requires
  let tool: any, z: any;
  try {
    tool = require("ai").tool;
    z = require("zod").z;
  } catch {
    throw new Error("Vercel AI SDK integration requires 'ai' and 'zod' packages: npm install ai zod");
  }

  const client = getClient(apiKey);

  return {
    createInbox: tool({
      description: "Create a new email inbox",
      parameters: z.object({
        displayName: z.string().optional().describe("Friendly name for the inbox"),
      }),
      execute: async ({ displayName }: { displayName?: string }) => {
        return client.inboxes.create({ displayName });
      },
    }),

    listInboxes: tool({
      description: "List all email inboxes",
      parameters: z.object({}),
      execute: async () => {
        const result = await client.inboxes.list();
        return result.inboxes.map((i) => ({
          inbox_id: i.inbox_id,
          email: i.email,
          display_name: i.display_name,
          message_count: i.message_count,
        }));
      },
    }),

    sendEmail: tool({
      description: "Send an email from an inbox",
      parameters: z.object({
        inboxId: z.string().describe("The inbox to send from"),
        to: z.string().describe("Recipient email address"),
        subject: z.string().describe("Email subject"),
        body: z.string().describe("Email body text"),
      }),
      execute: async ({
        inboxId,
        to,
        subject,
        body,
      }: {
        inboxId: string;
        to: string;
        subject: string;
        body: string;
      }) => {
        return client.messages.send({
          inboxId,
          to,
          subject,
          textBody: body,
        });
      },
    }),

    readEmails: tool({
      description: "Read recent emails from an inbox",
      parameters: z.object({
        inboxId: z.string().describe("The inbox to read from"),
        limit: z.number().optional().default(5).describe("Max messages"),
      }),
      execute: async ({ inboxId, limit }: { inboxId: string; limit: number }) => {
        const result = await client.messages.list(inboxId, { limit });
        return result.messages.map((m) => ({
          message_id: m.message_id,
          direction: m.direction,
          from: m.from_email,
          subject: m.subject,
          snippet: m.snippet,
        }));
      },
    }),

    readEmail: tool({
      description: "Read a single email with full body",
      parameters: z.object({
        inboxId: z.string().describe("The inbox containing the message"),
        messageId: z.string().describe("The message ID"),
      }),
      execute: async ({ inboxId, messageId }: { inboxId: string; messageId: string }) => {
        const msg = await client.messages.get(inboxId, messageId);
        return {
          from: msg.from_email,
          to: msg.to,
          subject: msg.subject,
          body: msg.latest_reply || msg.text_body,
        };
      },
    }),

    replyToEmail: tool({
      description: "Reply to an email. Threading is automatic.",
      parameters: z.object({
        inboxId: z.string().describe("The inbox containing the message"),
        messageId: z.string().describe("The message to reply to"),
        body: z.string().describe("Reply body text"),
      }),
      execute: async ({
        inboxId,
        messageId,
        body,
      }: {
        inboxId: string;
        messageId: string;
        body: string;
      }) => {
        return client.messages.reply(inboxId, messageId, { textBody: body });
      },
    }),
  };
}

/**
 * Get OpenAI function calling compatible tool definitions (no Vercel AI SDK required).
 */
export function getFunctionDefinitions() {
  return [
    {
      type: "function" as const,
      function: {
        name: "send_email",
        description: "Send an email from a Dead Simple Email inbox",
        parameters: {
          type: "object",
          properties: {
            inbox_id: { type: "string", description: "The inbox to send from" },
            to: { type: "string", description: "Recipient email address" },
            subject: { type: "string", description: "Email subject" },
            body: { type: "string", description: "Email body text" },
          },
          required: ["inbox_id", "to", "subject", "body"],
        },
      },
    },
    {
      type: "function" as const,
      function: {
        name: "read_emails",
        description: "Read recent emails from an inbox",
        parameters: {
          type: "object",
          properties: {
            inbox_id: { type: "string", description: "The inbox to read from" },
            limit: { type: "integer", description: "Max messages (default 5)" },
          },
          required: ["inbox_id"],
        },
      },
    },
    {
      type: "function" as const,
      function: {
        name: "create_inbox",
        description: "Create a new email inbox",
        parameters: {
          type: "object",
          properties: {
            display_name: { type: "string", description: "Friendly name" },
          },
        },
      },
    },
    {
      type: "function" as const,
      function: {
        name: "list_inboxes",
        description: "List all email inboxes",
        parameters: { type: "object", properties: {} },
      },
    },
  ];
}
