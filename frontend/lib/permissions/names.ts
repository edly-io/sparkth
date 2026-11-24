/**
 * The permissions core registers. Hand-maintained: the OpenAPI schema doesn't expose the
 * vocabulary, so keep this in sync with the backend registry.
 */
type CorePermissionName =
  | "analytics.read"
  | "audit.read"
  | "email.whitelist.read"
  | "email.whitelist.create"
  | "email.whitelist.delete"
  | "role.create"
  | "role.read"
  | "role.update"
  | "role.delete"
  | "group.create"
  | "group.read"
  | "group.update"
  | "group.delete"
  | "permission.read"
  | "user.read"
  | "llm.config.create"
  | "llm.config.read"
  | "llm.config.update"
  | "llm.config.delete"
  | "plugin.use"
  | "plugin.manage"
  | "file.upload";

/**
 * One entry per plugin that registers permissions, valued with the union of its permission
 * names. Empty here: each such plugin adds its entry from its own `permissions.d.ts`.
 */
export interface PluginPermissions {}

/**
 * Every permission name the backend registers, core and plugin. Typing a permission check's
 * argument against it turns a typo'd name, which would otherwise fail closed and silently (the
 * gated UI just never appears), into a compile error.
 */
export type PermissionName = CorePermissionName | PluginPermissions[keyof PluginPermissions];
