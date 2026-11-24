import { describe, it, expect } from "vitest";
import { screen } from "@testing-library/react";
import { renderWithIntl } from "@/tests/intl";
import { RoleCard } from "@/core/permissions/components/ui/RoleCard";
import type { RoleResponse } from "@/core/permissions/types";

function role(overrides: Partial<RoleResponse>): RoleResponse {
  return {
    id: 1,
    name: "grader",
    display_name: "grader",
    description: "Marks submissions.",
    permissions: ["assignment.grade"],
    is_builtin: false,
    is_default: false,
    user_count: 0,
    group_count: 0,
    ...overrides,
  };
}

describe("RoleCard", () => {
  it("shows a custom role's own name and description with a Custom badge", () => {
    renderWithIntl(<RoleCard role={role({})} />);

    expect(screen.getByRole("heading", { name: "grader" })).toBeInTheDocument();
    expect(screen.getByText("Marks submissions.")).toBeInTheDocument();
    expect(screen.getByText("Custom")).toBeInTheDocument();
    expect(screen.queryByText("Built-in")).not.toBeInTheDocument();
  });

  it("shows the name and description the API gives a built-in role, with a Built-in badge", () => {
    renderWithIntl(
      <RoleCard
        role={role({
          name: "admin",
          display_name: "Admin",
          description: "Can do everything in Sparkth.",
          is_builtin: true,
        })}
      />,
    );

    expect(screen.getByRole("heading", { name: "Admin" })).toBeInTheDocument();
    expect(screen.getByText("Can do everything in Sparkth.")).toBeInTheDocument();
    expect(screen.getByText("Built-in")).toBeInTheDocument();
    expect(screen.queryByText("Custom")).not.toBeInTheDocument();
  });

  it("marks a role every account is given as automatic and held by everyone", () => {
    renderWithIntl(
      <RoleCard
        role={role({
          name: "sparkth_user",
          display_name: "Sparkth user",
          is_builtin: true,
          is_default: true,
          user_count: 40,
        })}
      />,
    );

    expect(screen.getByRole("heading", { name: "Sparkth user" })).toBeInTheDocument();
    expect(screen.getByText("Built-in")).toBeInTheDocument();
    expect(screen.getByText("Automatic")).toBeInTheDocument();
    expect(screen.getByText("Everyone", { selector: "strong" })).toBeInTheDocument();
    expect(screen.queryByText(/40/)).not.toBeInTheDocument();
  });

  it("counts its permissions", () => {
    renderWithIntl(<RoleCard role={role({ permissions: ["a.read", "a.write"] })} />);

    expect(screen.getByRole("article")).toHaveTextContent("2 permissions");
    expect(screen.getByText("2", { selector: "strong" })).toBeInTheDocument();
  });

  it.each([
    [{ user_count: 1, group_count: 0 }, "1 person"],
    [{ user_count: 3, group_count: 2 }, "2 groups · 3 people"],
    [{ user_count: 0, group_count: 1 }, "1 group"],
    [{ user_count: 0, group_count: 0 }, "Not assigned"],
  ])("says who holds it: %o", (counts, text) => {
    renderWithIntl(<RoleCard role={role(counts)} />);

    expect(screen.getByText(text, { selector: "strong" })).toBeInTheDocument();
  });
});
