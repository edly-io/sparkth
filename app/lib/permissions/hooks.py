from app.core.permissions.scope import PermissionScope
from app.core.permissions.constants import SCOPE_GLOBAL
from app.lib.hooks import PluginCollectionHook

# Permissions hook
PERMISSIONS: PluginCollectionHook[str] = PluginCollectionHook()

# Scopes hook
PERMISSION_SCOPE: PluginCollectionHook[PermissionScope] = PluginCollectionHook()
# PERMISSION_SCOPE.add_item(PermissionScope(plugin, SCOPE_GLOBAL))  # default global; may move

# TODO: question: how to add default scopes and permission that are not related to any plugin?
# cant add to `PluginCollectionHook` without a plugin.
# TODO: question - where do these hooks get registered in the app lifecycle?
