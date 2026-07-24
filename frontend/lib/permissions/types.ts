import type { Schema } from "@/lib/api";

export type PermissionCheckResponse = Schema<"PermissionCheckResponse">;

// The permission vocabulary the backend registers (see the PERMISSIONS hook in
// sparkth/core/permissions/__init__.py — the source of truth). Hand-maintained: the OpenAPI
// schema doesn't expose the vocabulary, so keep this in sync with the backend registry. Typing
// checkPermission's argument against it turns a typo'd permission — which would otherwise fail
// closed and silently (the gated UI just never appears) — into a compile error.
export type PermissionName =
  | "analytics.read"
  | "email.whitelist.read"
  | "email.whitelist.create"
  | "email.whitelist.delete"
  | "role.create"
  | "role.read"
  | "role.update"
  | "role.delete"
  | "permission.read";
