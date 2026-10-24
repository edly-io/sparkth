import { afterEach, describe, it, expect, vi } from "vitest";
import { fireEvent, render, screen } from "@testing-library/react";

import MobileSidebar from "@/core/components/layout/MobileSidebar";

const sidebar = vi.hoisted(() => ({ isOpen: false, close: vi.fn() }));

vi.mock("@/lib/sidebar-context", () => ({ useSidebar: () => sidebar }));
vi.mock("@/core/components/layout/AppSidebar", () => ({
  default: ({ variant, onNavigate }: { variant: string; onNavigate?: () => void }) => (
    <button onClick={onNavigate}>{`sidebar ${variant}`}</button>
  ),
}));

describe("MobileSidebar", () => {
  afterEach(() => {
    sidebar.isOpen = false;
    sidebar.close.mockReset();
  });

  it("shows the mobile sidebar while the menu is open", () => {
    sidebar.isOpen = true;

    render(<MobileSidebar />);

    expect(screen.getByText("sidebar mobile")).toBeInTheDocument();
  });

  it("renders nothing while the menu is closed", () => {
    render(<MobileSidebar />);

    expect(screen.queryByText("sidebar mobile")).toBeNull();
  });

  it("closes the menu when the sidebar navigates", () => {
    sidebar.isOpen = true;
    render(<MobileSidebar />);

    fireEvent.click(screen.getByText("sidebar mobile"));

    expect(sidebar.close).toHaveBeenCalledOnce();
  });

  it("closes the menu when it is dismissed", () => {
    sidebar.isOpen = true;
    render(<MobileSidebar />);

    fireEvent.keyDown(screen.getByText("sidebar mobile"), { key: "Escape" });

    expect(sidebar.close).toHaveBeenCalledOnce();
  });
});
