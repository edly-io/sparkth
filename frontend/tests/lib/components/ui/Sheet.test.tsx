import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";

import { Sheet, SheetContent, SheetTitle } from "@/lib/components/ui/Sheet";

describe("Sheet", () => {
  it("renders its content while open", () => {
    render(
      <Sheet open>
        <SheetContent>
          <SheetTitle>History</SheetTitle>
          Panel body
        </SheetContent>
      </Sheet>,
    );

    expect(screen.getByText("Panel body")).toBeInTheDocument();
  });

  it("renders nothing while closed", () => {
    render(
      <Sheet open={false}>
        <SheetContent>
          <SheetTitle>History</SheetTitle>
          Panel body
        </SheetContent>
      </Sheet>,
    );

    expect(screen.queryByText("Panel body")).toBeNull();
  });
});
