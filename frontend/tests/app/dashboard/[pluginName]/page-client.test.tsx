import { screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, it, expect, vi } from "vitest";

import PluginPageClient from "@/app/dashboard/[pluginName]/page-client";
import coreEn from "@/core/i18n/en.json";
import coreEs from "@/core/i18n/es.json";
import { registerPlugin, unregisterPlugin } from "@/core/plugins/registry";
import type { PluginState } from "@/core/plugins/types";
import { renderWithIntl } from "@/tests/intl";

// The mocks below read these directly, so a test sets them before rendering.
let params: { pluginName?: string } = {};
let auth = { isAuthenticated: true, loading: false };
let plugins: PluginState[] = [];

vi.mock("next/navigation", () => ({
  useParams: () => params,
  redirect: vi.fn(),
}));

vi.mock("@/core/auth/hooks", () => ({
  useAuth: () => auth,
}));

vi.mock("@/core/plugins/context", () => ({
  usePlugin: () => ({ isEnabled: false }),
  usePluginContext: () => ({ plugins, loading: false }),
}));

beforeEach(() => {
  params = {};
  auth = { isAuthenticated: true, loading: false };
  plugins = [];
});

describe("PluginPageClient — a URL that names no registered plugin", () => {
  it("shows the not-found panel naming the plugin", () => {
    params = { pluginName: "nosuchplugin" };

    renderWithIntl(<PluginPageClient />, coreEn);

    const panel = screen.getByRole("alert");
    expect(panel).toHaveTextContent(coreEn.pluginNotFound.title);
    expect(panel).toHaveTextContent(
      coreEn.pluginNotFound.message.replace("{name}", "nosuchplugin"),
    );
    expect(screen.getByRole("link", { name: coreEn.dashboardLink.back })).toHaveAttribute(
      "href",
      "/dashboard",
    );
  });

  it("shows the not-found panel without naming a plugin when the URL names none", () => {
    renderWithIntl(<PluginPageClient />, coreEn);

    const panel = screen.getByRole("alert");
    expect(panel).toHaveTextContent(coreEn.pluginNotFound.title);
    expect(panel).not.toHaveTextContent("No plugin is registered");
  });
});

describe("PluginPageClient — while the user is being authenticated", () => {
  it("says so", () => {
    auth = { isAuthenticated: false, loading: true };

    renderWithIntl(<PluginPageClient />, coreEn);

    expect(screen.getByText(coreEn.pluginPage.authenticating)).toBeInTheDocument();
  });

  it("says so in the active language", () => {
    auth = { isAuthenticated: false, loading: true };

    renderWithIntl(<PluginPageClient />, coreEs);

    expect(screen.getByText(coreEs.pluginPage.authenticating)).toBeInTheDocument();
  });
});

describe("PluginPageClient — a registered plugin the user has not enabled", () => {
  beforeEach(() => {
    params = { pluginName: "exampleplugin" };
    registerPlugin({
      name: "exampleplugin",
      loadComponent: () => Promise.resolve({ default: () => null }),
    });
  });

  afterEach(() => {
    unregisterPlugin("exampleplugin");
  });

  it("says the plugin is not enabled and offers settings and the dashboard", () => {
    renderWithIntl(<PluginPageClient />, coreEn);

    expect(
      screen.getByRole("heading", { name: coreEn.pluginPage.notEnabledTitle }),
    ).toBeInTheDocument();
    expect(
      screen.getByText(coreEn.pluginPage.notEnabledMessage.replace("{name}", "exampleplugin")),
    ).toBeInTheDocument();
    expect(screen.getByRole("link", { name: coreEn.pluginPage.enableInSettings })).toHaveAttribute(
      "href",
      "/dashboard/settings",
    );
    expect(screen.getByRole("link", { name: coreEn.pluginPage.goBack })).toHaveAttribute(
      "href",
      "/dashboard",
    );
  });

  it("says so in the active language", () => {
    renderWithIntl(<PluginPageClient />, coreEs);

    expect(
      screen.getByRole("heading", { name: coreEs.pluginPage.notEnabledTitle }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("link", { name: coreEs.pluginPage.enableInSettings }),
    ).toBeInTheDocument();
  });
});

describe("PluginPageClient — a plugin in the list", () => {
  const EXAMPLE: PluginState = {
    plugin_name: "exampleplugin",
    enabled: true,
    system_enabled: true,
    config: {},
    config_schema: {},
    is_core: false,
    display: { display_name: "Example Plugin", description: "", icon: null },
    sidebar: null,
    has_frontend: true,
    secrets_set: [],
    masked_secrets: {},
  };

  beforeEach(() => {
    params = { pluginName: "exampleplugin" };
    registerPlugin({
      name: "exampleplugin",
      loadComponent: () => Promise.resolve({ default: () => null }),
    });
  });

  afterEach(() => {
    unregisterPlugin("exampleplugin");
  });

  it("says an administrator switched it off, with no link to settings", () => {
    plugins = [{ ...EXAMPLE, system_enabled: false }];

    renderWithIntl(<PluginPageClient />, coreEn);

    expect(
      screen.getByRole("heading", { name: coreEn.pluginPage.systemDisabledTitle }),
    ).toBeInTheDocument();
    expect(
      screen.getByText(coreEn.pluginPage.systemDisabledMessage.replace("{name}", "Example Plugin")),
    ).toBeInTheDocument();
    expect(screen.getByRole("link", { name: coreEn.pluginPage.goBack })).toHaveAttribute(
      "href",
      "/dashboard",
    );
    expect(
      screen.queryByRole("link", { name: coreEn.pluginPage.enableInSettings }),
    ).not.toBeInTheDocument();
  });

  it("still sends a plugin the user turned off to settings", () => {
    plugins = [{ ...EXAMPLE, enabled: false }];

    renderWithIntl(<PluginPageClient />, coreEn);

    expect(
      screen.getByText(coreEn.pluginPage.notEnabledMessage.replace("{name}", "Example Plugin")),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("link", { name: coreEn.pluginPage.enableInSettings }),
    ).toBeInTheDocument();
    expect(screen.getByRole("link", { name: coreEn.pluginPage.goBack })).toBeInTheDocument();
  });

  it("says so in the active language when an administrator switched it off", () => {
    plugins = [{ ...EXAMPLE, system_enabled: false }];

    renderWithIntl(<PluginPageClient />, coreEs);

    expect(
      screen.getByRole("heading", { name: coreEs.pluginPage.systemDisabledTitle }),
    ).toBeInTheDocument();
  });
});
