import { spawnSync } from "node:child_process";
import {
  copyFileSync,
  mkdirSync,
  mkdtempSync,
  readdirSync,
  readFileSync,
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
let root: string;

/** Lints a file holding `importPath` at `filePath`, under the real config; returns the errors. */
function lintImport(filePath: string, importPath: string): string {
  const file = path.join(root, filePath);
  mkdirSync(path.dirname(file), { recursive: true });
  writeFileSync(file, `import { x } from "${importPath}";\nexport { x };\n`);
  const result = spawnSync(oxlint, ["-c", ".oxlintrc.json", "-f", "unix", filePath], {
    cwd: root,
    encoding: "utf8",
  });
  return result.stdout
    .split("\n")
    .filter((line) => line.includes("no-restricted-imports"))
    .join("\n");
}

beforeAll(() => {
  root = mkdtempSync(path.join(tmpdir(), "sparkth-oxlint-"));
  copyFileSync(path.join(frontend, ".oxlintrc.json"), path.join(root, ".oxlintrc.json"));
});

afterAll(() => {
  rmSync(root, { recursive: true, force: true });
});

describe("frontend import boundaries", () => {
  it.each([
    ["core/feature/x.ts", "@/plugins/pxc/src/client"],
    ["lib/area/x.ts", "@/plugins/compose/lib"],
  ])("stops %s importing a plugin (%s)", (file, importPath) => {
    expect(lintImport(file, importPath)).toContain(importPath);
  });

  it.each(plugins)("keeps %s to @/lib for core code", (plugin) => {
    for (const importPath of ["@/core/auth/tokens", "@/app/plugins"]) {
      expect(lintImport(`plugins/${plugin}/src/x.ts`, importPath)).toContain(importPath);
    }
  });

  it.each(plugins)("stops %s importing another plugin's internals", (plugin) => {
    const other = plugin === "pxc" ? "compose" : "pxc";
    const importPath = `@/plugins/${other}/src/client`;

    expect(lintImport(`plugins/${plugin}/src/x.ts`, importPath)).toContain(importPath);
  });

  it.each([
    ["plugins/compose/src/x.ts", "@/plugins/pxc/lib"],
    ["plugins/compose/src/x.ts", "@/plugins/compose/src/client"],
    ["plugins/compose/src/x.ts", "@/lib/api"],
    ["app/x.ts", "@/plugins/compose/src"],
  ])("lets %s import %s", (file, importPath) => {
    expect(lintImport(file, importPath)).toBe("");
  });

  it("gives every plugin its own override, so it cannot import other plugins' internals", () => {
    const config = JSON.parse(readFileSync(path.join(frontend, ".oxlintrc.json"), "utf8")) as {
      overrides: { files: string[] }[];
    };
    const covered = new Set(config.overrides.flatMap((override) => override.files));

    expect(plugins.filter((plugin) => !covered.has(`plugins/${plugin}/**`))).toEqual([]);
  });
});
