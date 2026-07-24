import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";

import AppSidebar from "./AppSidebar";

// AppSidebar reads the current path and the enabled-plugins context; stub both
// so the component renders in isolation on a non-chat, non-plugin route.
vi.mock("next/navigation", () => ({ usePathname: () => "/dashboard" }));
vi.mock("@/lib/plugins/context", () => ({
  useEnabledPlugins: () => ({ plugins: [], loading: false }),
}));

describe("AppSidebar analytics nav entry", () => {
  it("shows Analytics when the user holds analytics.read", () => {
    render(<AppSidebar user={{ name: "A", permissions: ["analytics.read"] }} />);
    expect(screen.getByText("Analytics")).toBeInTheDocument();
  });

  it("hides Analytics when the user lacks the permission", () => {
    render(<AppSidebar user={{ name: "A", permissions: [] }} />);
    expect(screen.queryByText("Analytics")).not.toBeInTheDocument();
  });
});
