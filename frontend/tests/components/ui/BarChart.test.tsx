import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";

import { BarChart } from "@/components/ui/BarChart";

describe("BarChart", () => {
  it("renders one bar (rect) per data point", () => {
    const { container } = render(
      <BarChart
        data={[
          { label: "a", value: 1 },
          { label: "b", value: 2 },
          { label: "c", value: 0 },
        ]}
        caption="c"
        headers={["Date", "Logins"]}
      />,
    );
    expect(container.querySelectorAll("rect")).toHaveLength(3);
  });

  it("renders repeated labels without a React key collision (labels need not be unique)", () => {
    // Shared primitive: identity is positional, so duplicate labels must not warn or drop bars.
    const spy = vi.spyOn(console, "error").mockImplementation(() => {});
    try {
      const { container } = render(
        <BarChart
          data={[
            { label: "Mon", value: 1 },
            { label: "Mon", value: 2 },
          ]}
          caption="c"
          headers={["Date", "Logins"]}
        />,
      );
      expect(container.querySelectorAll("rect")).toHaveLength(2);
      expect(spy).not.toHaveBeenCalled();
    } finally {
      spy.mockRestore();
    }
  });

  it("hides the SVG and exposes the data as a captioned table", () => {
    const { container } = render(
      <BarChart
        data={[{ label: "a", value: 1 }]}
        caption="Logins by day"
        headers={["Date", "Logins"]}
      />,
    );
    expect(container.querySelector("svg")).toHaveAttribute("aria-hidden", "true");
    expect(screen.getByRole("table", { name: "Logins by day" })).toBeInTheDocument();
  });

  it("draws a bottom baseline so zero/low days have a visible floor", () => {
    // A zero value renders a zero-height rect (invisible), so a quiet month would read as an
    // empty chart. A baseline at the plot bottom keeps it legible. Assert there are two
    // horizontal rules at different heights — the top max-value gridline and the baseline
    // below it — without hard-coding the layout constants.
    const { container } = render(
      <BarChart
        data={[
          { label: "a", value: 0 },
          { label: "b", value: 3 },
        ]}
        caption="c"
        headers={["Date", "Logins"]}
      />,
    );
    const ys = Array.from(container.querySelectorAll("line"))
      .filter((l) => l.getAttribute("y1") === l.getAttribute("y2"))
      .map((l) => Number(l.getAttribute("y1")));
    expect(Math.max(...ys)).toBeGreaterThan(Math.min(...ys));
  });

  it("renders with empty data without crashing", () => {
    const { container } = render(<BarChart data={[]} caption="c" headers={["Date", "Logins"]} />);
    expect(container.querySelector("svg")).toBeInTheDocument();
    expect(container.querySelectorAll("rect")).toHaveLength(0);
  });
});
