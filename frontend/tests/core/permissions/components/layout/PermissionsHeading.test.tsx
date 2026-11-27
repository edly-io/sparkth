import { describe, expect, it } from "vitest";
import { screen } from "@testing-library/react";
import { renderWithIntl } from "@/tests/intl";
import { PermissionsHeading } from "@/core/permissions/components/layout/PermissionsHeading";

describe("PermissionsHeading", () => {
  it("shows the section's heading and what it is for", () => {
    renderWithIntl(<PermissionsHeading />);

    expect(
      screen.getByRole("heading", { level: 1, name: "Access & permissions" }),
    ).toBeInTheDocument();
    expect(screen.getByText("See and manage who can do what in Sparkth.")).toBeInTheDocument();
  });
});
