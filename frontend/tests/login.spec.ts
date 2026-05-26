import { test, expect } from "@playwright/test";
import { apiBaseUrl, firstSuperuser, firstSuperuserPassword } from "./config";
import { logInViaUi, randomUser } from "./utils/user";

// These specs exercise the login form directly, so they must NOT reuse the
// shared authenticated storage state — every test starts logged out.
test.use({ storageState: { cookies: [], origins: [] } });

test.describe("login", () => {
  test("logs a verified user into the dashboard", async ({ page }) => {
    await logInViaUi(page, firstSuperuser, firstSuperuserPassword);
    await expect(page).toHaveURL(/\/dashboard|\/$/);
    await page.goto("/dashboard");
    await expect(page.getByRole("heading", { name: /dashboard/i })).toBeVisible();
  });

  test("shows an error message for incorrect credentials", async ({ page }) => {
    await logInViaUi(page, firstSuperuser, "wrong-password");
    await expect(page.getByText(/incorrect username or password/i)).toBeVisible();
    await expect(page).toHaveURL(/\/login/);
  });

  test("prompts unverified users to resend the confirmation email", async ({ page, request }) => {
    // Register a brand-new user, then immediately try to log in. The backend
    // returns 403 with code=email_not_verified, and the form surfaces the
    // "resend confirmation email" CTA.
    const user = randomUser("login-unverified");
    const response = await request.post(`${apiBaseUrl}/api/v1/auth/register`, {
      data: {
        name: user.name,
        username: user.username,
        email: user.email,
        password: user.password,
      },
    });
    expect(response.ok()).toBeTruthy();

    await logInViaUi(page, user.username, user.password);
    await expect(page.getByText(/please confirm your email before logging in/i)).toBeVisible();
    await expect(page.getByRole("button", { name: /resend confirmation email/i })).toBeVisible();
  });

  test("links to the registration page", async ({ page }) => {
    await page.goto("/login");
    await page.getByRole("link", { name: /sign up/i }).click();
    await expect(page).toHaveURL(/\/register/);
  });
});
