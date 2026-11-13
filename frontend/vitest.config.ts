import { defineConfig } from "vitest/config";
import react from "@vitejs/plugin-react";
import { existsSync, readdirSync } from "fs";
import path from "path";

// sparkth-pxc.js imports "./pxc.js", which the backend serves from the installed pxc-lib
// distribution. Tests resolve it to that same file in the backend's virtualenv.
const venvLib = path.resolve(__dirname, "../.venv/lib");
const pxcJs = existsSync(venvLib)
  ? readdirSync(venvLib)
      .map((python) => path.join(venvLib, python, "site-packages/pxc/lib/static/js/pxc.js"))
      .find((candidate) => existsSync(candidate))
  : undefined;

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
    alias: [
      // app/pluginModules.ts loads the plugins with require.context, which Vitest lacks, so tests load
      // them through a stand-in. An alias, not vi.mock: a mock's factory is not re-run after
      // vi.resetModules(), so the plugins would never fill a fresh slot.
      {
        find: /^@\/app\/pluginModules$/,
        replacement: path.resolve(__dirname, "tests/app/pluginModules.ts"),
      },
      { find: "@", replacement: path.resolve(__dirname, ".") },
      ...(pxcJs ? [{ find: /^\.\/pxc\.js$/, replacement: pxcJs }] : []),
    ],
  },
});
