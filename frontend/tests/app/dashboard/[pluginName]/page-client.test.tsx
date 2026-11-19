import { screen } from "@testing-library/react";
import { beforeEach, describe, it, expect, vi } from "vitest";

import PluginPageClient from "@/app/dashboard/[pluginName]/page-client";
import coreEn from "@/core/i18n/en.json";
import { renderWithIntl } from "@/tests/intl";

// useParams is mocked to read this directly, so a test sets it before rendering.
let params: { pluginName?: string } = {};

vi.mock("next/navigation", () => ({
  useParams: () => params,
  redirect: vi.fn(),
}));

vi.mock("@/core/auth/hooks", () => ({
  useAuth: () => ({ isAuthenticated: true, loading: false }),
}));

vi.mock("@/core/plugins/context", () => ({
  usePlugin: () => ({ isEnabled: false }),
  usePluginContext: () => ({ userPlugins: [], loading: false }),
}));

describe("PluginPageClient — a URL that names no registered plugin", () => {
  beforeEach(() => {
    params = {};
  });

  it("shows the not-found panel naming the plugin", () => {
    params = { pluginName: "nosuchplugin" };

    renderWithIntl(<PluginPageClient />, coreEn);

    expect(screen.getByRole("alert")).toHaveTextContent(coreEn.pluginNotFound.title);
    expect(screen.getByText(/nosuchplugin/)).toBeInTheDocument();
    expect(screen.getByRole("link", { name: coreEn.pluginNotFound.back })).toHaveAttribute(
      "href",
      "/dashboard",
    );
  });

  it("shows the not-found panel when the URL names no plugin at all", () => {
    renderWithIntl(<PluginPageClient />, coreEn);

    expect(screen.getByRole("alert")).toHaveTextContent(coreEn.pluginNotFound.title);
  });
});
