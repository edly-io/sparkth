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

let failed = check("messages", ["app", "components", "core", "lib", "hooks"]) !== 0;

// A plugin keeps its catalogs in src/i18n and is checked against its src. A plugin not yet in that
// layout keeps them in messages/ and is checked against the whole plugin.
for (const entry of readdirSync("plugins", { withFileTypes: true })) {
  if (!entry.isDirectory()) continue;
  const plugin = `plugins/${entry.name}`;
  if (existsSync(`${plugin}/src/i18n`)) {
    failed = check(`${plugin}/src/i18n`, [`${plugin}/src`]) !== 0 || failed;
  } else if (existsSync(`${plugin}/messages`)) {
    failed = check(`${plugin}/messages`, [plugin]) !== 0 || failed;
  }
}

process.exit(failed ? 1 : 0);
