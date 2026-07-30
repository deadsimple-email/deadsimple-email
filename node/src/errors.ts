/** Error types for the Dead Simple Email SDK. */

export class DeadSimpleError extends Error {
  code: string;
  statusCode: number;
  details: { field: string; message: string }[];

  constructor(
    message: string,
    {
      code = "",
      statusCode = 0,
      details = [],
    }: {
      code?: string;
      statusCode?: number;
      details?: { field: string; message: string }[];
    } = {}
  ) {
    super(message);
    this.name = "DeadSimpleError";
    this.code = code;
    this.statusCode = statusCode;
    this.details = details;
  }
}

export class AuthenticationError extends DeadSimpleError {
  constructor(message: string, opts?: { code?: string; details?: { field: string; message: string }[] }) {
    super(message, { ...opts, statusCode: 401 });
    this.name = "AuthenticationError";
  }
}

export class ValidationError extends DeadSimpleError {
  constructor(message: string, opts?: { code?: string; details?: { field: string; message: string }[] }) {
    super(message, { ...opts, statusCode: 400 });
    this.name = "ValidationError";
  }
}

export class NotFoundError extends DeadSimpleError {
  constructor(message: string, opts?: { code?: string }) {
    super(message, { ...opts, statusCode: 404 });
    this.name = "NotFoundError";
  }
}

export class RateLimitError extends DeadSimpleError {
  retryAfter: number;

  constructor(message: string, opts?: { code?: string; retryAfter?: number }) {
    super(message, { ...opts, statusCode: 429 });
    this.name = "RateLimitError";
    this.retryAfter = opts?.retryAfter ?? 60;
  }
}
