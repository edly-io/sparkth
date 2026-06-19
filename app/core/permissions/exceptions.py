class RoleNotFound(Exception):
    """Raised when a role referenced by name does not exist."""

    def __init__(self, role_name: str) -> None:
        super().__init__(f"Role not found: {role_name}")
        self.role_name = role_name
