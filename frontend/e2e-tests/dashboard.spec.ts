import { test, expect, type APIRequestContext } from "@playwright/test";

import type { PluginState } from "@/core/plugins/types";
import { apiBaseUrl, firstSuperuser, firstSuperuserPassword } from "./config";
import { logInViaApi } from "./utils/user";

/** The enabled plugins with a frontend, as the plugins API declares them. */
async function frontendPlugins(request: APIRequestContext): Promise<PluginState[]> {
  const { access_token } = await logInViaApi(request, firstSuperuser, firstSuperuserPassword);
  const response = await request.get(`${apiBaseUrl}/api/v1/plugins/`, {
    headers: { Authorization: `Bearer ${access_token}` },
  });
  const plugins = ((await response.json()) as PluginState[]).filter(
    (plugin) => plugin.enabled && plugin.has_frontend,
  );
  expect(plugins.length).toBeGreaterThan(0);
  return plugins;
}

/**
 * Authenticated dashboard checks. Uses the shared storage state from
 * `auth.setup.ts`, so every test starts as the seeded superuser.
 */
test.describe("dashboard", () => {
  test("renders the dashboard for an authenticated user", async ({ page }) => {
    await page.goto("/dashboard");
    await expect(page.getByRole("heading", { name: /dashboard/i })).toBeVisible();
    await expect(page.getByText(/manage your enabled plugins/i)).toBeVisible();
  });

  test("navigates to plugin settings", async ({ page }) => {
    await page.goto("/dashboard");
    await page.goto("/dashboard/settings");
    await expect(page.getByRole("heading", { name: "Settings", exact: true })).toBeVisible();
  });

  // The backend declares each plugin's icons by name; the frontend must ship a component for every one,
  // or the card and sidebar link fall back to a letter.
  test("shows each icon a plugin declares", async ({ page, request }) => {
    const plugins = await frontendPlugins(request);

    await page.goto("/dashboard");
    const cards = page.getByRole("link").filter({ has: page.getByRole("heading", { level: 3 }) });
    for (const plugin of plugins) {
      const href = `[href^="/dashboard/${plugin.plugin_name}"]`;
      if (plugin.display?.icon) {
        const card = cards.and(page.locator(href));
        await expect(card.locator("svg"), `${plugin.plugin_name}'s card icon`).toHaveCount(2);
      }
      if (plugin.sidebar?.icon) {
        const link = page.getByRole("navigation").first().locator(`a${href}`);
        await expect(link.locator("svg"), `${plugin.plugin_name}'s sidebar icon`).toHaveCount(1);
      }
    }
  });

  test("opens the page of every plugin with a frontend", async ({ page, request }) => {
    for (const plugin of await frontendPlugins(request)) {
      await page.goto(`/dashboard/${plugin.plugin_name}`);
      await page.waitForLoadState("networkidle");
      // The not-found page for an address with no built page, or core's "Plugin <name> not found".
      await expect(page.getByText(/not found/i)).toHaveCount(0);
    }
  });

  test("says no plugin has that name at an address that names none", async ({ page }) => {
    await page.goto("/dashboard/nosuchplugin");

    await expect(page.getByRole("heading", { name: "Plugin not found" })).toBeVisible();
    await expect(
      page.getByText("No plugin is registered with the name nosuchplugin."),
    ).toBeVisible();
    await page.getByRole("link", { name: "Back to dashboard" }).click();
    await expect(page.getByRole("heading", { name: /dashboard/i })).toBeVisible();
  });

  test("redirects to login when the token is cleared", async ({ page }) => {
    await page.goto("/dashboard");
    await page.evaluate(() => window.localStorage.clear());
    await page.goto("/dashboard");
    await expect(page).toHaveURL(/\/login/);
  });
});
