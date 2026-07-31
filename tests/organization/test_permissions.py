"""Tests that the organizational-unit management permissions are registered.
Authored with LLM (Claude) assistance."""


def test_orgunit_permissions_are_registered() -> None:
    from sparkth.lib.permissions import (
        ORGANIZATION_UNIT_CREATE,
        ORGANIZATION_UNIT_DELETE,
        ORGANIZATION_UNIT_READ,
        ORGANIZATION_UNIT_UPDATE,
        get_permission,
    )

    assert get_permission("organization.unit.create") is ORGANIZATION_UNIT_CREATE
    assert get_permission("organization.unit.read") is ORGANIZATION_UNIT_READ
    assert get_permission("organization.unit.update") is ORGANIZATION_UNIT_UPDATE
    assert get_permission("organization.unit.delete") is ORGANIZATION_UNIT_DELETE
