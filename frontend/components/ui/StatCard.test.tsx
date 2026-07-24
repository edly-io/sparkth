import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";

import { StatCard } from "./StatCard";

describe("StatCard", () => {
  it("renders title, value, and hint", () => {
    render(<StatCard title="Total logins" value={42} hint="last 30 days" />);
    expect(screen.getByText("Total logins")).toBeInTheDocument();
    expect(screen.getByText("42")).toBeInTheDocument();
    expect(screen.getByText("last 30 days")).toBeInTheDocument();
  });

  it("omits the hint line when no hint is given", () => {
    render(<StatCard title="Busiest day" value="—" />);
    expect(screen.getByText("Busiest day")).toBeInTheDocument();
    expect(screen.getByText("—")).toBeInTheDocument();
  });
});
