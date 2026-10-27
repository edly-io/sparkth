import { describe, it, expect, vi, beforeEach } from "vitest";
import { screen } from "@testing-library/react";

const ctx = vi.hoisted(() => ({ value: {} as Record<string, unknown> }));
vi.mock("@/core/plugins/context", () => ({ usePluginContext: () => ctx.value }));

import PluginsSettings from "@/app/dashboard/settings/page";
import { renderWithIntl } from "@/tests/intl-test-utils";

const base = {
  userPlugins: [],
  loading: false,
  error: null,
  refreshPlugins: vi.fn(),
  enablePlugin: vi.fn(),
  disablePlugin: vi.fn(),
  updatePluginConfig: vi.fn(),
};

beforeEach(() => {
  ctx.value = { ...base };
});

describe("Settings page", () => {
  it("shows the page heading", () => {
    renderWithIntl(<PluginsSettings />);
    expect(screen.getByRole("heading", { name: "Settings" })).toBeDefined();
  });

  it("shows a load failure in an alert under the heading", () => {
    ctx.value = { ...base, error: "boom" };
    renderWithIntl(<PluginsSettings />);
    expect(screen.getByRole("heading", { name: "Settings" })).toBeDefined();
    expect(screen.getByRole("alert").textContent).toContain("Failed to load plugins: boom");
  });

  it("says when there are no plugins", () => {
    renderWithIntl(<PluginsSettings />);
    expect(screen.getByText("No plugins found")).toBeDefined();
  });
});
