import { test, expect } from "@playwright/test";
import { apiBaseUrl } from "./config";
import { extractVerificationLink, findLatestMessageTo } from "./utils/mailpit";
import { logInViaUi, randomUser, signUpViaUi } from "./utils/user";

// Sign-up tests must run logged out.
test.use({ storageState: { cookies: [], origins: [] } });

test.describe("sign up", () => {
  test("registers a new user and shows the verification prompt", async ({ page }) => {
    const user = randomUser("signup");
    await signUpViaUi(page, user);
    await expect(page.getByText(user.email)).toBeVisible();
    await expect(page.getByRole("link", { name: /back to sign in/i })).toBeVisible();
  });

  test("rejects mismatched password confirmation", async ({ page }) => {
    const user = randomUser("signup-mismatch");
    await page.goto("/register");
    await page.locator('input[name="name"]').fill(user.name);
    await page.locator('input[name="username"]').fill(user.username);
    await page.locator('input[name="email"]').fill(user.email);
    await page.locator('input[name="password"]').fill(user.password);
    await page.locator('input[name="confirmPassword"]').fill(`${user.password}-different`);
    await page.getByRole("button", { name: /create account/i }).click();
    await expect(page.getByText(/passwords do not match/i)).toBeVisible();
    // Form did not advance to the success screen.
    await expect(page.getByText(/check your email/i)).not.toBeVisible();
  });

  test("rejects duplicate usernames", async ({ page, request }) => {
    const user = randomUser("signup-dup");
    // Seed the first user via the API so the form only needs to assert the
    // server-side duplicate rejection.
    const initial = await request.post(`${apiBaseUrl}/api/v1/auth/register`, {
      data: {
        name: user.name,
        username: user.username,
        email: user.email,
        password: user.password,
      },
    });
    expect(initial.ok()).toBeTruthy();

    await signUpViaUiExpectingError(page, user);
  });

  test("verifies a freshly registered user end-to-end via mailpit", async ({ page, request }) => {
    const user = randomUser("signup-verify");
    await signUpViaUi(page, user);

    const message = await findLatestMessageTo(request, user.email);

    // extractVerificationLink throws if it doesn't find a /verify-email URL,
    // which is a stronger assertion than a Subject substring match.
    const verificationLink = extractVerificationLink(message);
    // The link points at FRONTEND_BASE_URL; rewrite the origin to whatever
    // the test runner is hitting so we land on the local app.
    const verificationUrl = new URL(verificationLink);
    await page.goto(verificationUrl.pathname + verificationUrl.search + verificationUrl.hash);

    await expect(page.getByText(/email verified|account is ready|sign in/i)).toBeVisible();

    // The user can now log in.
    await logInViaUi(page, user.username, user.password);
    await expect(page).toHaveURL(/\/dashboard|\/$/);
  });
});

/**
 * Submit the sign-up form and assert an inline server-side error is shown.
 * Used for cases like duplicate username/email where the form should stay on
 * `/register` rather than advancing to the success screen.
 */
async function signUpViaUiExpectingError(
  page: import("@playwright/test").Page,
  user: ReturnType<typeof randomUser>,
): Promise<void> {
  await page.goto("/register");
  await page.locator('input[name="name"]').fill(user.name);
  await page.locator('input[name="username"]').fill(user.username);
  await page.locator('input[name="email"]').fill(user.email);
  await page.locator('input[name="password"]').fill(user.password);
  await page.locator('input[name="confirmPassword"]').fill(user.password);
  await page.getByRole("button", { name: /create account/i }).click();
  await expect(page.getByText(/check your email/i)).not.toBeVisible();
  // The form re-renders without redirecting; the alert/error banner is shown.
  await expect(page).toHaveURL(/\/register/);
}
