"""Public API for the organization tree.

Application code and plugins import the organization surface from here, never from
``sparkth.core.organization`` directly. The tree is inert people-classification data:
nothing here grants access, and no permission check reads it.
"""

from sparkth.core.organization.exceptions import (
    OrganizationalUnitAlreadyExists,
    OrganizationalUnitInUse,
    OrganizationalUnitNotFound,
    OrganizationCycleError,
)
from sparkth.core.organization.memberships import (
    add_organization_member,
    get_organization_members,
    remove_organization_member,
)
from sparkth.core.organization.units import (
    create_organizational_unit,
    delete_organizational_unit,
    get_organizational_unit,
    list_organizational_units,
    move_organizational_unit,
    patch_organizational_unit,
    update_organizational_unit,
)

__all__ = [
    "add_organization_member",
    "create_organizational_unit",
    "delete_organizational_unit",
    "get_organization_members",
    "get_organizational_unit",
    "list_organizational_units",
    "move_organizational_unit",
    "patch_organizational_unit",
    "remove_organization_member",
    "update_organizational_unit",
    "OrganizationCycleError",
    "OrganizationalUnitAlreadyExists",
    "OrganizationalUnitInUse",
    "OrganizationalUnitNotFound",
]
