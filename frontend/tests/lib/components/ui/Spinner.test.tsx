import { describe, it, expect } from "vitest";
import { render } from "@testing-library/react";

import { Spinner } from "@/lib/components/ui/Spinner";

describe("Spinner", () => {
  it("renders a spinning loader at the requested size", () => {
    const { container } = render(<Spinner size="sm" />);

    expect(container.querySelector("svg")).toHaveClass("animate-spin", "w-4", "h-4");
  });
});
