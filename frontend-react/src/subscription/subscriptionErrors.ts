import { ApiClientError } from "../api/client";

export type SubscriptionErrorKind =
  | "authentication"
  | "access"
  | "allowance"
  | "payment"
  | "selection"
  | "configuration"
  | "provider"
  | "network"
  | "unknown";

export interface SubscriptionErrorOptions {
  code: string;
  message: string;
  status: number | null;
  kind: SubscriptionErrorKind;
  retryable: boolean;
  details?: Record<string, unknown>;
}

export class SubscriptionError extends Error {
  readonly code: string;
  readonly status: number | null;
  readonly kind: SubscriptionErrorKind;
  readonly retryable: boolean;
  readonly details: Record<string, unknown>;

  constructor(options: SubscriptionErrorOptions) {
    super(options.message);
    this.name = "SubscriptionError";
    this.code = options.code;
    this.status = options.status;
    this.kind = options.kind;
    this.retryable = options.retryable;
    this.details = options.details ?? {};
  }
}

export function toSubscriptionError(
  error: unknown,
  fallbackMessage = "Subscription information could not be loaded.",
): SubscriptionError {
  if (error instanceof SubscriptionError) return error;

  if (error instanceof ApiClientError) {
    const detail = structuredDetail(error.body);
    const code = detail.code ?? fallbackCode(error.status);
    return new SubscriptionError({
      code,
      message: detail.message ?? error.message ?? fallbackMessage,
      status: error.status,
      kind: errorKind(code, error.status),
      retryable: isRetryable(code, error.status),
      details: detail.fields,
    });
  }

  if (error instanceof TypeError) {
    return new SubscriptionError({
      code: "billing_network_error",
      message: "The billing service could not be reached. Please try again.",
      status: null,
      kind: "network",
      retryable: true,
    });
  }

  return new SubscriptionError({
    code: "subscription_request_failed",
    message: error instanceof Error && error.message ? error.message : fallbackMessage,
    status: null,
    kind: "unknown",
    retryable: false,
  });
}

export function isAbortError(error: unknown): boolean {
  return (
    (error instanceof DOMException && error.name === "AbortError") ||
    (error instanceof Error && error.name === "AbortError")
  );
}

interface StructuredDetail {
  code?: string;
  message?: string;
  fields: Record<string, unknown>;
}

function structuredDetail(body: unknown): StructuredDetail {
  if (!isRecord(body)) return { fields: {} };
  const candidate = isRecord(body.detail) ? body.detail : body;
  const fields = { ...candidate };
  const code = typeof candidate.code === "string" ? candidate.code : undefined;
  const message = typeof candidate.message === "string" ? candidate.message : undefined;
  delete fields.code;
  delete fields.message;
  return { code, message, fields };
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function fallbackCode(status: number): string {
  if (status === 401 || status === 403) return "billing_authentication_required";
  if (status === 429) return "monthly_allowance_exhausted";
  if (status >= 500) return "billing_service_unavailable";
  return "subscription_request_failed";
}

function errorKind(code: string, status: number): SubscriptionErrorKind {
  if (
    code === "billing_identity_not_found" ||
    code === "billing_authentication_required" ||
    code === "session_auth_required"
  ) {
    return "authentication";
  }
  if (code === "monthly_allowance_exhausted") return "allowance";
  if (code === "subscription_payment_required") return "payment";
  if (code === "feature_not_in_plan" || code === "model_not_in_plan" || status === 403) {
    return "access";
  }
  if (
    code === "invalid_subscription_plan" ||
    code === "paid_subscription_plan_required" ||
    status === 422
  ) {
    return "selection";
  }
  if (code === "billing_provider_unavailable") return "provider";
  if (
    code === "billing_not_configured" ||
    code === "billing_database_required" ||
    code === "subscription_configuration_error" ||
    code === "invalid_billing_redirect"
  ) {
    return "configuration";
  }
  if (status >= 500) return "provider";
  return "unknown";
}

function isRetryable(code: string, status: number): boolean {
  if (
    code === "billing_not_configured" ||
    code === "billing_database_required" ||
    code === "subscription_configuration_error"
  ) {
    return false;
  }
  return code === "billing_provider_unavailable" || status === 429 || status >= 500;
}
