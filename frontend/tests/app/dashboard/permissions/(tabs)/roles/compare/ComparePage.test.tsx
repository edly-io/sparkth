import { describe, it, expect } from "vitest";
import { screen } from "@testing-library/react";
import { renderWithIntl } from "@/tests/intl";
import ComparePage from "@/app/dashboard/permissions/(tabs)/roles/compare/ComparePage";

describe("ComparePage", () => {
  it("opens on the Compare view and says it is view only", () => {
    renderWithIntl(<ComparePage />);

    expect(screen.getByRole("link", { name: "Compare permissions" })).toHaveAttribute(
      "aria-current",
      "page",
    );
    expect(screen.getByText("View only")).toBeInTheDocument();
  });
});
