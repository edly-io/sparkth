import { describe, it, expect, vi } from "vitest";
import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { renderWithIntl } from "@/tests/intl";
import { RoleCard } from "@/core/permissions/components/ui/RoleCard";
import type { RoleResponse } from "@/core/permissions/types";

function role(overrides: Partial<RoleResponse>): RoleResponse {
  return {
    id: 1,
    name: "grader",
    description: "Marks submissions.",
    permissions: ["assignment.grade"],
    is_builtin: false,
    is_default: false,
    user_count: 0,
    group_count: 0,
    risks: [],
    ...overrides,
  };
}

describe("RoleCard", () => {
  it("shows a custom role's name, formatted to read, and description with a Custom badge", () => {
    renderWithIntl(<RoleCard role={role({})} />);

    expect(screen.getByRole("heading", { name: "Grader" })).toBeInTheDocument();
    expect(screen.getByText("Marks submissions.")).toBeInTheDocument();
    expect(screen.getByText("Custom")).toBeInTheDocument();
    expect(screen.queryByText("Built-in")).not.toBeInTheDocument();
  });

  it("shows a built-in role's name formatted to read, its description and a Built-in badge", () => {
    renderWithIntl(
      <RoleCard
        role={role({
          name: "admin",
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

  it("offers Delete in its menu when the role can be deleted", async () => {
    const onDelete = vi.fn();
    renderWithIntl(<RoleCard role={role({})} onDelete={onDelete} />);

    await userEvent.click(screen.getByRole("button", { name: "More actions for Grader" }));
    await userEvent.click(screen.getByRole("button", { name: "Delete role" }));

    expect(onDelete).toHaveBeenCalled();
  });

  it("has no menu when nothing can be done with the role", () => {
    renderWithIntl(<RoleCard role={role({})} />);

    expect(screen.queryByRole("button", { name: /More actions/ })).not.toBeInTheDocument();
  });
});
