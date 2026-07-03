from app.core.permissions.exceptions import PermissionNotFound
from app.lib.hooks import SingleNamedItemHook


class Permission:
    def __init__(self, name: str) -> None:
        self.name = name

    @classmethod
    def create(cls, name: str) -> "Permission":
        """Create a permission and register it on the PERMISSIONS hook.

        Use this, not the bare ``Permission(name)`` constructor — the constructor does not
        register (it is internal/test-only), and an unregistered permission authorizes nothing.
        """
        permission = cls(name)
        PERMISSIONS.add_item(permission)
        return permission

    # TODO: Weigh in the pros and cons for these methods
    # defered to a later PR.
    # def require(self):
    #     ...

    # def require_in_scope(self, permisson_scope: str, scope_object_id: str):
    #     ...


# Every permission the platform knows; Permission.create() registers each one here.
# This hook is the single source of truth — get_permission() resolves names against it.
PERMISSIONS: SingleNamedItemHook[Permission] = SingleNamedItemHook()


def get_permission(name: str) -> Permission:
    """Return the registered permission named ``name``, or raise PermissionNotFound."""
    permission = PERMISSIONS.get(name)
    if permission is None:
        raise PermissionNotFound(name)
    return permission


# Core Permissions shipped with the application.

# The email-whitelist permissions gate the registration email whitelist.
EMAIL_WHITELIST_READ = Permission.create("email.whitelist.read")
EMAIL_WHITELIST_CREATE = Permission.create("email.whitelist.create")
EMAIL_WHITELIST_DELETE = Permission.create("email.whitelist.delete")
