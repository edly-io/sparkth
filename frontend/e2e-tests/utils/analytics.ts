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
  await stubPeriods(page, "**/api/v1/googledrive/analytics/documents**", current, previous, status);
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

/** One permission check as the `/api/v1/permissions/can` probes send it. */
type SentCheck = { permission: string; scope: string; scope_object_id?: string | null };

/**
 * Makes the `/api/v1/permissions/can` probes answer `allowed` for one permission. A single check
 * naming another permission passes through. A batch is answered here in full, with every other
 * permission denied: the seeded e2e user has no roles, so that is what the backend would answer.
 */
export async function stubPermission(
  page: Page,
  permission: string,
  allowed: boolean,
): Promise<void> {
  await page.route("**/api/v1/permissions/can**", (route) => {
    const request = route.request();
    if (new URL(request.url()).pathname.endsWith("/batch")) {
      const checks = request.postDataJSON() as SentCheck[];
      const json = checks.map((check) => ({
        ...check,
        scope_object_id: check.scope_object_id ?? null,
        allowed: check.permission === permission && allowed,
      }));
      return route.fulfill({ json });
    }
    if (request.postDataJSON()?.permission !== permission) return route.continue();
    return route.fulfill({ json: { allowed } });
  });
}

export const daysAgoUtc = (days: number): string =>
  new Date(Date.now() - days * 86_400_000).toISOString().slice(0, 10);
