import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { Badge } from "@/core/permissions/components/ui/Badge";

describe("Badge", () => {
  it("shows what it is given as a pill in the colours passed", () => {
    render(<Badge className="bg-primary-50 text-primary-700">Custom</Badge>);

    const badge = screen.getByText("Custom");
    expect(badge).toHaveClass("rounded-full", "text-xs", "bg-primary-50", "text-primary-700");
  });
});
