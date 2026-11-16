import { spawnSync } from "node:child_process";
import {
  copyFileSync,
  existsSync,
  mkdirSync,
  mkdtempSync,
  readdirSync,
  rmSync,
  writeFileSync,
} from "node:fs";
import { tmpdir } from "node:os";
import path from "node:path";
import { afterAll, beforeAll, describe, expect, it } from "vitest";

const frontend = path.resolve(__dirname, "..");
const oxlint = path.join(frontend, "node_modules/.bin/oxlint");
const plugins = readdirSync(path.join(frontend, "plugins"), { withFileTypes: true })
  .filter((entry) => entry.isDirectory())
  .map((entry) => entry.name);
const CORE_IMPORTS_PLUGIN =
  "Core and lib never import a plugin; a plugin contributes to them through a slot.";
const PLUGIN_IMPORTS_CORE = "Plugins import core code through @/lib, never from @/core or @/app.";
const PLUGIN_IMPORTS_PLUGIN = "A plugin imports another plugin only through that plugin's lib/.";
let root: string;

/** Lints a file holding `importPath` at `filePath`, under the real configs; returns the messages of its errors. */
function lintImport(filePath: string, importPath: string): string[] {
  const file = path.join(root, filePath);
  mkdirSync(path.dirname(file), { recursive: true });
  writeFileSync(file, `import { x } from "${importPath}";\nexport { x };\n`);
  const result = spawnSync(oxlint, ["-f", "json", filePath], { cwd: root, encoding: "utf8" });
  const { diagnostics } = JSON.parse(result.stdout) as {
    diagnostics: { code: string; help: string }[];
  };
  return [
    ...new Set(
      diagnostics
        .filter((diagnostic) => diagnostic.code === "eslint(no-restricted-imports)")
        .map((diagnostic) => diagnostic.help),
    ),
  ];
}

/** Another plugin than `plugin`, so the tests depend on no plugin by name. */
function otherThan(plugin: string): string {
  return plugins.find((name) => name !== plugin)!;
}

/** Whether `plugin` has its own lint config. */
function hasLintConfig(plugin: string): boolean {
  return existsSync(path.join(frontend, "plugins", plugin, ".oxlintrc.json"));
}

beforeAll(() => {
  root = mkdtempSync(path.join(tmpdir(), "sparkth-oxlint-"));
  copyFileSync(path.join(frontend, ".oxlintrc.json"), path.join(root, ".oxlintrc.json"));
  // A plugin without a config is reported by the last test, not left to fail the setup.
  for (const plugin of plugins.filter(hasLintConfig)) {
    mkdirSync(path.join(root, "plugins", plugin), { recursive: true });
    copyFileSync(
      path.join(frontend, "plugins", plugin, ".oxlintrc.json"),
      path.join(root, "plugins", plugin, ".oxlintrc.json"),
    );
  }
});

afterAll(() => {
  rmSync(root, { recursive: true, force: true });
});

describe("frontend import boundaries", () => {
  it.each(["core/feature/x.ts", "lib/area/x.ts"])("stops %s importing a plugin", (file) => {
    expect(lintImport(file, `@/plugins/${plugins[0]}/lib`)).toEqual([CORE_IMPORTS_PLUGIN]);
  });

  it.each(plugins)("keeps %s to @/lib for core code", (plugin) => {
    for (const importPath of ["@/core/auth/tokens", "@/app/plugins"]) {
      expect(lintImport(`plugins/${plugin}/src/x.ts`, importPath)).toEqual([PLUGIN_IMPORTS_CORE]);
    }
  });

  it.each(plugins)("stops %s importing another plugin's internals", (plugin) => {
    const importPath = `@/plugins/${otherThan(plugin)}/src/client`;

    expect(lintImport(`plugins/${plugin}/src/x.ts`, importPath)).toEqual([PLUGIN_IMPORTS_PLUGIN]);
  });

  it.each(plugins)("lets %s import its own files, another plugin's lib/ and @/lib", (plugin) => {
    for (const importPath of [
      `@/plugins/${plugin}/src/client`,
      `@/plugins/${otherThan(plugin)}/lib`,
      "@/lib/api",
    ]) {
      expect(lintImport(`plugins/${plugin}/src/x.ts`, importPath)).toEqual([]);
    }
  });

  it("lets app/ import any plugin's files", () => {
    expect(lintImport("app/x.ts", `@/plugins/${plugins[0]}/src`)).toEqual([]);
  });

  it("gives every plugin its own lint config", () => {
    expect(plugins.filter((plugin) => !hasLintConfig(plugin))).toEqual([]);
  });
});
