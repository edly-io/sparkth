import { describe, it, expect } from "vitest";
import { formatRoleName } from "@/core/permissions/roleName";

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
