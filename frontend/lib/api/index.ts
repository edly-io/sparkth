export { api, bearer, call, type Schema } from "./client";
export {
  ApiRequestError,
  formatApiError,
  isStructuredDetail,
  rethrowOrWrapConnectionError,
  type ApiError,
  type FormattedError,
  type StructuredErrorDetail,
  type ValidationError,
} from "./errors";
