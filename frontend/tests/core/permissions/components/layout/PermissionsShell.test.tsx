import { describe, expect, it } from "vitest";
import { screen } from "@testing-library/react";
import { renderWithIntl } from "@/tests/intl";
import { PermissionsShell } from "@/core/permissions/components/layout/PermissionsShell";

describe("PermissionsShell", () => {
  it("shows the section's heading and what it is for", () => {
    renderWithIntl(<PermissionsShell>content</PermissionsShell>);

    expect(
      screen.getByRole("heading", { level: 1, name: "Access & permissions" }),
    ).toBeInTheDocument();
    expect(screen.getByText("See and manage who can do what in Sparkth.")).toBeInTheDocument();
  });

  it("leaves the heading out for a page that has its own", () => {
    renderWithIntl(
      <PermissionsShell withHeading={false}>
        <p>role page</p>
      </PermissionsShell>,
    );

    expect(screen.getByText("role page")).toBeInTheDocument();
    expect(screen.queryByRole("heading")).not.toBeInTheDocument();
  });

  it("renders its content after the heading", () => {
    renderWithIntl(
      <PermissionsShell>
        <p>tab content</p>
      </PermissionsShell>,
    );

    const heading = screen.getByRole("heading", { level: 1 });
    const content = screen.getByText("tab content");
    expect(
      heading.compareDocumentPosition(content) & Node.DOCUMENT_POSITION_FOLLOWING,
    ).toBeTruthy();
  });
});
