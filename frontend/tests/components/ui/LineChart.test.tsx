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

  it("marks a single point with a dot, labelled underneath it", () => {
    // A one-vertex polyline has zero length and paints nothing, so a lone point needs a marker.
    const { container } = render(
      <LineChart data={[{ label: "Jul 1", value: 3 }]} caption="c" headers={["Date", "Logins"]} />,
    );
    const dot = container.querySelector("circle");
    expect(dot).toBeInTheDocument();
    expect(dot?.getAttribute("cx")).not.toMatch(/NaN|Infinity/);
    expect(dot?.getAttribute("cy")).not.toMatch(/NaN|Infinity/);
    const label = container.querySelector("text");
    expect(label).toHaveTextContent("Jul 1");
    expect(label).toHaveAttribute("x", dot?.getAttribute("cx"));
    expect(label).toHaveAttribute("text-anchor", "middle");
  });

  it("leaves no dot when there are several points", () => {
    const { container } = render(
      <LineChart data={data} caption="c" headers={["Date", "Logins"]} />,
    );
    expect(container.querySelector("circle")).not.toBeInTheDocument();
  });

  it("reads a missing previous-period value as a dash, not as zero", () => {
    render(
      <LineChart
        data={data}
        comparison={[4]}
        caption="c"
        headers={["Date", "Logins", "Previous period"]}
      />,
    );
    const cells = (day: string) =>
      within(screen.getByRole("rowheader", { name: day }).closest("tr")!).getAllByRole("cell");
    expect(cells("Jul 1")[1]).toHaveTextContent("4");
    expect(cells("Jul 2")[1]).toHaveTextContent("—");
    expect(cells("Jul 3")[1]).toHaveTextContent("—");
  });

  it("ignores comparison values beyond the data, so nothing plots off-chart", () => {
    const { container } = render(
      <LineChart
        data={data}
        comparison={[1, 1, 1, 50, 50]}
        caption="c"
        headers={["Date", "Logins", "Previous period"]}
      />,
    );
    const [dashed, line] = container.querySelectorAll("polyline");
    expect(dashed.getAttribute("points")?.split(" ")).toHaveLength(data.length);
    // Scaled to the data's max (5), not the dropped 50: the 5 sits at the top of the plot.
    expect(line.getAttribute("points")?.split(" ")[1]).toMatch(/,8$/);
    expect(within(screen.getByRole("table")).getAllByRole("row")).toHaveLength(data.length + 1);
  });
});
