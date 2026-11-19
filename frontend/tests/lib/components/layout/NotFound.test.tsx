import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";

import { NotFound } from "@/lib/components/layout/NotFound";

describe("NotFound", () => {
  it("announces itself to screen readers when it appears", () => {
    render(<NotFound title="Chat not found" />);

    expect(screen.getByRole("alert")).toHaveTextContent("Chat not found");
  });

  it("names what was not found as a heading", () => {
    render(<NotFound title="Chat not found" />);

    expect(screen.getByRole("heading", { name: "Chat not found" })).toBeInTheDocument();
  });

  it("shows the message and the action it is given", () => {
    render(
      <NotFound
        title="Chat not found"
        message="It may have been deleted."
        action={<a href="/dashboard/compose">New chat</a>}
      />,
    );

    expect(screen.getByText("It may have been deleted.")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "New chat" })).toHaveAttribute(
      "href",
      "/dashboard/compose",
    );
  });
});
