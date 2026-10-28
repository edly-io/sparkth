import { describe, it, expect, vi } from "vitest";
import { fireEvent, screen } from "@testing-library/react";

import { SettingsListItem } from "@/core/components/settings/SettingsListItem";
import type { UserPluginState } from "@/core/plugins/types";
import { renderWithIntl } from "@/tests/intl-test-utils";

const noop = async () => {};

function renderItem(plugin: UserPluginState, onConfigure?: () => void) {
  return renderWithIntl(
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
  secrets_set: [],
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

  it("drops the hardcoded Sparkth line and labels its switch", () => {
    renderItem(CANVAS);

    expect(screen.queryByText("Sparkth")).toBeNull();
    expect(screen.getByRole("switch", { name: "Turn Canvas on or off" })).toBeDefined();
  });

  it.each([
    [true, "Enabled"],
    [false, "Disabled"],
  ])("says whether the plugin is enabled (%s)", (enabled, label) => {
    renderItem({ ...CANVAS, enabled });

    expect(screen.getByText(label)).toBeDefined();
  });

  it("offers no configure button when the plugin has no config modal", () => {
    renderItem(CANVAS);

    expect(screen.queryByRole("button", { name: "Configure Canvas" })).toBeNull();
  });

  it("opens the config modal when its configure button is pressed", () => {
    const onConfigure = vi.fn();
    renderItem(CANVAS, onConfigure);

    fireEvent.click(screen.getByRole("button", { name: "Configure Canvas" }));

    expect(onConfigure).toHaveBeenCalledOnce();
  });
});
