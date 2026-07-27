"""Exceptions for the organizational-unit CRUD engine (sparkth.core.organization.units).
Authored with LLM (Claude) assistance."""


class OrganizationalUnitNotFound(Exception):
    """Raised when an organizational unit referenced by id does not exist."""

    def __init__(self, unit: str) -> None:
        super().__init__(f"Organizational unit not found: {unit}")
        self.unit = unit


class OrganizationalUnitAlreadyExists(Exception):
    """Raised when creating, renaming, or moving a unit to a sibling name that is taken."""

    def __init__(self, name: str) -> None:
        super().__init__(f"Organizational unit name already taken among siblings: {name}")
        self.name = name


class OrganizationalUnitInUse(Exception):
    """Raised when deleting a unit that still has children or active members."""

    def __init__(self, unit_id: int) -> None:
        super().__init__(f"Organizational unit still has children or active members and cannot be deleted: {unit_id}")
        self.unit_id = unit_id


class OrganizationCycleError(Exception):
    """Raised when moving a unit under itself or one of its descendants."""

    def __init__(self, unit_id: int, new_parent_id: int) -> None:
        super().__init__(f"Moving organizational unit {unit_id} under {new_parent_id} would create a cycle")
        self.unit_id = unit_id
        self.new_parent_id = new_parent_id
