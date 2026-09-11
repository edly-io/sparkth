import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";

import PluginListItem from "@/components/settings/ListItem";
import type { UserPluginState } from "@/lib/plugins";

const noop = async () => {};

function renderItem(plugin: UserPluginState) {
  return render(
    <PluginListItem
      plugin={plugin}
      isLast
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
    });

    expect(screen.getByRole("heading", { name: "mystery" })).toBeDefined();
  });
});
