"""Enumerations of the permissions package."""

from enum import StrEnum


class PermissionRisk(StrEnum):
    """A reason to think twice before giving someone a permission."""

    # Lets the holder give others access: create roles, change what a role or group grants, or add people to a group.
    DELEGATES_ACCESS = "delegates_access"
    # Lets the holder see information about other people.
    PRIVATE_DATA = "private_data"
    # Lets the holder delete something for everyone.
    DELETES = "deletes"
