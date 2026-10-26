import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";

import { TooltipProvider } from "@/core/components/ui/Tooltip";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/lib/components/ui/Tooltip";

describe("Tooltip", () => {
  it("shows its content while open", () => {
    render(
      <TooltipProvider>
        <Tooltip open>
          <TooltipTrigger>Expand</TooltipTrigger>
          <TooltipContent>Show chat history</TooltipContent>
        </Tooltip>
      </TooltipProvider>,
    );

    // Radix also renders a visually hidden copy for screen readers.
    expect(screen.getAllByText("Show chat history").length).toBeGreaterThan(0);
  });
});
