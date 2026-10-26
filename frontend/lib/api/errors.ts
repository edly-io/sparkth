import { createTranslator } from "next-intl";

import { getActiveLocale, getActiveMessages } from "@/lib/i18n/active-locale";

export interface ValidationError {
  loc: (string | number)[];
  msg: string;
  type: string;
}

export interface StructuredErrorDetail {
  code: string;
  email?: string;
}

export interface ApiError {
  detail: string | ValidationError[] | StructuredErrorDetail;
}

export interface FormattedError {
  message: string;
  fieldErrors: Record<string, string>;
}

export function isStructuredDetail(value: unknown): value is StructuredErrorDetail {
  return (
    typeof value === "object" &&
    value !== null &&
    !Array.isArray(value) &&
    typeof (value as { code?: unknown }).code === "string"
  );
}

export function formatApiError(error: ApiError): FormattedError {
  if (typeof error.detail === "string") {
    return { message: error.detail, fieldErrors: {} };
  }

  if (Array.isArray(error.detail)) {
    const fieldErrors: Record<string, string> = {};
    const messages: string[] = [];

    for (const err of error.detail) {
      const field = err.loc[err.loc.length - 1];
      if (typeof field === "string" && field !== "body") {
        fieldErrors[field] = err.msg;
      } else {
        messages.push(err.msg);
      }
    }

    return {
      message:
        messages.length > 0
          ? messages.join(". ")
          : Object.values(fieldErrors)[0] || "Validation failed",
      fieldErrors,
    };
  }

  if (isStructuredDetail(error.detail)) {
    return { message: error.detail.code, fieldErrors: {} };
  }

  return { message: "An unexpected error occurred", fieldErrors: {} };
}

export class ApiRequestError extends Error {
  fieldErrors: Record<string, string>;
  status?: number;
  code?: string;
  data?: StructuredErrorDetail;

  constructor(formatted: FormattedError, status?: number, detail?: StructuredErrorDetail) {
    super(formatted.message);
    this.name = "ApiRequestError";
    this.fieldErrors = formatted.fieldErrors;
    this.status = status;
    if (detail) {
      this.code = detail.code;
      this.data = detail;
    }
  }
}

// errorMiddleware turns every non-ok response into an ApiRequestError; aborts are
// flow control and pass through unwrapped; anything else rejecting at a call site
// is a transport failure (DNS, refused connection, ...).
export function rethrowOrWrapConnectionError(error: unknown): never {
  if (error instanceof ApiRequestError) throw error;
  if (error instanceof DOMException && error.name === "AbortError") throw error;
  const detail = error instanceof Error ? error.message : "Unknown error";
  const t = createTranslator({
    locale: getActiveLocale(),
    messages: getActiveMessages(),
    namespace: "api",
  });
  // i18n-check only finds keys used through React's translation hooks, so this key is declared
  // with the marker below.
  // i18n-check t("api.connectionFailed")
  throw new ApiRequestError({ message: t("connectionFailed", { detail }), fieldErrors: {} });
}
