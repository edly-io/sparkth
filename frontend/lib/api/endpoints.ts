import { api, type Schema } from "./client";
import { ApiRequestError } from "./errors";

export type LoginRequest = Schema<"UserLogin">;
export type LoginResponse = Schema<"Token">;
export type RegisterRequest = Schema<"UserCreate">;
export type RegisterResponse = Schema<"User">;
export type GoogleAuthUrlResponse = Schema<"GoogleAuthUrl">;
export type WhitelistEntry = Schema<"WhitelistedEmailResponse">;
export type CurrentUser = Schema<"User">;

function bearer(token: string): { Authorization: string } {
  return { Authorization: `Bearer ${token}` };
}

// errorMiddleware turns every non-ok response into an ApiRequestError; anything
// else rejecting here is a transport failure (DNS, refused connection, ...).
function wrapConnectionError(error: unknown): never {
  if (error instanceof ApiRequestError) throw error;
  const message = error instanceof Error ? error.message : "Unknown error";
  throw new ApiRequestError({
    message: `Unable to connect to server: ${message}`,
    fieldErrors: {},
  });
}

export async function login(data: LoginRequest): Promise<LoginResponse> {
  try {
    const { data: token } = await api.POST("/api/v1/auth/login", { body: data });
    return token as LoginResponse;
  } catch (error) {
    wrapConnectionError(error);
  }
}

export async function register(data: RegisterRequest): Promise<RegisterResponse> {
  try {
    const { data: user } = await api.POST("/api/v1/auth/register", { body: data });
    return user as RegisterResponse;
  } catch (error) {
    wrapConnectionError(error);
  }
}

export async function getGoogleLoginUrl(): Promise<GoogleAuthUrlResponse> {
  try {
    const { data } = await api.GET("/api/v1/auth/google/authorize");
    return data as GoogleAuthUrlResponse;
  } catch (error) {
    wrapConnectionError(error);
  }
}

export async function getWhitelist(token: string): Promise<WhitelistEntry[]> {
  try {
    const { data } = await api.GET("/api/v1/whitelist/", { headers: bearer(token) });
    return data as WhitelistEntry[];
  } catch (error) {
    wrapConnectionError(error);
  }
}

export async function addWhitelistEntry(token: string, value: string): Promise<WhitelistEntry> {
  try {
    const { data } = await api.POST("/api/v1/whitelist/", {
      body: { value },
      headers: bearer(token),
    });
    return data as WhitelistEntry;
  } catch (error) {
    wrapConnectionError(error);
  }
}

export async function removeWhitelistEntry(token: string, id: number): Promise<void> {
  try {
    await api.DELETE("/api/v1/whitelist/{entry_id}", {
      params: { path: { entry_id: id } },
      headers: bearer(token),
    });
  } catch (error) {
    wrapConnectionError(error);
  }
}

export async function verifyEmail(token: string): Promise<void> {
  try {
    await api.POST("/api/v1/auth/verify-email", { body: { token } });
  } catch (error) {
    wrapConnectionError(error);
  }
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
    wrapConnectionError(error);
  }
}

export async function getCurrentUser(token: string): Promise<CurrentUser> {
  try {
    const { data } = await api.GET("/api/v1/user/me", { headers: bearer(token) });
    return data as CurrentUser;
  } catch (error) {
    wrapConnectionError(error);
  }
}
