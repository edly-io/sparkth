import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { ChartColumn } from "lucide-react";

import { SidebarLink } from "@/core/sidebar/components/ui/SidebarLink/SidebarLink";

describe("SidebarLink", () => {
  it("renders a link to href with the label and an icon", () => {
    const { container } = render(
      <SidebarLink
        href="/dashboard/analytics"
        label="Analytics"
        icon={ChartColumn}
        isActive={false}
      />,
    );
    const link = screen.getByRole("link", { name: /analytics/i });
    expect(link).toHaveAttribute("href", "/dashboard/analytics");
    expect(container.querySelector("svg")).toBeInTheDocument();
  });

  it("applies active styling when isActive", () => {
    render(<SidebarLink href="/x" label="X" icon={ChartColumn} isActive />);
    expect(screen.getByRole("link")).toHaveClass("border-primary-500");
  });

  it("hides the label when collapsed", () => {
    render(<SidebarLink href="/x" label="X" icon={ChartColumn} isActive={false} isCollapsed />);
    expect(screen.queryByText("X")).not.toBeInTheDocument();
  });
});
