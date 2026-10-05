import { describe, it, expect } from "vitest";
import { render, screen, within } from "@testing-library/react";
import { RankedBar } from "@/components/ui/RankedBar";

describe("RankedBar", () => {
  const data = [
    { label: "google", value: 3 },
    { label: "password", value: 12 },
    { label: "sso", value: 6 },
  ];

  it("ranks descending and scales bars to the largest value", () => {
    const { container } = render(
      <RankedBar data={data} caption="Logins by method" headers={["Method", "Logins"]} />,
    );
    const rows = within(screen.getByRole("table", { name: "Logins by method" })).getAllByRole(
      "rowheader",
    );
    expect(rows.map((r) => r.textContent)).toEqual(["password", "sso", "google"]);
    const widths = [...container.querySelectorAll<HTMLElement>("[data-bar]")].map(
      (b) => b.style.width,
    );
    expect(widths).toEqual(["100%", "50%", "25%"]);
  });

  it("shows only the top N", () => {
    render(<RankedBar data={data} limit={2} caption="c" headers={["Method", "Logins"]} />);
    expect(screen.queryByRole("rowheader", { name: "google" })).not.toBeInTheDocument();
  });
});
