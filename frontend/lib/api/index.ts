export { api, type Schema } from "./client";
export {
  ApiRequestError,
  formatApiError,
  isStructuredDetail,
  type ApiError,
  type FormattedError,
  type StructuredErrorDetail,
  type ValidationError,
} from "./errors";
export {
  addWhitelistEntry,
  getCurrentUser,
  getGoogleLoginUrl,
  getWhitelist,
  login,
  register,
  removeWhitelistEntry,
  resendVerificationEmail,
  verifyEmail,
  type CurrentUser,
  type GoogleAuthUrlResponse,
  type LoginRequest,
  type LoginResponse,
  type RegisterRequest,
  type RegisterResponse,
  type WhitelistEntry,
} from "./endpoints";
