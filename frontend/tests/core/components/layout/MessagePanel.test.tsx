import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { SearchX } from "lucide-react";

import { MessagePanel } from "@/core/components/layout/MessagePanel";

describe("MessagePanel", () => {
  it("names the situation as a heading", () => {
    render(<MessagePanel icon={SearchX} title="Nothing here" />);

    expect(screen.getByRole("heading", { name: "Nothing here" })).toBeInTheDocument();
  });

  it("shows the message and the action it is given", () => {
    render(
      <MessagePanel
        icon={SearchX}
        title="Nothing here"
        message="It may have been deleted."
        action={<a href="/dashboard">Back</a>}
      />,
    );

    expect(screen.getByText("It may have been deleted.")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Back" })).toHaveAttribute("href", "/dashboard");
  });

  it("draws the icon it is given and keeps it from screen readers", () => {
    const { container } = render(<MessagePanel icon={SearchX} title="Nothing here" />);

    expect(container.querySelector("svg")).toHaveAttribute("aria-hidden", "true");
  });
});
