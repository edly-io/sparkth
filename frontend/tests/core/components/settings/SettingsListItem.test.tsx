import { describe, it, expect, vi } from "vitest";
import { fireEvent, render, screen } from "@testing-library/react";

import { SettingsListItem } from "@/core/components/settings/SettingsListItem";
import type { UserPluginState } from "@/core/plugins/types";

const noop = async () => {};

function renderItem(plugin: UserPluginState, onConfigure?: () => void) {
  return render(
    <SettingsListItem plugin={plugin} onEnable={noop} onDisable={noop} onConfigure={onConfigure} />,
  );
}

const CANVAS: UserPluginState = {
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
};

describe("SettingsListItem", () => {
  it("renders the backend-declared display name and description", () => {
    renderItem(CANVAS);

    expect(screen.getByRole("heading", { name: "Canvas" })).toBeDefined();
    expect(screen.getByText("Canvas LMS integration with course authoring tools")).toBeDefined();
  });

  it("falls back to the plugin name when no display info is declared", () => {
    renderItem({ ...CANVAS, plugin_name: "mystery", enabled: false, display: null });

    expect(screen.getByRole("heading", { name: "mystery" })).toBeDefined();
  });

  it("offers no configure button when the plugin has no config modal", () => {
    renderItem(CANVAS);

    expect(screen.queryByTitle("Configure plugin")).toBeNull();
  });

  it("opens the config modal when its configure button is pressed", () => {
    const onConfigure = vi.fn();
    renderItem(CANVAS, onConfigure);

    fireEvent.click(screen.getByTitle("Configure plugin"));

    expect(onConfigure).toHaveBeenCalledOnce();
  });
});
