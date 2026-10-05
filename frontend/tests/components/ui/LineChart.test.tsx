import { describe, it, expect } from "vitest";
import { render, screen, within } from "@testing-library/react";
import { LineChart } from "@/components/ui/LineChart";

const data = [
  { label: "Jul 1", value: 2 },
  { label: "Jul 2", value: 5 },
  { label: "Jul 3", value: 0 },
];

describe("LineChart", () => {
  it("hides the SVG and exposes the data as a captioned table", () => {
    const { container } = render(
      <LineChart data={data} caption="Logins by day" headers={["Date", "Logins"]} />,
    );
    expect(container.querySelector("svg")).toHaveAttribute("aria-hidden", "true");
    const table = screen.getByRole("table", { name: "Logins by day" });
    expect(within(table).getAllByRole("row")).toHaveLength(4); // header + 3
    expect(within(table).getByRole("rowheader", { name: "Jul 2" })).toBeInTheDocument();
  });

  it("draws one line, plus a dashed comparison line when given", () => {
    const { container, rerender } = render(
      <LineChart data={data} caption="c" headers={["Date", "Logins"]} />,
    );
    expect(container.querySelectorAll("polyline")).toHaveLength(1);
    rerender(
      <LineChart
        data={data}
        comparison={[1, 1, 1]}
        caption="c"
        headers={["Date", "Logins", "Previous period"]}
      />,
    );
    const lines = container.querySelectorAll("polyline");
    expect(lines).toHaveLength(2);
    expect(lines[0]).toHaveAttribute("stroke-dasharray");
    expect(screen.getByRole("columnheader", { name: "Previous period" })).toBeInTheDocument();
  });

  it("renders a single point without dividing by zero", () => {
    const { container } = render(
      <LineChart data={[{ label: "Jul 1", value: 3 }]} caption="c" headers={["Date", "Logins"]} />,
    );
    expect(container.querySelector("polyline")?.getAttribute("points")).not.toMatch(/NaN|Infinity/);
  });
});
