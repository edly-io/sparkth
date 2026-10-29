import type { Page } from "@playwright/test";

export const todayUtc = (): string => new Date().toISOString().slice(0, 10);

/**
 * Stubs the logins read API. The page asks for the period and the period before it; a
 * request ending before today is the previous one.
 */
export async function stubLogins(
  page: Page,
  current: unknown,
  previous: unknown = [],
  status = 200,
): Promise<void> {
  await stubPeriods(page, "**/api/v1/analytics/logins**", current, previous, status);
}

/** Stubs the compose authoring-activity read API, with the same period rule as `stubLogins`. */
export async function stubComposeActivity(
  page: Page,
  current: unknown,
  previous: unknown = [],
  status = 200,
): Promise<void> {
  await stubPeriods(page, "**/api/v1/compose/analytics/activity**", current, previous, status);
}

/** Stubs the Drive documents read API, with the same period rule as `stubLogins`. */
export async function stubDriveDocuments(
  page: Page,
  current: unknown,
  previous: unknown = [],
  status = 200,
): Promise<void> {
  await stubPeriods(
    page,
    "**/api/v1/google-drive/analytics/documents**",
    current,
    previous,
    status,
  );
}

/** Stubs the period summary API: one response carries both periods. */
export async function stubSummary(page: Page, figures: unknown, status = 200): Promise<void> {
  await page.route("**/api/v1/analytics/summary**", (route) =>
    route.fulfill({ status, contentType: "application/json", body: JSON.stringify(figures) }),
  );
}

async function stubPeriods(
  page: Page,
  url: string,
  current: unknown,
  previous: unknown,
  status: number,
): Promise<void> {
  await page.route(url, (route) => {
    const to = new URL(route.request().url()).searchParams.get("to") ?? "";
    const body = to < todayUtc() ? previous : current;
    return route.fulfill({ status, contentType: "application/json", body: JSON.stringify(body) });
  });
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

export const daysAgoUtc = (days: number): string =>
  new Date(Date.now() - days * 86_400_000).toISOString().slice(0, 10);
