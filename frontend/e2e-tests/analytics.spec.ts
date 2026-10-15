import { test, expect } from "@playwright/test";
import {
  daysAgoUtc,
  stubChatActivity,
  stubLogins,
  stubPermission,
  stubSummary,
  todayUtc,
} from "./utils/analytics";

/**
 * Analytics dashboard. Runs as the seeded e2e user (auth.setup.ts), which has no roles, so
 * analytics.read and the read API are stubbed (utils/analytics.ts). Each view adds its own
 * specs here.
 */
const summary = [
  { key: "logins", label: "Logins", view: "logins", plugin: null, current: 4, previous: 2 },
  { key: "active_users", label: "Active users", view: null, plugin: null, current: 3, previous: 0 },
];

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
    await stubLogins(page, []);
    await page.goto("/dashboard/analytics/logins");
    await expect(page.getByText(/no logins in this period/i)).toBeVisible();
  });

  test("shows login totals when there is data", async ({ page }) => {
    await stubLogins(page, [{ bucket: todayUtc(), method: "password", login_count: 4 }]);
    await page.goto("/dashboard/analytics/logins");
    await expect(page.getByText("Total logins")).toBeVisible();
  });

  test("shows logins by sign-in method", async ({ page }) => {
    await stubLogins(page, [
      { bucket: todayUtc(), method: "google", login_count: 3 },
      { bucket: todayUtc(), method: "password", login_count: 1 },
    ]);
    await page.goto("/dashboard/analytics/logins");
    await expect(page.getByRole("heading", { name: "Sign-in method" })).toBeVisible();
    // The bar label; the screen-reader table repeats it.
    await expect(page.getByText("Google", { exact: true }).first()).toBeVisible();
  });

  test("compares the total with the previous period", async ({ page }) => {
    await stubLogins(
      page,
      [{ bucket: todayUtc(), method: "password", login_count: 4 }],
      [{ bucket: daysAgoUtc(40), method: "password", login_count: 2 }],
    );
    await page.goto("/dashboard/analytics/logins");
    await expect(page.getByText("+100% vs previous period", { exact: true })).toBeVisible();
  });

  test("opens the Overview from the sidebar, with its rail entry current", async ({ page }) => {
    await stubSummary(page, []);
    await page.goto("/dashboard");
    await page.getByRole("link", { name: "Analytics" }).first().click();
    await expect(page).toHaveURL(/\/dashboard\/analytics\/?$/);
    await expect(page.getByRole("link", { name: "Overview" })).toHaveAttribute(
      "aria-current",
      "page",
    );
  });

  test("opens on the Overview with a card per figure", async ({ page }) => {
    await stubSummary(page, summary);
    await page.goto("/dashboard/analytics");
    await expect(page.getByText("Logins", { exact: true }).first()).toBeVisible();
    await expect(page.getByText("+100% vs previous period", { exact: true })).toBeVisible();
    await expect(page.getByText("New this period", { exact: true })).toBeVisible();
  });

  test("a card opens the view behind it", async ({ page }) => {
    await stubSummary(page, summary);
    await stubLogins(page, []);
    await page.goto("/dashboard/analytics");
    await page
      .getByRole("link", { name: /Logins/ })
      .filter({ hasText: "4" })
      .click();
    await expect(page).toHaveURL(/\/dashboard\/analytics\/logins\/?/);
  });

  test("collapses the rail to tabs on a phone with no horizontal scroll", async ({ page }) => {
    await stubLogins(page, []);
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
    await stubLogins(page, [{ bucket: todayUtc(), method: "password", login_count: 4 }]);
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

test.describe("analytics course authoring", () => {
  test("opens from its rail entry, with the entry current", async ({ page }) => {
    await stubLogins(page, []);
    await stubChatActivity(page, []);
    await page.goto("/dashboard/analytics/logins");
    await page.getByRole("link", { name: "Course authoring" }).click();
    await expect(page).toHaveURL(/\/dashboard\/analytics\/authoring\/?$/);
    await expect(page.getByRole("link", { name: "Course authoring" })).toHaveAttribute(
      "aria-current",
      "page",
    );
  });

  test("shows activity and the tools used", async ({ page }) => {
    await stubChatActivity(page, [
      { bucket: todayUtc(), event_type: "chat.message_sent", event_count: 4 },
      {
        bucket: todayUtc(),
        event_type: "chat.tool_invoked",
        dimension: "create_course",
        outcome: "succeeded",
        event_count: 2,
      },
    ]);
    await page.goto("/dashboard/analytics/authoring");
    await expect(page.getByText("Messages sent", { exact: true })).toBeVisible();
    // The bar label; the screen-reader table repeats it.
    await expect(page.getByText("create_course", { exact: true }).first()).toBeVisible();
  });

  test("keeps the period when switching between Logins and Course authoring", async ({ page }) => {
    await stubLogins(page, []);
    await stubChatActivity(page, []);
    await page.goto("/dashboard/analytics/logins?range=90d&bucket=month");
    await page.getByRole("link", { name: "Course authoring" }).click();
    await expect(page).toHaveURL(/\/authoring\/?\?range=90d&bucket=month/);
    await page.getByRole("link", { name: "Logins" }).click();
    await expect(page).toHaveURL(/\/logins\/?\?range=90d&bucket=month/);
  });

  test("shows the empty state for a period with no activity", async ({ page }) => {
    await stubChatActivity(page, []);
    await page.goto("/dashboard/analytics/authoring");
    await expect(page.getByText(/no course-authoring activity in this period/i)).toBeVisible();
  });
});
