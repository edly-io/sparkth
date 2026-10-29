import { describe, it, expect } from "vitest";

import { sidebarItemsFrom } from "@/core/components/layout/sidebarItems";
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
    masked_secrets: {},
    ...overrides,
  };
}

describe("sidebarItemsFrom", () => {
  const chat = state({
    plugin_name: "compose",
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
    expect(items.map((item) => item.name)).toEqual(["compose", "slack"]);
  });

  it("excludes plugins without a frontend registration even if they declare a sidebar entry", () => {
    expect(sidebarItemsFrom([backendOnly, chat]).map((item) => item.name)).toEqual(["compose"]);
  });

  it("carries the declared label, icon name, and description", () => {
    const [item] = sidebarItemsFrom([chat]);
    expect(item).toEqual({
      name: "compose",
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
