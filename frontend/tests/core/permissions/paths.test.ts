import { describe, it, expect } from "vitest";
import { ROLES_PATH, getRolePath } from "@/core/permissions/paths";

describe("getRolePath", () => {
  it("is the role page under Roles, naming the role by id", () => {
    expect(getRolePath(7)).toBe(`${ROLES_PATH}/role?id=7`);
    expect(ROLES_PATH).toBe("/dashboard/permissions/roles");
  });
});
