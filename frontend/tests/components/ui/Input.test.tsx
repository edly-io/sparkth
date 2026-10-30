import { render, screen } from "@testing-library/react";
import { describe, it, expect } from "vitest";

import { Input } from "@/components/ui/Input";

describe("Input", () => {
  it("is marked invalid and described by its error", () => {
    render(<Input id="name" label="Name" error="Name is required." />);

    const input = screen.getByLabelText("Name");
    expect(input).toHaveAttribute("aria-invalid", "true");
    expect(input).toHaveAccessibleDescription("Name is required.");
  });

  it("is not marked invalid without an error", () => {
    render(<Input id="name" label="Name" />);

    expect(screen.getByLabelText("Name")).not.toHaveAttribute("aria-invalid");
  });
});
