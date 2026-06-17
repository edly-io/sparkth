import { test as setup, expect } from "@playwright/test";
import { firstSuperuser, firstSuperuserPassword } from "./config";
import { logInViaApi } from "./utils/user";

const STORAGE_STATE = "playwright/.auth/user.json";

/**
 * One-time setup that authenticates the seeded superuser and persists the
 * resulting localStorage to `playwright/.auth/user.json`. Every chromium
 * project depends on this fixture, so individual specs start already logged in.
 *
 * The seeded superuser is created out-of-band — either by `make create-user`
 * locally or by the `seed-e2e-user` step in `.github/workflows/playwright.yml`.
 */
setup("authenticate", async ({ page, request }) => {
  const { access_token, expires_at } = await logInViaApi(
    request,
    firstSuperuser,
    firstSuperuserPassword,
  );

  // The frontend reads the token from localStorage on bootstrap, so we seed
  // it on the origin Playwright will use, then save the state.
  await page.goto("/");
  await page.evaluate(
    ({ token, expiresAt }) => {
      window.localStorage.setItem("access_token", token);
      window.localStorage.setItem("expires_at", expiresAt);
    },
    { token: access_token, expiresAt: expires_at },
  );

  // Visit the dashboard to confirm the token is accepted by the API.
  await page.goto("/dashboard");
  await expect(page).toHaveURL(/\/dashboard/);

  await page.context().storageState({ path: STORAGE_STATE });
});
