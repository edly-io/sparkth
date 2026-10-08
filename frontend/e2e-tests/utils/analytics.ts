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
 * Makes `GET /api/v1/permissions/can` answer `allowed` for one permission and pass every other
 * check through. The seeded e2e user has no roles, so specs grant or deny what they need here.
 */
export async function stubPermission(
  page: Page,
  permission: string,
  allowed: boolean,
): Promise<void> {
  await page.route("**/api/v1/permissions/can**", (route) => {
    const url = new URL(route.request().url());
    if (url.searchParams.get("permission") !== permission) return route.continue();
    return route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({ allowed }),
    });
  });
}

export const todayUtc = (): string => new Date().toISOString().slice(0, 10);

export const daysAgoUtc = (days: number): string =>
  new Date(Date.now() - days * 86_400_000).toISOString().slice(0, 10);
