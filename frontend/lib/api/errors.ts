/** A structured error detail from the backend: a machine-readable code and, for some codes, the email. */
export interface StructuredErrorDetail {
  code: string;
  email?: string;
}

/** An error response turned into one message plus a message per invalid field. */
export interface FormattedError {
  message: string;
  fieldErrors: Record<string, string>;
}

/**
 * The error every API call rejects with when the backend answers with an error status: its message,
 * any per-field messages, the HTTP status and, for a structured detail, its code.
 */
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
