import { describe, expect, it } from "vitest";
import { screen } from "@testing-library/react";
import { renderWithIntl } from "@/tests/intl";
import { PermissionsShell } from "@/core/permissions/components/layout/PermissionsShell";

describe("PermissionsShell", () => {
  it("frames its content, with no heading of its own", () => {
    renderWithIntl(
      <PermissionsShell>
        <p>page content</p>
      </PermissionsShell>,
    );

    expect(screen.getByText("page content")).toBeInTheDocument();
    expect(screen.queryByRole("heading")).not.toBeInTheDocument();
  });
});
