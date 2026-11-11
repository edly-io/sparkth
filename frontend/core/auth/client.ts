import {
  api,
  ApiRequestError,
  bearer,
  call,
  rethrowOrWrapConnectionError,
  type Schema,
} from "@/lib/api";

/** A username and its password. */
export type LoginRequest = Schema<"UserLogin">;
/** The access token a successful login returns, with its expiry. */
export type LoginResponse = Schema<"Token">;
/** The details a new account is registered with. */
export type RegisterRequest = Schema<"UserCreate">;
/** The account a registration creates. */
export type RegisterResponse = Schema<"User">;
/** Where to send the browser to sign in with Google. */
export type GoogleAuthUrlResponse = Schema<"GoogleAuthUrl">;
/** The signed-in user. */
export type CurrentUser = Schema<"User">;
/** The profile fields a user can change; any left out keep their value. */
export type UserUpdate = Schema<"UserUpdate">;
/** A user's current password and the new one replacing it. */
export type PasswordChange = Schema<"PasswordChange">;
/** A reset link's token and the new password it sets. */
export type PasswordResetConfirm = Schema<"PasswordResetConfirm">;

/** Signs in with a username and password, returning the access token. */
export async function login(data: LoginRequest): Promise<LoginResponse> {
  return call<LoginResponse>(() => api.POST("/api/v1/auth/login", { body: data }));
}

/** Creates an account; the user verifies the email before signing in. */
export async function register(data: RegisterRequest): Promise<RegisterResponse> {
  return call<RegisterResponse>(() => api.POST("/api/v1/auth/register", { body: data }));
}

/** The Google sign-in address to send the browser to. */
export async function getGoogleLoginUrl(): Promise<GoogleAuthUrlResponse> {
  return call<GoogleAuthUrlResponse>(() => api.GET("/api/v1/auth/google/authorize"));
}

/** Confirms an email address with the token from the verification link. */
export async function verifyEmail(token: string): Promise<void> {
  return call<void>(() => api.POST("/api/v1/auth/verify-email", { body: { token } }));
}

/**
 * Emails a new verification link. A request inside the cooldown rejects with a 429 whose message
 * is `rate_limited`; any other failure with a fixed message, never the response body.
 */
export async function resendVerificationEmail(email: string): Promise<void> {
  try {
    await api.POST("/api/v1/auth/verify-email/resend", { body: { email } });
  } catch (error) {
    if (error instanceof ApiRequestError) {
      // The form shows its own text for the cooldown, keyed on this sentinel.
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

/** The user the token belongs to. */
export async function getCurrentUser(token: string): Promise<CurrentUser> {
  return call<CurrentUser>(() => api.GET("/api/v1/user/me", { headers: bearer(token) }));
}

/** Update the current user's name or language; fields left out keep their stored value. */
export async function updateCurrentUser(token: string, data: UserUpdate): Promise<CurrentUser> {
  return call<CurrentUser>(() =>
    api.PATCH("/api/v1/user/me", { body: data, headers: bearer(token) }),
  );
}

/** Change the current user's password, given their current one. Resolves on 204. */
export async function changePassword(token: string, data: PasswordChange): Promise<void> {
  return call<void>(() =>
    api.POST("/api/v1/user/me/password", { body: data, headers: bearer(token) }),
  );
}

/**
 * Ask for a password reset link to be emailed. Resolves on 202 whether or not the email has an
 * account; a request inside the per-email cooldown rejects with a 429 `ApiRequestError`.
 */
export async function requestPasswordReset(email: string): Promise<void> {
  await call(() => api.POST("/api/v1/auth/password-reset", { body: { email } }));
}

/** Set a new password with a reset link's token. Resolves on 204; a refused link is a 400. */
export async function confirmPasswordReset(data: PasswordResetConfirm): Promise<void> {
  return call<void>(() => api.POST("/api/v1/auth/password-reset/confirm", { body: data }));
}
