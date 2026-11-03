import { describe, it, expect } from "vitest";

import { pluginPath } from "@/core/plugins/routes";

describe("pluginPath", () => {
  it("returns the dashboard page core serves for the plugin", () => {
    expect(pluginPath("compose")).toBe("/dashboard/compose");
  });

  it("keeps a hyphenated plugin name as it is", () => {
    expect(pluginPath("google-drive")).toBe("/dashboard/google-drive");
  });
});
