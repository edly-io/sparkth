import { describe, it, expect } from "vitest";
import { screen } from "@testing-library/react";

import { Forbidden } from "@/lib/components/layout/Forbidden";
import coreEn from "@/core/i18n/en.json";
import { renderWithIntl } from "@/lib/testing/intl";

describe("Forbidden", () => {
  it("tells the user they have no access, without naming a permission", () => {
    renderWithIntl(<Forbidden />, coreEn);

    expect(screen.getByRole("heading", { name: coreEn.forbidden.title })).toBeInTheDocument();
    expect(screen.getByText(coreEn.forbidden.message)).toBeInTheDocument();
  });

  it("leads back to the dashboard", () => {
    renderWithIntl(<Forbidden />, coreEn);

    expect(screen.getByRole("link", { name: coreEn.forbidden.back })).toHaveAttribute(
      "href",
      "/dashboard",
    );
  });
});
