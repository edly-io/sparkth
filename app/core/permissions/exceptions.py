class RoleNotFound(Exception):
    """Raised when a role referenced by name does not exist."""

    def __init__(self, role_name: str) -> None:
        super().__init__(f"Role not found: {role_name}")
        self.role_name = role_name


class PermissionNotFound(Exception):
    """Raised when a permission referenced by name is not registered."""

    def __init__(self, permission: str) -> None:
        super().__init__(f"Permission not found: {permission}")
        self.permission = permission


class PermissionScopeNotFound(Exception):
    """Raised when a permission scope referenced by name is not registered."""

    def __init__(self, name: str) -> None:
        super().__init__(f"Permission scope not found: {name}")
        self.name = name


class RoleAlreadyExists(Exception):
    """Raised when creating or renaming a role to a name that is already taken."""

    def __init__(self, name: str) -> None:
        super().__init__(f"Role already exists: {name}")
        self.name = name


class RoleInUse(Exception):
    """Raised when deleting a role that still has active assignments."""

    def __init__(self, role_id: int) -> None:
        super().__init__(f"Role is still assigned and cannot be deleted: {role_id}")
        self.role_id = role_id
