import { readdirSync, readFileSync } from "node:fs";
import path from "node:path";
import { describe, it, expect, vi } from "vitest";

describe("plugin registration", () => {
  it("registers every plugin in the PLUGINS slot", async () => {
    vi.resetModules();
    const { PLUGINS: freshPlugins } = await import("@/lib/plugins/slots");
    freshPlugins.set("exampleplugin", {
      name: "exampleplugin",
      loadComponent: () => Promise.resolve({ default: () => null }),
    });

    await import("@/app/plugins");
    const { getPlugin } = await import("@/core/plugins/registry");

    expect(getPlugin("exampleplugin")?.name).toBe("exampleplugin");
  });

  it("loads the plugins without naming any", () => {
    const frontend = path.resolve(__dirname, "../..");
    const folders = readdirSync(path.join(frontend, "plugins"), { withFileTypes: true })
      .filter((entry) => entry.isDirectory())
      .map((entry) => entry.name);
    const loaders = ["app/plugins.ts", "app/pluginModules.ts"].map((file) =>
      readFileSync(path.join(frontend, file), "utf8"),
    );

    const named = folders.filter((folder) =>
      loaders.some((source) => source.includes(`@/plugins/${folder}`)),
    );
    expect(named).toEqual([]);
  });
});
