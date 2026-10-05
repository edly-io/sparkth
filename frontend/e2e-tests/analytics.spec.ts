import { test, expect } from "@playwright/test";
import { daysAgoUtc, stubLoginActivity, stubPermission, todayUtc } from "./utils/analytics";

/**
 * Analytics dashboard. Runs as the seeded e2e user (auth.setup.ts), which has no roles, so
 * analytics.read and the read API are stubbed (utils/analytics.ts). Each view adds its own
 * specs here.
 */
test.beforeEach(async ({ page }) => {
  await stubPermission(page, "analytics.read", true);
});

test.describe("analytics", () => {
  test("shows the 403 view without analytics.read, staying on the URL", async ({ page }) => {
    // Registered after the beforeEach grant, so this route wins.
    await stubPermission(page, "analytics.read", false);
    await page.goto("/dashboard/analytics/logins");
    await expect(
      page.getByRole("heading", { name: "You don't have access to this page" }),
    ).toBeVisible();
    await expect(page).toHaveURL(/\/dashboard\/analytics\/logins\/?$/);
  });

  test("shows the empty state for a period with no logins", async ({ page }) => {
    await stubLoginActivity(page, []);
    await page.goto("/dashboard/analytics/logins");
    await expect(page.getByText(/no logins in this period/i)).toBeVisible();
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

test.describe("analytics period", () => {
  test.beforeEach(async ({ page }) => {
    await stubLoginActivity(page, [{ day: todayUtc(), login_count: 4 }]);
  });

  test("a preset and bucket survive a reload", async ({ page }) => {
    await page.goto("/dashboard/analytics/logins");
    await page.getByLabel("Period").selectOption("7d");
    await page.getByLabel("Group by").selectOption("week");
    await expect(page).toHaveURL(/range=7d&bucket=week/);
    await page.reload();
    await expect(page.getByLabel("Period")).toHaveValue("7d");
    await expect(page.getByLabel("Group by")).toHaveValue("week");
  });

  test("a custom range is written to the URL", async ({ page }) => {
    await page.goto("/dashboard/analytics/logins");
    await page.getByLabel("Period").selectOption("custom");
    // Relative to today, so the range never falls outside the selectable window.
    const from = daysAgoUtc(30);
    const to = daysAgoUtc(1);
    await page.getByLabel("Start date").fill(from);
    await page.getByLabel("End date").fill(to);
    await page.getByRole("button", { name: "Apply" }).click();
    await expect(page).toHaveURL(new RegExp(`from=${from}&to=${to}`));
  });

  test("an inverted custom range is blocked inline", async ({ page }) => {
    await page.goto("/dashboard/analytics/logins");
    await page.getByLabel("Period").selectOption("custom");
    await page.getByLabel("Start date").fill(daysAgoUtc(1));
    await page.getByLabel("End date").fill(daysAgoUtc(30));
    await page.getByRole("button", { name: "Apply" }).click();
    // Not getByRole("alert"): Next's route announcer also carries role="alert".
    await expect(page.locator("#period-error")).toContainText(/start date must be on or before/i);
    await expect(page).not.toHaveURL(/from=/);
  });

  test("switching views keeps the period", async ({ page }) => {
    await page.goto("/dashboard/analytics/logins?range=90d&bucket=month");
    await expect(page.getByRole("link", { name: "Logins" })).toHaveAttribute(
      "href",
      /range=90d&bucket=month/,
    );
  });
});
