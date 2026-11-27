import { describe, it, expect } from "vitest";
import { filterPermissions, groupByCategory } from "@/core/permissions/permissionList";
import type { PermissionResponse } from "@/core/permissions/types";

function permission(name: string, label: string, category: string): PermissionResponse {
  return { name, label, description: "", category, risks: [], requires: [] };
}

const SEE_ROLES = permission("role.read", "See roles", "Users & access");
const READ_CHATS = permission("compose.conversation.read", "Read conversations", "Compose");
const EDIT_ROLES = permission("role.update", "Edit roles", "Users & access");
const PERMISSIONS = [SEE_ROLES, READ_CHATS, EDIT_ROLES];

describe("groupByCategory", () => {
  it("groups permissions under their category, both in the order first met", () => {
    expect([...groupByCategory(PERMISSIONS)]).toEqual([
      ["Users & access", [SEE_ROLES, EDIT_ROLES]],
      ["Compose", [READ_CHATS]],
    ]);
  });
});

describe("filterPermissions", () => {
  it.each([
    ["label", "edit", [EDIT_ROLES]],
    ["category", "compose", [READ_CHATS]],
    ["internal name", "role.", [SEE_ROLES, EDIT_ROLES]],
    ["nothing typed", "  ", PERMISSIONS],
    ["no match", "nothing like this", []],
  ])("keeps the permissions matching by %s, whatever the case", (_, search, matching) => {
    expect(filterPermissions(PERMISSIONS, search.toUpperCase())).toEqual(matching);
  });
});
