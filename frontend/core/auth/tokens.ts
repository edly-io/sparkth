const TOKEN_KEY = "access_token";
const EXPIRES_KEY = "expires_at";

export function setAuthTokens(token: string, expiresAt: string): void {
  localStorage.setItem(TOKEN_KEY, token);
  localStorage.setItem(EXPIRES_KEY, expiresAt);
}

export function clearAuthTokens(): void {
  localStorage.removeItem(TOKEN_KEY);
  localStorage.removeItem(EXPIRES_KEY);
}

// Read the stored token if present and unexpired; clears it if expired.
// Returns null during the server render (no localStorage).
export function getStoredToken(): string | null {
  if (typeof window === "undefined") return null;

  const storedToken = localStorage.getItem(TOKEN_KEY);
  const expiresAt = localStorage.getItem(EXPIRES_KEY);

  if (storedToken && expiresAt) {
    const isExpired = new Date(expiresAt) < new Date();
    if (!isExpired) {
      return storedToken;
    }
    clearAuthTokens();
  }
  return null;
}
