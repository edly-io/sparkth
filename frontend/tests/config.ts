/**
 * Shared configuration for Playwright E2E tests.
 *
 * Values come from environment variables (loaded via `dotenv/config` in
 * `playwright.config.ts`). Defaults match `compose.yml`'s local dev setup so
 * the suite "just works" against `make services.up`.
 */

export const firstSuperuser = process.env.FIRST_SUPERUSER ?? "admin";
export const firstSuperuserPassword = process.env.FIRST_SUPERUSER_PASSWORD ?? "Sparkth-admin-1!";
export const firstSuperuserEmail = process.env.FIRST_SUPERUSER_EMAIL ?? "admin@sparkth.local";

export const apiBaseUrl = process.env.PLAYWRIGHT_API_URL ?? "http://localhost:7727";
export const mailpitBaseUrl = process.env.MAILPIT_URL ?? "http://localhost:8025";
