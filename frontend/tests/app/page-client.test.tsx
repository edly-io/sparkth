import { describe, it, expect, vi } from "vitest";
import { screen } from "@testing-library/react";

import HomeClient from "@/app/page-client";
import { renderWithIntl } from "../intl-test-utils";

// The page under test only renders landing copy; stub the collaborators that
// would otherwise need a router or theme context.
vi.mock("@/lib/auth-context", () => ({
  useAuth: () => ({ isAuthenticated: false, logout: vi.fn() }),
}));
vi.mock("next/navigation", () => ({ redirect: vi.fn() }));
vi.mock("@/components/SparkthHeader", () => ({ default: () => null }));

describe("HomeClient", () => {
  it("renders the localized landing copy", () => {
    renderWithIntl(<HomeClient />);

    expect(screen.getByRole("heading", { name: "Welcome to Sparkth" })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Get Started" })).toHaveAttribute("href", "/register");
    expect(screen.getByRole("link", { name: "Sign in" })).toHaveAttribute("href", "/login");
  });
});
