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
