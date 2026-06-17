import { expect, type APIRequestContext, type Page } from "@playwright/test";
import { apiBaseUrl } from "../config";

const PASSWORD_SUFFIX = "A1!";

export interface RandomUser {
  name: string;
  username: string;
  email: string;
  password: string;
}

/**
 * Generates a unique user payload. Username/email are randomized so tests can
 * run in parallel without colliding on the database's UNIQUE constraints.
 *
 * The username column is `max_length=20` (see `app/models/user.py`), so we
 * cap the prefix and use a UUID-derived suffix — slicing a UUID gives true
 * random bits that survive truncation, unlike a timestamp prefix.
 */
export function randomUser(prefix = "e2e"): RandomUser {
  const suffix = crypto.randomUUID().replace(/-/g, "").slice(0, 11);
  const username = `${prefix.slice(0, 8)}-${suffix}`;
  return {
    name: `E2E User ${suffix}`,
    username,
    email: `${username}@example.com`,
    password: `Pw-${suffix}${PASSWORD_SUFFIX}`,
  };
}

/**
 * Fill and submit the sign-up form on `/register`.
 */
export async function signUpViaUi(page: Page, user: RandomUser): Promise<void> {
  await page.goto("/register");
  await page.locator('input[name="name"]').fill(user.name);
  await page.locator('input[name="username"]').fill(user.username);
  await page.locator('input[name="email"]').fill(user.email);
  await page.locator('input[name="password"]').fill(user.password);
  await page.locator('input[name="confirmPassword"]').fill(user.password);
  await page.getByRole("button", { name: /create account/i }).click();
  // The form swaps to a "Check your email" success state on success.
  await expect(page.getByText(/check your email/i)).toBeVisible();
}

/**
 * Fill and submit the login form on `/login`.
 */
export async function logInViaUi(page: Page, username: string, password: string): Promise<void> {
  await page.goto("/login");
  await page.locator('input[name="username"]').fill(username);
  await page.locator('input[name="password"]').fill(password);
  // Anchor the regex so the "Sign in with Google" OAuth button isn't matched.
  await page.getByRole("button", { name: /^sign in$/i }).click();
}

/**
 * Hit the JSON login endpoint directly — used by `auth.setup.ts` to obtain a
 * token without going through the UI form on every spec run.
 */
export async function logInViaApi(
  request: APIRequestContext,
  username: string,
  password: string,
): Promise<{ access_token: string; expires_at: string }> {
  const response = await request.post(`${apiBaseUrl}/api/v1/auth/login`, {
    data: { username, password },
  });
  if (!response.ok()) {
    throw new Error(`Login failed for ${username}: ${response.status()} ${await response.text()}`);
  }
  return (await response.json()) as { access_token: string; expires_at: string };
}
