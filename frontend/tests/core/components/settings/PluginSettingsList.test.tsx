import { afterEach, describe, it, expect, vi } from "vitest";
import { fireEvent, screen } from "@testing-library/react";

import { PluginSettingsList } from "@/core/components/settings/PluginSettingsList";
import type { UserPluginState } from "@/core/plugins/types";
import {
  SETTINGS_ITEMS,
  type ConfigModalProps,
  type SettingsListItemProps,
} from "@/lib/settings/slots";
import { renderWithIntl } from "@/tests/intl-test-utils";

const context = vi.hoisted(() => ({
  userPlugins: [] as UserPluginState[],
  enablePlugin: vi.fn(async () => {}),
  disablePlugin: vi.fn(async () => {}),
  updatePluginConfig: vi.fn(async () => {}),
  refreshPlugins: vi.fn(async () => {}),
}));

vi.mock("@/core/plugins/context", () => ({
  usePluginContext: () => context,
}));

function state(pluginName: string): UserPluginState {
  return {
    plugin_name: pluginName,
    enabled: true,
    config: {},
    config_schema: {},
    is_core: true,
    display: null,
    sidebar: null,
    has_frontend: false,
    secrets_set: [],
  };
}

// A plugin whose backend config declares one field.
function configurable(pluginName: string): UserPluginState {
  return {
    ...state(pluginName),
    config_schema: { type: "object", properties: { limit: { title: "Limit", type: "integer" } } },
  };
}

function ExampleRow({ plugin, onEnable, onConfigure }: SettingsListItemProps) {
  return (
    <div>
      <p>Row for {plugin.plugin_name}</p>
      <button onClick={onEnable}>Enable</button>
      {onConfigure ? <button onClick={onConfigure}>Configure</button> : <p>No configure</p>}
    </div>
  );
}

function ExampleModal({ plugin, open }: ConfigModalProps) {
  return open ? <p>Modal for {plugin.plugin_name}</p> : null;
}

describe("PluginSettingsList", () => {
  afterEach(() => {
    SETTINGS_ITEMS.clear();
    context.userPlugins = [];
    vi.clearAllMocks();
  });

  it("renders the row each plugin set, for the plugins the API returned", () => {
    SETTINGS_ITEMS.set("example", { listItem: ExampleRow });
    context.userPlugins = [state("example")];

    renderWithIntl(<PluginSettingsList />);

    expect(screen.getByText("Row for example")).toBeDefined();
  });

  it("lists the rows in plugin-name order", () => {
    SETTINGS_ITEMS.set("zeta", { listItem: ExampleRow });
    SETTINGS_ITEMS.set("alpha", { listItem: ExampleRow });
    context.userPlugins = [state("zeta"), state("alpha")];

    renderWithIntl(<PluginSettingsList />);

    const rows = screen.getAllByText((text) => text.startsWith("Row for "));
    expect(rows.map((row) => row.textContent)).toEqual(["Row for alpha", "Row for zeta"]);
  });

  it("leaves out a row whose plugin the API did not return", () => {
    SETTINGS_ITEMS.set("missing", { listItem: ExampleRow });

    renderWithIntl(<PluginSettingsList />);

    expect(screen.queryByText("Row for missing")).toBeNull();
    expect(screen.getByText("No plugins found")).toBeDefined();
  });

  it("turns on the plugin whose row asks for it", () => {
    SETTINGS_ITEMS.set("example", { listItem: ExampleRow });
    context.userPlugins = [state("example")];

    renderWithIntl(<PluginSettingsList />);
    fireEvent.click(screen.getByRole("button", { name: "Enable" }));

    expect(context.enablePlugin).toHaveBeenCalledWith("example");
  });

  it("gives a row no configure action when its plugin supplied no config modal", () => {
    SETTINGS_ITEMS.set("example", { listItem: ExampleRow });
    context.userPlugins = [state("example")];

    renderWithIntl(<PluginSettingsList />);

    expect(screen.getByText("No configure")).toBeDefined();
  });

  it("gives a row no configure action when its plugin's backend config declares no fields", () => {
    SETTINGS_ITEMS.set("example", {
      listItem: ExampleRow,
      loadConfigModal: async () => ({ default: ExampleModal }),
    });
    context.userPlugins = [state("example")];

    renderWithIntl(<PluginSettingsList />);

    expect(screen.getByText("No configure")).toBeDefined();
  });

  it("opens the config modal a plugin supplied from its row", async () => {
    SETTINGS_ITEMS.set("example", {
      listItem: ExampleRow,
      loadConfigModal: async () => ({ default: ExampleModal }),
    });
    context.userPlugins = [configurable("example")];

    renderWithIntl(<PluginSettingsList />);
    fireEvent.click(screen.getByRole("button", { name: "Configure" }));

    expect(await screen.findByText("Modal for example")).toBeDefined();
  });

  it("keeps the page and shows an error when a plugin's config modal fails to load", async () => {
    const consoleError = vi.spyOn(console, "error").mockImplementation(() => {});
    SETTINGS_ITEMS.set("example", {
      listItem: ExampleRow,
      loadConfigModal: () => Promise.reject(new Error("chunk failed")),
    });
    context.userPlugins = [configurable("example")];

    renderWithIntl(<PluginSettingsList />);
    fireEvent.click(screen.getByRole("button", { name: "Configure" }));

    expect(await screen.findByText("chunk failed")).toBeDefined();
    expect(screen.getByText("Row for example")).toBeDefined();
    consoleError.mockRestore();
  });
});
