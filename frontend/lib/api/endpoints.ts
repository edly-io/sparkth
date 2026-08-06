import { api, bearer, call, type Schema } from "./client";
import { ApiRequestError, rethrowOrWrapConnectionError } from "./errors";

export type LoginRequest = Schema<"UserLogin">;
export type LoginResponse = Schema<"Token">;
export type RegisterRequest = Schema<"UserCreate">;
export type RegisterResponse = Schema<"User">;
export type GoogleAuthUrlResponse = Schema<"GoogleAuthUrl">;
export type WhitelistEntry = Schema<"WhitelistedEmailResponse">;
export type CurrentUser = Schema<"User">;

export async function login(data: LoginRequest): Promise<LoginResponse> {
  return call<LoginResponse>(() => api.POST("/api/v1/auth/login", { body: data }));
}

export async function register(data: RegisterRequest): Promise<RegisterResponse> {
  return call<RegisterResponse>(() => api.POST("/api/v1/auth/register", { body: data }));
}

export async function getGoogleLoginUrl(): Promise<GoogleAuthUrlResponse> {
  return call<GoogleAuthUrlResponse>(() => api.GET("/api/v1/auth/google/authorize"));
}

export async function getWhitelist(token: string): Promise<WhitelistEntry[]> {
  return call<WhitelistEntry[]>(() => api.GET("/api/v1/whitelist/", { headers: bearer(token) }));
}

export async function addWhitelistEntry(token: string, value: string): Promise<WhitelistEntry> {
  return call<WhitelistEntry>(() =>
    api.POST("/api/v1/whitelist/", { body: { value }, headers: bearer(token) }),
  );
}

export async function removeWhitelistEntry(token: string, id: number): Promise<void> {
  return call<void>(() =>
    api.DELETE("/api/v1/whitelist/{entry_id}", {
      params: { path: { entry_id: id } },
      headers: bearer(token),
    }),
  );
}

export async function verifyEmail(token: string): Promise<void> {
  return call<void>(() => api.POST("/api/v1/auth/verify-email", { body: { token } }));
}

export async function resendVerificationEmail(email: string): Promise<void> {
  try {
    await api.POST("/api/v1/auth/verify-email/resend", { body: { email } });
  } catch (error) {
    if (error instanceof ApiRequestError) {
      // Preserve the pre-conversion contract: a bare sentinel for the cooldown
      // case, a fixed message otherwise, never the response body.
      if (error.status === 429) {
        throw new ApiRequestError({ message: "rate_limited", fieldErrors: {} }, 429);
      }
      throw new ApiRequestError(
        { message: "Could not resend confirmation email. Please try again.", fieldErrors: {} },
        error.status,
      );
    }
    rethrowOrWrapConnectionError(error);
  }
}

export async function getCurrentUser(token: string): Promise<CurrentUser> {
  return call<CurrentUser>(() => api.GET("/api/v1/user/me", { headers: bearer(token) }));
}
