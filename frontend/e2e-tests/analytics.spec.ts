import { test, expect } from "@playwright/test";
import { stubLoginActivity, todayUtc } from "./utils/analytics";

/**
 * Analytics dashboard. Runs as the seeded superuser (auth.setup.ts), with the read API
 * stubbed (utils/analytics.ts). Each view issue adds its own specs here.
 */
test.describe("analytics", () => {
  test("redirects to the dashboard when analytics access is denied", async ({ page }) => {
    // The superuser holds analytics.read, so the denial is simulated by the API's 403.
    await stubLoginActivity(page, { detail: "Permission denied" }, 403);
    await page.goto("/dashboard/analytics");
    await expect(page).toHaveURL(/\/dashboard\/?$/);
  });

  test("shows the empty state for a period with no logins", async ({ page }) => {
    await stubLoginActivity(page, []);
    await page.goto("/dashboard/analytics");
    await expect(page.getByText(/no logins in the last 30 days/i)).toBeVisible();
  });

  test("shows login totals when there is data", async ({ page }) => {
    await stubLoginActivity(page, [{ day: todayUtc(), login_count: 4 }]);
    await page.goto("/dashboard/analytics");
    await expect(page.getByText("Total logins")).toBeVisible();
  });
});
