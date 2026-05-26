import { defineConfig, devices } from "@playwright/test";
import "dotenv/config";

/**
 * Sparkth Playwright config.
 *
 * Reads environment variables from a `.env` file at the frontend root (loaded
 * via `dotenv/config` above). The variables consumed by the suite live in
 * `tests/config.ts`.
 *
 * See https://playwright.dev/docs/test-configuration.
 */
const BASE_URL = process.env.PLAYWRIGHT_BASE_URL ?? "http://localhost:3000";

export default defineConfig({
  testDir: "./tests",
  /* Run tests in files in parallel */
  fullyParallel: true,
  /* Fail the build on CI if you accidentally left test.only in the source code. */
  forbidOnly: !!process.env.CI,
  /* No retries — for a new suite, flakes should be loud, not silently rescued. */
  retries: 0,
  /* Opt out of parallel tests on CI. */
  workers: process.env.CI ? 1 : undefined,
  /* Reporter to use. See https://playwright.dev/docs/test-reporters */
  reporter: process.env.CI ? "blob" : "html",
  /* Shared settings for all the projects below. See https://playwright.dev/docs/api/class-testoptions. */
  use: {
    baseURL: BASE_URL,
    trace: "on-first-retry",
  },

  projects: [
    { name: "setup", testMatch: /.*\.setup\.ts/ },

    {
      name: "chromium",
      use: {
        ...devices["Desktop Chrome"],
        storageState: "playwright/.auth/user.json",
      },
      dependencies: ["setup"],
    },

    // {
    //   name: "firefox",
    //   use: {
    //     ...devices["Desktop Firefox"],
    //     storageState: "playwright/.auth/user.json",
    //   },
    //   dependencies: ["setup"],
    // },

    // {
    //   name: "webkit",
    //   use: {
    //     ...devices["Desktop Safari"],
    //     storageState: "playwright/.auth/user.json",
    //   },
    //   dependencies: ["setup"],
    // },
  ],

  // Start `next dev` locally; in CI the app is started by docker compose
  // (see .github/workflows/playwright.yml), and PLAYWRIGHT_NO_WEBSERVER=1 is set.
  webServer: process.env.PLAYWRIGHT_NO_WEBSERVER
    ? undefined
    : {
        command: "bun run dev",
        url: BASE_URL,
        reuseExistingServer: !process.env.CI,
        timeout: 120_000,
      },
});
