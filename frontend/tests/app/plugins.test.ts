import { describe, it, expect } from "vitest";

import "@/app/plugins";
import { getAllPlugins } from "@/core/plugins/registry";
import { FRONTEND_PLUGIN_NAMES } from "@/core/plugins/generated";

describe("frontend plugin registry vs backend declarations", () => {
  it("registers a PluginDefinition for exactly the backend-declared frontend plugins", () => {
    const registered = getAllPlugins()
      .map((plugin) => plugin.name)
      .sort();
    expect(registered).toEqual([...FRONTEND_PLUGIN_NAMES].sort());
  });
});
