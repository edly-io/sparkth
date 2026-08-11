import { describe, it, expect } from "vitest";

// Importing the barrel registers the built-in frontend plugin definitions.
import { getAllPlugins } from "@/lib/plugins";
import { FRONTEND_PLUGIN_NAMES } from "@/lib/plugins/generated";

describe("frontend plugin registry vs backend declarations", () => {
  it("registers a PluginDefinition for exactly the backend-declared frontend plugins", () => {
    const registered = getAllPlugins()
      .map((plugin) => plugin.name)
      .sort();
    expect(registered).toEqual([...FRONTEND_PLUGIN_NAMES].sort());
  });
});
