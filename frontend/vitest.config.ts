import { defineConfig } from "vitest/config";
import react from "@vitejs/plugin-react";
import path from "path";

export default defineConfig({
  plugins: [react()],
  test: {
    environment: "jsdom",
    globals: true,
    setupFiles: ["./vitest.setup.ts"],
    // Vitest owns the tests/ mirror and nothing else: an explicit include keeps the
    // suite from picking up stray specs elsewhere in the tree — notably the Playwright
    // e2e specs in e2e-tests/, which run via `make test.e2e`.
    include: ["tests/**/*.test.{ts,tsx}"],
  },
  resolve: {
    alias: {
      "@": path.resolve(__dirname, "."),
    },
  },
});
