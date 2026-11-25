import type { Page } from "@playwright/test";

/** One permission check as `POST /api/v1/permissions/can/batch` sends it. */
type SentCheck = { permission: string; scope: string; scope_object_id?: string | null };

/**
 * Makes `POST /api/v1/permissions/can/batch` grant the `granted` permissions, at whatever scope
 * they are asked. The batch is answered here in full, with every other permission denied: the
 * seeded e2e user has no roles, so that is what the backend would answer.
 */
export async function stubPermissions(page: Page, granted: readonly string[]): Promise<void> {
  await page.route("**/api/v1/permissions/can/batch", (route) => {
    const checks = route.request().postDataJSON() as SentCheck[];
    const json = checks.map((check) => ({
      ...check,
      scope_object_id: check.scope_object_id ?? null,
      allowed: granted.includes(check.permission),
    }));
    return route.fulfill({ json });
  });
}

/** Stubs `GET /api/v1/permissions/roles` with `roles`. */
export async function stubRoles(page: Page, roles: unknown[]): Promise<void> {
  await page.route("**/api/v1/permissions/roles", (route) => route.fulfill({ json: roles }));
}

/** Stubs `GET /api/v1/permissions/groups` with `groups`. */
export async function stubGroups(page: Page, groups: unknown[]): Promise<void> {
  await page.route("**/api/v1/permissions/groups", (route) => route.fulfill({ json: groups }));
}
