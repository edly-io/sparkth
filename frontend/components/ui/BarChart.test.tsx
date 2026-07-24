import { describe, it, expect } from "vitest";
import { render } from "@testing-library/react";

import { BarChart } from "./BarChart";

describe("BarChart", () => {
  it("renders one bar (rect) per data point", () => {
    const { container } = render(
      <BarChart
        data={[
          { label: "a", value: 1 },
          { label: "b", value: 2 },
          { label: "c", value: 0 },
        ]}
      />,
    );
    expect(container.querySelectorAll("rect")).toHaveLength(3);
  });

  it("exposes an accessible name describing the series", () => {
    const { getByRole } = render(<BarChart data={[{ label: "a", value: 1 }]} />);
    expect(getByRole("img")).toHaveAccessibleName(/bar chart/i);
  });

  it("renders with empty data without crashing", () => {
    const { container, getByRole } = render(<BarChart data={[]} />);
    expect(getByRole("img")).toBeInTheDocument();
    expect(container.querySelectorAll("rect")).toHaveLength(0);
  });
});
