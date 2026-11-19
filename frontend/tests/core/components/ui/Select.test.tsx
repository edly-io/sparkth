import { render, screen } from "@testing-library/react";
import { describe, it, expect } from "vitest";

import { Select } from "@/core/components/ui/Select";

const OPTIONS = [{ value: "a", label: "A" }];
const ERROR = "Pick a model.";

describe("Select", () => {
  it("is marked invalid and described by an announced error", () => {
    render(<Select id="model" label="Model" options={OPTIONS} error={ERROR} />);

    const select = screen.getByLabelText("Model");
    expect(select).toHaveAttribute("aria-invalid", "true");
    expect(select).toHaveAccessibleDescription(ERROR);
    expect(screen.getByRole("alert")).toHaveTextContent(ERROR);
  });

  it("is not marked invalid without an error", () => {
    render(<Select id="model" label="Model" options={OPTIONS} />);

    expect(screen.getByLabelText("Model")).not.toHaveAttribute("aria-invalid");
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
  });
});
