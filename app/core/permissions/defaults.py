"""Platform-default permission vocabulary.

These are the permissions and scope kinds the application ships with. The registries
seed them at construction, so they exist independently of which plugins are loaded.
"""

from app.core.permissions.constants import SCOPE_GLOBAL
from app.core.permissions.scope import PermissionScope

# Default scope kinds, ordered root-first so each is registered after its parent.
DEFAULT_PERMISSION_SCOPES: list[PermissionScope] = [
    # The root scope: it applies platform-wide and names no object. This is the canonical
    # instance plugins should reference as a parent so the whole tree shares one root.
    PermissionScope(SCOPE_GLOBAL)
]
# Default permission strings shipped with the platform.
DEFAULT_PERMISSIONS: list[str] = []
