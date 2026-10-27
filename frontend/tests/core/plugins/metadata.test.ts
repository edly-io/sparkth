import { describe, it, expect } from "vitest";

import { displayNameOf } from "@/core/plugins/metadata";
import type { UserPluginState } from "@/core/plugins/types";

function state(overrides: Partial<UserPluginState> & { plugin_name: string }): UserPluginState {
  return {
    enabled: true,
    config: {},
    config_schema: {},
    is_core: true,
    display: null,
    sidebar: null,
    has_frontend: false,
    secrets_set: [],
    ...overrides,
  };
}

describe("displayNameOf", () => {
  it("uses the backend-declared display name", () => {
    const plugin = state({
      plugin_name: "chat",
      display: {
        display_name: "Create Course",
        description: "Build courses with AI",
        icon: "plus",
      },
    });
    expect(displayNameOf(plugin)).toBe("Create Course");
  });

  it("falls back to the plugin name when no display info is declared", () => {
    expect(displayNameOf(state({ plugin_name: "canvas" }))).toBe("canvas");
  });
});
