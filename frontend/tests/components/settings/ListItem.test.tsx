import { describe, it, expect, vi } from "vitest";
import { screen } from "@testing-library/react";

import { renderWithIntl } from "@/tests/intl-test-utils";

import PluginListItem from "@/components/settings/ListItem";
import type { UserPluginState } from "@/core/plugins/types";

const noop = async () => {};

function renderItem(plugin: UserPluginState) {
  return renderWithIntl(
    <PluginListItem
      plugin={plugin}
      onEnable={noop}
      onDisable={noop}
      onConfigChange={noop}
      onRefresh={vi.fn()}
    />,
  );
}

describe("PluginListItem", () => {
  it("renders the backend-declared display name and description", () => {
    renderItem({
      plugin_name: "canvas",
      enabled: true,
      config: {},
      config_schema: {},
      is_core: true,
      display: {
        display_name: "Canvas",
        description: "Canvas LMS integration with course authoring tools",
        icon: null,
      },
      sidebar: null,
      has_frontend: false,
      secrets_set: [],
    });

    expect(screen.getByRole("heading", { name: "Canvas" })).toBeDefined();
    expect(screen.getByText("Canvas LMS integration with course authoring tools")).toBeDefined();
  });

  it("falls back to the plugin name when no display info is declared", () => {
    renderItem({
      plugin_name: "mystery",
      enabled: false,
      config: {},
      config_schema: {},
      is_core: true,
      display: null,
      sidebar: null,
      has_frontend: false,
      secrets_set: [],
    });

    expect(screen.getByRole("heading", { name: "mystery" })).toBeDefined();
  });

  it("drops the hardcoded Sparkth line and labels its controls", () => {
    renderItem({
      plugin_name: "canvas",
      enabled: true,
      config: {},
      config_schema: {},
      is_core: true,
      display: { display_name: "Canvas", description: "d", icon: null },
      sidebar: null,
      has_frontend: false,
      secrets_set: [],
    });

    expect(screen.queryByText("Sparkth")).toBeNull();
    expect(screen.getByRole("switch", { name: "Turn Canvas on or off" })).toBeDefined();
    expect(screen.getByRole("button", { name: "Configure Canvas" })).toBeDefined();
  });
  it.each([
    [true, "Enabled"],
    [false, "Disabled"],
  ])("says whether the plugin is enabled (%s)", (enabled, label) => {
    renderItem({
      plugin_name: "canvas",
      enabled,
      config: {},
      config_schema: {},
      is_core: true,
      display: { display_name: "Canvas", description: "d", icon: null },
      sidebar: null,
      has_frontend: false,
      secrets_set: [],
    });

    expect(screen.getByText(label)).toBeDefined();
  });
});
