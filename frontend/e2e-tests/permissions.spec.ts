import { test, expect, type Page } from "@playwright/test";
import { stubGroups, stubPermissions, stubRoles } from "./utils/permissions";

/**
 * The Access & permissions section. Its sidebar entry and its pages need permission.read,
 * role.read and group.read together; the checks and the role and group lists are stubbed
 * (utils/permissions.ts).
 */
const ALL_THREE = ["permission.read", "role.read", "group.read"];

/** Opens the dashboard and waits for the sidebar's permission check to be answered. */
async function openDashboard(page: Page): Promise<void> {
  const answered = page.waitForResponse("**/api/v1/permissions/can/batch");
  await page.goto("/dashboard");
  await answered;
}

test.describe("access & permissions", () => {
  test.beforeEach(async ({ page }) => {
    await stubRoles(page, [
      {
        id: 1,
        name: "Course editor",
        display_name: "Course editor",
        description: "Edits courses",
        permissions: [],
        is_builtin: false,
        is_default: false,
        user_count: 0,
        group_count: 0,
      },
    ]);
    await stubGroups(page, [{ id: 2, name: "Science faculty", description: null }]);
  });

  test("opens on Roles from the sidebar and switches to Groups", async ({ page }) => {
    await stubPermissions(page, ALL_THREE);
    await openDashboard(page);

    await page.getByRole("link", { name: "Access & permissions" }).first().click();
    await expect(page).toHaveURL(/\/dashboard\/permissions\/roles\/?$/);
    await expect(page.getByRole("heading", { name: "Access & permissions" })).toBeVisible();
    await expect(page.getByRole("link", { name: "Roles", exact: true })).toHaveAttribute(
      "aria-current",
      "page",
    );
    await expect(page.getByText("Course editor")).toBeVisible();

    await page.getByRole("link", { name: "Groups", exact: true }).click();
    await expect(page).toHaveURL(/\/dashboard\/permissions\/groups\/?$/);
    await expect(page.getByRole("link", { name: "Groups", exact: true })).toHaveAttribute(
      "aria-current",
      "page",
    );
    await expect(page.getByText("Science faculty")).toBeVisible();
  });

  for (const missing of ALL_THREE) {
    test(`without ${missing} there is no entry and the URL shows no access`, async ({ page }) => {
      await stubPermissions(
        page,
        ALL_THREE.filter((permission) => permission !== missing),
      );
      await openDashboard(page);
      await expect(page.getByRole("link", { name: "Access & permissions" })).toHaveCount(0);

      await page.goto("/dashboard/permissions/roles");
      await expect(
        page.getByRole("heading", { name: "You don't have access to this page" }),
      ).toBeVisible();
      await expect(page.getByText("Course editor")).toHaveCount(0);
    });
  }
});
