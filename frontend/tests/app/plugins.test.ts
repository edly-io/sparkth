import { describe, it, expect } from "vitest";

import "@/app/plugins";
import { resolvePluginIcon } from "@/core/components/ui/icons";
import { getAllPlugins } from "@/core/plugins/registry";
import { FRONTEND_PLUGIN_NAMES } from "@/lib/plugins/generated";
import { SETTINGS_ITEMS } from "@/lib/settings/slots";

describe("frontend plugin registry vs backend declarations", () => {
  it("registers a PluginDefinition for exactly the backend-declared frontend plugins", () => {
    const registered = getAllPlugins()
      .map((plugin) => plugin.name)
      .sort();
    expect(registered).toEqual([...FRONTEND_PLUGIN_NAMES].sort());
  });

  it("resolves every icon the backend plugins declare", () => {
    expect(resolvePluginIcon("plus")).toBeDefined();
    expect(resolvePluginIcon("blocks")).toBeDefined();
    expect(resolvePluginIcon("slack")).toBeDefined();
  });

  it("sets a settings row for every plugin", () => {
    expect([...SETTINGS_ITEMS.keys()]).toEqual(
      expect.arrayContaining(["canvas", "chat", "google-drive", "moodle", "pxc", "slack"]),
    );
  });
});
