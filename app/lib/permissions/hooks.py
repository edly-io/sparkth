from app.core.permissions.scope import Scope
from app.core.permissions.constants import SCOPE_GLOBAL
from app.lib.hooks import PluginCollectionHook

# Permissions hook
PERMISSIONS: PluginCollectionHook[str] = PluginCollectionHook()

# Scopes hook
SCOPES: PluginCollectionHook[Scope] = PluginCollectionHook()
# SCOPES.add_item(Scope(SCOPE_GLOBAL))    # Adding this here for now, might need to shift to a better place

# TODO: question: how to add default scopes and permission that are not related to any plugin?
# cant add to `PluginCollectionHook` without a plugin.
# TODO: question - where do these PERMISSIONS get registered in the plugin lifecycle?
