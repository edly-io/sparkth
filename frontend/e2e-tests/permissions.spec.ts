import { test, expect, type Page } from "@playwright/test";
import {
  stubGroups,
  stubPermissionList,
  stubPermissions,
  stubRole,
  stubRoles,
} from "./utils/permissions";

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
        description: "Edits courses",
        permissions: [],
        is_builtin: false,
        is_default: false,
        user_count: 0,
        group_count: 0,
        risks: ["delegates_access"],
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

  test("creates a role with the permissions ticked", async ({ page }) => {
    await stubPermissions(page, [...ALL_THREE, "role.create", "role.update"]);
    await stubPermissionList(page, [
      {
        name: "role.read",
        label: "See roles",
        description: "See every role and what it allows.",
        category: "Users & access",
        risks: [],
        requires: [],
      },
      {
        name: "role.update",
        label: "Change roles",
        description: "Choose what a role allows.",
        category: "Users & access",
        risks: ["delegates_access"],
        requires: [],
      },
    ]);
    const sent: unknown[] = [];
    await page.route("**/api/v1/permissions/roles", (route) => {
      if (route.request().method() !== "POST") return route.fallback();
      sent.push(route.request().postDataJSON());
      return route.fulfill({ status: 201, json: {} });
    });
    await page.goto("/dashboard/permissions/roles");

    await page.getByRole("button", { name: "Create role" }).click();
    await page.getByLabel("Name").fill("Grader");
    await page.getByRole("radio", { name: "Choose permissions" }).click();
    await page.getByLabel("Search permissions").fill("change");
    await expect(page.getByRole("checkbox", { name: "See roles" })).toHaveCount(0);
    await page.getByRole("checkbox", { name: "Change roles" }).check();
    await page.getByRole("button", { name: "Create", exact: true }).click();

    await expect
      .poll(() => sent)
      .toEqual([{ name: "Grader", description: null, permissions: ["role.update"] }]);
  });

  test("opens a role's page from its card", async ({ page }) => {
    await stubPermissions(page, ALL_THREE);
    await stubRole(page, {
      id: 1,
      name: "Course editor",
      description: "Edits courses",
      permissions: ["role.read"],
      is_builtin: false,
      is_default: false,
      user_count: 0,
      group_count: 0,
      risks: [],
    });
    await stubPermissionList(page, [
      {
        name: "role.read",
        label: "See roles",
        description: "See every role and what it allows.",
        category: "Users & access",
        risks: [],
        requires: [],
      },
    ]);
    await page.goto("/dashboard/permissions/roles");

    await page.getByRole("link", { name: "Course editor" }).click();

    await expect(page).toHaveURL(/\/dashboard\/permissions\/roles\/role\/?\?id=1$/);
    await expect(page.getByRole("heading", { name: "Course editor" })).toBeVisible();
    await expect(page.getByRole("checkbox", { name: "See roles" })).toBeChecked();
    await expect(
      page.getByRole("navigation", { name: "Breadcrumb" }).getByRole("link", { name: "Roles" }),
    ).toBeVisible();
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
