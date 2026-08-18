from sparkth.lib.i18n import _


class RoleNotFound(Exception):
    """Raised when a role referenced by name does not exist."""

    def __init__(self, role_name: str) -> None:
        super().__init__(_("Role not found: {role_name}").format(role_name=role_name))
        self.role_name = role_name


class PermissionNotFound(Exception):
    """Raised when a permission referenced by name is not registered."""

    def __init__(self, permission: str) -> None:
        super().__init__(_("Permission not found: {permission}").format(permission=permission))
        self.permission = permission


class PermissionScopeNotFound(Exception):
    """Raised when a permission scope referenced by name is not registered."""

    def __init__(self, name: str) -> None:
        super().__init__(_("Permission scope not found: {name}").format(name=name))
        self.name = name


class RoleAlreadyExists(Exception):
    """Raised when creating or renaming a role to a name that is already taken."""

    def __init__(self, name: str) -> None:
        super().__init__(_("Role already exists: {name}").format(name=name))
        self.name = name


class RoleInUse(Exception):
    """Raised when deleting a role that still has active assignments."""

    def __init__(self, role_id: int) -> None:
        super().__init__(_("Role is still assigned and cannot be deleted: {role_id}").format(role_id=role_id))
        self.role_id = role_id


class GroupNotFound(Exception):
    """Raised when a group referenced by id or name does not exist."""

    def __init__(self, name: str) -> None:
        super().__init__(_("Group not found: {name}").format(name=name))
        self.name = name


class GroupAlreadyExists(Exception):
    """Raised when creating or renaming a group to a name that is already taken."""

    def __init__(self, name: str) -> None:
        super().__init__(_("Group already exists: {name}").format(name=name))
        self.name = name


class GroupInUse(Exception):
    """Raised when deleting a group that still has active role assignments."""

    def __init__(self, group_id: int) -> None:
        super().__init__(
            _("Group still has active role assignments and cannot be deleted: {group_id}").format(group_id=group_id)
        )
        self.group_id = group_id


class InvalidScopeObjectId(Exception):
    """Raised when a (scope, object id) pairing is invalid.

    An objectless scope must name no object (``scope_object_id`` is ``None``); an
    object-bearing scope must name one. Enforced in ``assign_role`` in place of the former
    ``ck_role_assignment_scope`` DB CHECK, so the database stays ignorant of the scope
    vocabulary (which lives in the ``PERMISSION_SCOPES`` hook).
    """

    def __init__(self, scope: str, scope_object_id: str | None) -> None:
        super().__init__(
            _("Invalid scope/object-id pairing for scope {scope!r}: {scope_object_id!r}").format(
                scope=scope, scope_object_id=scope_object_id
            )
        )
        self.scope = scope
        self.scope_object_id = scope_object_id
