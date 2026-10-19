import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";

import RegisterForm from "@/app/register/RegisterForm";

describe("RegisterForm", () => {
  it("links to the privacy policy", () => {
    render(<RegisterForm />);

    expect(screen.getByRole("link", { name: "Privacy Policy" })).toHaveAttribute(
      "href",
      "/privacy",
    );
  });
});
