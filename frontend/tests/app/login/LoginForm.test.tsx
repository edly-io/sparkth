import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";

import LoginForm from "@/app/login/LoginForm";

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: vi.fn() }),
  useSearchParams: () => new URLSearchParams(),
}));
vi.mock("@/core/auth/hooks", () => ({ useAuth: () => ({ login: vi.fn() }) }));

describe("LoginForm", () => {
  it("links to the privacy policy", () => {
    render(<LoginForm />);

    expect(screen.getByRole("link", { name: "Privacy Policy" })).toHaveAttribute(
      "href",
      "/privacy",
    );
  });
});
