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


class ScopeNotFound(Exception):
    """Raised when a scope referenced by name is not registered."""

    def __init__(self, name: str) -> None:
        super().__init__(f"Scope not found: {name}")
        self.name = name
