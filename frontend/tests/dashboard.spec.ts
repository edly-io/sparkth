import { test, expect } from "@playwright/test";

/**
 * Authenticated dashboard checks. Uses the shared storage state from
 * `auth.setup.ts`, so every test starts as the seeded superuser.
 */
test.describe("dashboard", () => {
  test("renders the dashboard for an authenticated user", async ({ page }) => {
    await page.goto("/dashboard");
    await expect(page.getByRole("heading", { name: /dashboard/i })).toBeVisible();
    await expect(page.getByText(/manage your enabled plugins/i)).toBeVisible();
  });

  test("navigates to plugin settings", async ({ page }) => {
    await page.goto("/dashboard");
    await page.goto("/dashboard/settings");
    await expect(page.getByRole("heading", { name: /my plugins/i })).toBeVisible();
  });

  test("redirects to login when the token is cleared", async ({ page }) => {
    await page.goto("/dashboard");
    await page.evaluate(() => window.localStorage.clear());
    await page.goto("/dashboard");
    await expect(page).toHaveURL(/\/login/);
  });
});
