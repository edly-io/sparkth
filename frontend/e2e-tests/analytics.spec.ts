import { test, expect } from "@playwright/test";
import { denyPermission, stubLoginActivity, todayUtc } from "./utils/analytics";

/**
 * Analytics dashboard. Runs as the seeded superuser (auth.setup.ts), with the read API
 * stubbed (utils/analytics.ts). Each view adds its own specs here.
 */
test.describe("analytics", () => {
  test("redirects to the dashboard without analytics.read", async ({ page }) => {
    await denyPermission(page, "analytics.read");
    await page.goto("/dashboard/analytics/logins");
    await expect(page).toHaveURL(/\/dashboard\/?$/);
  });

  test("shows the empty state for a period with no logins", async ({ page }) => {
    await stubLoginActivity(page, []);
    await page.goto("/dashboard/analytics/logins");
    await expect(page.getByText(/no logins in the last 30 days/i)).toBeVisible();
  });

  test("shows login totals when there is data", async ({ page }) => {
    await stubLoginActivity(page, [{ day: todayUtc(), login_count: 4 }]);
    await page.goto("/dashboard/analytics/logins");
    await expect(page.getByText("Total logins")).toBeVisible();
  });

  test("opens the Logins view from the sidebar, with its rail entry current", async ({ page }) => {
    await stubLoginActivity(page, []);
    await page.goto("/dashboard");
    await page.getByRole("link", { name: "Analytics" }).first().click();
    await expect(page).toHaveURL(/\/dashboard\/analytics\/logins\/?$/);
    await expect(page.getByRole("link", { name: "Logins" })).toHaveAttribute(
      "aria-current",
      "page",
    );
    // The index forwards with replace, so Back returns to the dashboard rather than bouncing.
    await page.goBack();
    await expect(page).toHaveURL(/\/dashboard\/?$/);
  });

  test("collapses the rail to tabs on a phone with no horizontal scroll", async ({ page }) => {
    await stubLoginActivity(page, []);
    await page.setViewportSize({ width: 375, height: 800 });
    await page.goto("/dashboard/analytics/logins");
    await expect(page.getByRole("navigation", { name: "Analytics views" })).toBeVisible();
    const overflow = await page.evaluate(
      () => document.documentElement.scrollWidth - document.documentElement.clientWidth,
    );
    expect(overflow).toBeLessThanOrEqual(0);
  });
});
