import { afterEach, describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import AppSidebar from "@/core/sidebar/components/layout/AppSidebar";

const nav = vi.hoisted(() => ({ pathname: "/dashboard" }));

// AppSidebar reads the current path and the plugin context; stub both so the
// component renders in isolation.
vi.mock("next/navigation", () => ({ usePathname: () => nav.pathname }));
vi.mock("@/core/plugins/context", () => ({
  usePluginContext: () => ({ plugins: [], loading: false }),
}));

describe("AppSidebar permission-gated links", () => {
  afterEach(() => {
    nav.pathname = "/dashboard";
  });

  it("shows Analytics when sidebarPermissions.analytics is true", () => {
    render(<AppSidebar user={{ name: "A" }} sidebarPermissions={{ analytics: true }} />);
    expect(screen.getByText("Analytics")).toBeInTheDocument();
  });

  it("hides Analytics when its permission is false", () => {
    render(<AppSidebar user={{ name: "A" }} sidebarPermissions={{ analytics: false }} />);
    expect(screen.queryByText("Analytics")).not.toBeInTheDocument();
  });

  it("shows Admin when sidebarPermissions.admin is true", () => {
    render(<AppSidebar user={{ name: "A" }} sidebarPermissions={{ admin: true }} />);
    expect(screen.getByText("Admin")).toBeInTheDocument();
  });

  it("hides Admin when its permission is false", () => {
    render(<AppSidebar user={{ name: "A" }} sidebarPermissions={{ admin: false }} />);
    expect(screen.queryByText("Admin")).not.toBeInTheDocument();
  });

  it("links Access & permissions to its first tab when sidebarPermissions.permissions is true", () => {
    render(<AppSidebar user={{ name: "A" }} sidebarPermissions={{ permissions: true }} />);
    expect(screen.getByRole("link", { name: "Access & permissions" })).toHaveAttribute(
      "href",
      "/dashboard/permissions/roles",
    );
  });

  it("hides Access & permissions when its permissions are not all held", () => {
    render(<AppSidebar user={{ name: "A" }} sidebarPermissions={{ permissions: false }} />);
    expect(screen.queryByText("Access & permissions")).not.toBeInTheDocument();
  });

  it("highlights Access & permissions on any of its tabs", () => {
    nav.pathname = "/dashboard/permissions/groups";
    render(<AppSidebar user={{ name: "A" }} sidebarPermissions={{ permissions: true }} />);
    expect(screen.getByRole("link", { name: "Access & permissions" })).toHaveClass(
      "border-primary-500",
    );
  });

  it("shows neither gated entry when sidebarPermissions is absent", () => {
    render(<AppSidebar user={{ name: "A" }} />);
    expect(screen.queryByText("Analytics")).not.toBeInTheDocument();
    expect(screen.queryByText("Admin")).not.toBeInTheDocument();
  });
});

describe("AppSidebar plugin entries", () => {
  it("shows no Resources entry when no plugin declares one", () => {
    render(<AppSidebar user={{ name: "A" }} />);

    expect(screen.queryByText("Resources")).not.toBeInTheDocument();
  });
});

describe("AppSidebar documentation link", () => {
  it("opens the documentation home page in a new tab", () => {
    render(<AppSidebar user={{ name: "A" }} />);

    const link = screen.getByRole("link", { name: "Documentation (opens in a new tab)" });
    expect(link).toHaveAttribute("href", "https://edly-io.github.io/sparkth/");
    expect(link).toHaveAttribute("target", "_blank");
    expect(link).toHaveAttribute("rel", "noopener noreferrer");
  });
});

describe("AppSidebar user menu", () => {
  it("links to the privacy policy", async () => {
    render(<AppSidebar user={{ name: "Ada" }} />);

    await userEvent.click(screen.getByText("Ada"));

    expect(screen.getByRole("link", { name: "Privacy Policy" })).toHaveAttribute(
      "href",
      "/privacy",
    );
  });

  it("links to the profile page inside the dashboard", async () => {
    render(<AppSidebar user={{ name: "Ada" }} />);

    await userEvent.click(screen.getByText("Ada"));

    expect(screen.getByRole("link", { name: "Profile" })).toHaveAttribute(
      "href",
      "/dashboard/profile",
    );
  });
});

describe("AppSidebar on a plugin page", () => {
  afterEach(() => {
    nav.pathname = "/dashboard";
  });

  it("renders no chat history on the chat page", () => {
    nav.pathname = "/dashboard/compose";

    render(<AppSidebar user={{ name: "A" }} />);

    expect(screen.queryByText("Recent chats")).toBeNull();
  });
});
