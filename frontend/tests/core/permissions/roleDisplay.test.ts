import { describe, it, expect } from "vitest";
import { formatRoleName, getDeclaredPermissions } from "@/core/permissions/roleDisplay";
import type { PermissionResponse } from "@/core/permissions/types";

describe("formatRoleName", () => {
  it.each([
    ["sparkth_user", "Sparkth user"],
    ["plugin_user", "Plugin user"],
    ["admin", "Admin"],
    ["grader", "Grader"],
    ["Course author", "Course author"],
    ["course__editor", "Course editor"],
  ])("shows %s as %s", (name, shown) => {
    expect(formatRoleName(name)).toBe(shown);
  });
});

function declared(name: string): PermissionResponse {
  return {
    name,
    label: name,
    description: "",
    category: "Users & access",
    risks: [],
    requires: [],
  };
}

describe("getDeclaredPermissions", () => {
  it("keeps the permissions still declared, in the order given", () => {
    expect(
      getDeclaredPermissions(
        ["role.update", "retired.permission", "role.read"],
        [declared("role.read"), declared("role.update")],
      ),
    ).toEqual(["role.update", "role.read"]);
  });

  it("keeps nothing when nothing is declared", () => {
    expect(getDeclaredPermissions(["role.read"], [])).toEqual([]);
  });
});
