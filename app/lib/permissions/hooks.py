from app.core.permissions.scope import PermissionScope
from app.lib.hooks import PluginCollectionHook

# Permission strings contributed by plugins. Platform-default permissions are seeded
# directly into PermissionsRegistry; this hook carries plugin contributions only.
PERMISSIONS: PluginCollectionHook[str] = PluginCollectionHook()

# Scope kinds contributed by plugins. Platform-default scopes (e.g. the global scope)
# are seeded into PermissionScopesRegistry; this hook carries plugin contributions only.
PERMISSION_SCOPE: PluginCollectionHook[PermissionScope] = PluginCollectionHook()
