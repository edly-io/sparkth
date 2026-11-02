import { describe, it, expect } from "vitest";

import "@/app/plugins";
import { resolvePluginIcon } from "@/core/components/ui/icons";
import { getAllPlugins } from "@/core/plugins/registry";
import { FRONTEND_PLUGIN_NAMES, PLUGIN_ICON_NAMES } from "@/lib/plugins/generated";

describe("frontend plugin registry vs backend declarations", () => {
  it("registers a PluginDefinition for exactly the backend-declared frontend plugins", () => {
    const registered = getAllPlugins()
      .map((plugin) => plugin.name)
      .sort();
    expect(registered).toEqual([...FRONTEND_PLUGIN_NAMES].sort());
  });

  it("resolves every icon the backend plugins declare", () => {
    const unresolved = Object.entries(PLUGIN_ICON_NAMES).flatMap(([plugin, names]) =>
      names.filter((name) => !resolvePluginIcon(plugin, name)).map((name) => `${plugin}: ${name}`),
    );
    expect(unresolved).toEqual([]);
  });
});
