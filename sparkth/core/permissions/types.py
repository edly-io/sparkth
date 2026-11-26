"""Value objects of the permissions package."""

from dataclasses import dataclass


@dataclass(frozen=True)
class RoleAssigneeCounts:
    """How many people hold a role directly, and how many groups hold it, through active assignments."""

    user_count: int
    group_count: int
