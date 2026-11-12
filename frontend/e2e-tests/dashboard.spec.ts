import { test, expect } from "@playwright/test";
import { apiBaseUrl, firstSuperuser, firstSuperuserPassword } from "./config";
import { logInViaApi } from "./utils/user";

/** The fields of a user-plugins API entry this spec reads. */
interface DeclaredPlugin {
  plugin_name: string;
  enabled: boolean;
  has_frontend: boolean;
  display?: { icon?: string | null } | null;
  sidebar?: { icon?: string | null } | null;
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
  // or the card and sidebar link fall back to a letter. Every plugin with a frontend must have a page.
  test("shows each icon a plugin declares and opens its page", async ({ page, request }) => {
    const { access_token } = await logInViaApi(request, firstSuperuser, firstSuperuserPassword);
    const response = await request.get(`${apiBaseUrl}/api/v1/user-plugins/`, {
      headers: { Authorization: `Bearer ${access_token}` },
    });
    const plugins = ((await response.json()) as DeclaredPlugin[]).filter(
      (plugin) => plugin.enabled && plugin.has_frontend,
    );
    expect(plugins.length).toBeGreaterThan(0);

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

    for (const plugin of plugins) {
      await page.goto(`/dashboard/${plugin.plugin_name}`);
      await page.waitForLoadState("networkidle");
      // Core's "Plugin Not Found" / "Plugin <name> not found", or the export's 404 for a page it never built.
      await expect(page.getByText(/not found|could not be found/i)).toHaveCount(0);
    }
  });

  test("redirects to login when the token is cleared", async ({ page }) => {
    await page.goto("/dashboard");
    await page.evaluate(() => window.localStorage.clear());
    await page.goto("/dashboard");
    await expect(page).toHaveURL(/\/login/);
  });
});
