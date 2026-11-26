import { screen } from "@testing-library/react";
import { beforeEach, describe, it, expect, vi } from "vitest";

import PluginPageClient from "@/app/dashboard/[pluginName]/page-client";
import coreEn from "@/core/i18n/en.json";
import coreEs from "@/core/i18n/es.json";
import { renderWithIntl } from "@/tests/intl";

// The mocks below read these directly, so a test sets them before rendering.
let params: { pluginName?: string } = {};
let auth = { isAuthenticated: true, loading: false };

vi.mock("next/navigation", () => ({
  useParams: () => params,
  redirect: vi.fn(),
}));

vi.mock("@/core/auth/hooks", () => ({
  useAuth: () => auth,
}));

vi.mock("@/core/plugins/context", () => ({
  usePlugin: () => ({ isEnabled: false }),
  usePluginContext: () => ({ plugins: [], loading: false }),
}));

beforeEach(() => {
  params = {};
  auth = { isAuthenticated: true, loading: false };
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

describe("PluginPageClient — a plugin the user has not enabled", () => {
  beforeEach(() => {
    params = { pluginName: "exampleplugin" };
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
