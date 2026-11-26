import { describe, it, expect, vi } from "vitest";
import { screen } from "@testing-library/react";

const ctx = vi.hoisted(() => ({ value: {} as Record<string, unknown> }));
vi.mock("@/core/plugins/context", () => ({ usePluginContext: () => ctx.value }));

import DashboardPage from "@/app/dashboard/page";
import type { PluginState } from "@/core/plugins/types";
import { renderWithIntl } from "@/tests/intl";

function state(name: string, overrides: Partial<PluginState> = {}): PluginState {
  return {
    plugin_name: name,
    enabled: true,
    system_enabled: true,
    config: {},
    config_schema: {},
    is_core: true,
    display: { display_name: `${name} title`, description: `${name} description`, icon: null },
    sidebar: null,
    has_frontend: true,
    secrets_set: [],
    masked_secrets: {},
    ...overrides,
  };
}

describe("Dashboard page", () => {
  it("shows the plugins that are usable and leaves out one switched off system-wide", () => {
    ctx.value = {
      loading: false,
      plugins: [state("canvas"), state("compose", { system_enabled: false })],
    };

    renderWithIntl(<DashboardPage />);

    expect(screen.getByRole("heading", { name: "canvas title" })).toBeDefined();
    expect(screen.queryByRole("heading", { name: "compose title" })).toBeNull();
  });
});
