from app.lib.hooks import HasName, SingleNamedItemHook

# The hooks are typed by the shared ``HasName`` bound rather than the concrete
# ``Permission`` / ``PermissionScope`` classes, so this module stays free of any
# app.core.permissions import.

# Every permission the platform knows. Core permissions are declared in
# app.core.permissions; plugins can add theirs via Permission.create().
# This hook is the single source of truth — PermissionsRegistry only reads from it.
PERMISSIONS: SingleNamedItemHook[HasName] = SingleNamedItemHook()

# Every scope kind the platform knows. Core scopes (the "global" root) are declared in
# app.core.permissions.scopes; plugins add theirs via PermissionScope.create().
# This hook is the single source of truth — PermissionScopesRegistry only reads from it.
PERMISSION_SCOPES: SingleNamedItemHook[HasName] = SingleNamedItemHook()
