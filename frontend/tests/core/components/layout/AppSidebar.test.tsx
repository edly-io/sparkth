import { afterEach, describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import AppSidebar from "@/core/components/layout/AppSidebar";

const nav = vi.hoisted(() => ({ pathname: "/dashboard" }));

// AppSidebar reads the current path and the plugin context; stub both so the
// component renders in isolation.
vi.mock("next/navigation", () => ({ usePathname: () => nav.pathname }));
vi.mock("@/core/plugins/context", () => ({
  usePluginContext: () => ({ userPlugins: [], loading: false }),
}));

describe("AppSidebar permission-gated nav", () => {
  it("shows Analytics when navPermissions.analytics is true", () => {
    render(<AppSidebar user={{ name: "A" }} navPermissions={{ analytics: true }} />);
    expect(screen.getByText("Analytics")).toBeInTheDocument();
  });

  it("hides Analytics when its permission is false", () => {
    render(<AppSidebar user={{ name: "A" }} navPermissions={{ analytics: false }} />);
    expect(screen.queryByText("Analytics")).not.toBeInTheDocument();
  });

  it("shows Admin when navPermissions.admin is true", () => {
    render(<AppSidebar user={{ name: "A" }} navPermissions={{ admin: true }} />);
    expect(screen.getByText("Admin")).toBeInTheDocument();
  });

  it("hides Admin when its permission is false", () => {
    render(<AppSidebar user={{ name: "A" }} navPermissions={{ admin: false }} />);
    expect(screen.queryByText("Admin")).not.toBeInTheDocument();
  });

  it("shows neither gated entry when navPermissions is absent", () => {
    render(<AppSidebar user={{ name: "A" }} />);
    expect(screen.queryByText("Analytics")).not.toBeInTheDocument();
    expect(screen.queryByText("Admin")).not.toBeInTheDocument();
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
