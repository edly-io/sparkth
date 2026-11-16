// Runs the i18n-check drift guard once per catalog: the core catalog against
// core sources, then each plugin catalog against that plugin's own sources.
// Mirrors the backend containment rule: core extraction ignores plugins, and
// a plugin owns (and is checked against) only its own catalogs.
import { spawnSync } from "node:child_process";
import { existsSync, mkdtempSync, readFileSync, readdirSync, rmSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";

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

// Core's catalog is split across its features (core/<feature>/i18n/<locale>.json), and a key is
// often used outside its feature (most analytics keys are used in app/), so the features are
// merged per locale and checked together against every core source.
function mergeCoreCatalogs() {
  const merged = {};
  const walk = (dir) => {
    for (const entry of readdirSync(dir, { withFileTypes: true })) {
      const path = join(dir, entry.name);
      if (entry.isDirectory()) walk(path);
      else if (dir.endsWith("/i18n") && entry.name.endsWith(".json")) {
        const locale = entry.name.slice(0, -".json".length);
        Object.assign((merged[locale] ??= {}), JSON.parse(readFileSync(path, "utf8")));
      }
    }
  };
  walk("core");
  const dir = mkdtempSync(join(tmpdir(), "sparkth-i18n-"));
  for (const [locale, catalog] of Object.entries(merged)) {
    writeFileSync(join(dir, `${locale}.json`), JSON.stringify(catalog, null, 2));
  }
  return dir;
}

const coreCatalogDir = mergeCoreCatalogs();
console.log("i18n-check: core/*/i18n/<locale>.json, merged into the folder below");
let failed = check(coreCatalogDir, ["app", "core", "lib"]) !== 0;
rmSync(coreCatalogDir, { recursive: true, force: true });

// A plugin keeps its catalogs in src/i18n and is checked against its src.
for (const entry of readdirSync("plugins", { withFileTypes: true })) {
  if (!entry.isDirectory()) continue;
  const catalogDir = `plugins/${entry.name}/src/i18n`;
  if (!existsSync(catalogDir)) continue;
  failed = check(catalogDir, [`plugins/${entry.name}/src`]) !== 0 || failed;
}

process.exit(failed ? 1 : 0);
