import { createTranslator } from "next-intl";

import { getActiveLocale, getActiveMessages } from "@/core/i18n/activeLocale";
import { ApiRequestError, type FormattedError, type StructuredErrorDetail } from "@/lib/api/errors";

/** One field error in a 422 response: where it is (`loc`), its message and its kind. */
export interface ValidationError {
  loc: (string | number)[];
  msg: string;
  type: string;
}

/** A backend error response: a message, a list of field errors, or a structured detail with a code. */
export interface ApiError {
  detail: string | ValidationError[] | StructuredErrorDetail;
}

/** Whether an error's `detail` is a structured detail (an object with a string `code`). */
export function isStructuredDetail(value: unknown): value is StructuredErrorDetail {
  return (
    typeof value === "object" &&
    value !== null &&
    !Array.isArray(value) &&
    typeof (value as { code?: unknown }).code === "string"
  );
}

/**
 * Turns an error response into one message plus a message per invalid field. Field errors map
 * to their field, and the rest join into the message; a structured detail's message is its code.
 */
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

/**
 * Rethrows an API call's failure in the shape callers expect: an `ApiRequestError` (an error
 * response) and an abort pass through unchanged, and anything else is a failed connection, thrown
 * as an `ApiRequestError` with a translated "couldn't connect" message.
 */
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
