// Runs the i18n-check drift guard once per catalog: the core catalog against
// core sources, then each plugin catalog against that plugin's own sources.
// Mirrors the backend containment rule: core extraction ignores plugins, and
// a plugin owns (and is checked against) only its own catalogs.
import { spawnSync } from "node:child_process";
import { existsSync, readdirSync } from "node:fs";

const SHARED_ARGS = [
  "--source",
  "en",
  "--format",
  "next-intl",
  "--only",
  "invalidKeys,missingKeys,unused,undefined",
];

function check(localesDir, sourcePaths) {
  console.log(`i18n-check: ${localesDir} against ${sourcePaths.join(", ")}`);
  const result = spawnSync(
    "bunx",
    ["i18n-check", "--locales", localesDir, ...SHARED_ARGS, "--unused", ...sourcePaths],
    { stdio: "inherit" },
  );
  return result.status ?? 1;
}

let failed = check("messages", ["app", "components", "lib", "hooks"]) !== 0;

for (const entry of readdirSync("plugins", { withFileTypes: true })) {
  if (!entry.isDirectory()) continue;
  const catalogDir = `plugins/${entry.name}/messages`;
  if (!existsSync(catalogDir)) continue;
  failed = check(catalogDir, [`plugins/${entry.name}`]) !== 0 || failed;
}

process.exit(failed ? 1 : 0);
