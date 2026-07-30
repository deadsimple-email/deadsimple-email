export { DeadSimple } from "./client.js";
export type { DeadSimpleOptions } from "./client.js";

export {
  DeadSimpleError,
  AuthenticationError,
  ValidationError,
  NotFoundError,
  RateLimitError,
} from "./errors.js";

export type {
  Inbox,
  InboxList,
  BulkCreateResult,
  BulkDeleteResult,
  Attachment,
  Draft,
  DraftList,
  Message,
  MessageFull,
  MessageList,
  SendResult,
  Thread,
  ThreadList,
  ThreadDetail,
  Webhook,
  WebhookList,
  Domain,
  DomainList,
  DomainVerification,
  ApiKey,
  ApiKeyList,
  Usage,
  Workspace,
  WorkspaceList,
  Pod,
  PodList,
  AttachmentUrl,
} from "./types.js";
