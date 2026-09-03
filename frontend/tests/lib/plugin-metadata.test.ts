import { describe, it, expect } from "vitest";

import { displayNameOf, sidebarItemsFrom } from "@/lib/plugins/metadata";
import type { UserPluginState } from "@/lib/plugins/types";

function state(overrides: Partial<UserPluginState> & { plugin_name: string }): UserPluginState {
  return {
    enabled: true,
    config: {},
    config_schema: {},
    is_core: true,
    display: null,
    sidebar: null,
    has_frontend: false,
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

describe("sidebarItemsFrom", () => {
  const chat = state({
    plugin_name: "chat",
    display: { display_name: "Create Course", description: "Build courses with AI", icon: "plus" },
    sidebar: { label: "Create Course", icon: "plus", order: 1 },
    has_frontend: true,
  });
  const slack = state({
    plugin_name: "slack",
    display: {
      display_name: "Slack TA Bot",
      description: "Answer questions in Slack",
      icon: "slack",
    },
    sidebar: { label: "Slack TA Bot", icon: "slack", order: 3 },
    has_frontend: true,
  });
  const drive = state({
    plugin_name: "google-drive",
    display: { display_name: "Google Drive", description: "Imported files", icon: null },
    has_frontend: true,
  });
  const canvas = state({ plugin_name: "canvas" });
  const backendOnly = state({
    plugin_name: "backend-only",
    sidebar: { label: "Backend Only", icon: null, order: 2 },
    has_frontend: false,
  });

  it("includes only enabled frontend plugins that declared a sidebar entry, sorted by order", () => {
    const items = sidebarItemsFrom([slack, canvas, drive, chat]);
    expect(items.map((item) => item.name)).toEqual(["chat", "slack"]);
  });

  it("excludes plugins without a frontend registration even if they declare a sidebar entry", () => {
    expect(sidebarItemsFrom([backendOnly, chat]).map((item) => item.name)).toEqual(["chat"]);
  });

  it("carries the declared label, icon name, and description", () => {
    const [item] = sidebarItemsFrom([chat]);
    expect(item).toEqual({
      name: "chat",
      label: "Create Course",
      icon: "plus",
      description: "Build courses with AI",
    });
  });

  it("excludes disabled plugins", () => {
    const disabled = { ...chat, enabled: false };
    expect(sidebarItemsFrom([disabled, slack])).toHaveLength(1);
  });
});
