import type { Page } from "@playwright/test";

/**
 * Stubs the analytics read API in the browser, so specs don't depend on seeded events.
 * `**` after the path matches any query string (`?days=30`, later `?from=…`).
 */
export async function stubLoginActivity(page: Page, body: unknown, status = 200): Promise<void> {
  await page.route("**/api/v1/analytics/login-activity**", (route) =>
    route.fulfill({ status, contentType: "application/json", body: JSON.stringify(body) }),
  );
}

/**
 * Makes `GET /api/v1/permissions/can` deny one permission and pass every other check through,
 * simulating a user who lacks it (the seeded superuser holds all of them).
 */
export async function denyPermission(page: Page, permission: string): Promise<void> {
  await page.route("**/api/v1/permissions/can**", (route) => {
    const url = new URL(route.request().url());
    if (url.searchParams.get("permission") !== permission) return route.continue();
    return route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({ allowed: false }),
    });
  });
}

export const todayUtc = (): string => new Date().toISOString().slice(0, 10);
