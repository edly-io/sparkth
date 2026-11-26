"""A permission keeps what it says it is for: a label, a description, a category and its risks."""

from pathlib import Path

import pytest

import sparkth.core.permissions as core_permissions
from sparkth.core.permissions import PERMISSIONS, Permission, get_permission
from sparkth.core.permissions.enums import PermissionRisk
from sparkth.lib.testing import get_marked_messages


@pytest.fixture(autouse=True)
def _restore_registry(monkeypatch: pytest.MonkeyPatch) -> None:
    # A permission created here registers on the shared hook; restore it after each test.
    monkeypatch.setattr(PERMISSIONS, "_items", dict(PERMISSIONS._items))


def test_a_permission_keeps_the_information_it_is_created_with() -> None:
    viewing = Permission.create("assignment.view", "See assignments", "Open submissions.", "Courses")
    Permission.create(
        "assignment.grade",
        "Grade assignments",
        "Mark submissions and give feedback.",
        "Courses",
        risks=(PermissionRisk.DELETES,),
        requires=(viewing,),
    )

    permission = get_permission("assignment.grade")
    assert (permission.label, permission.description, permission.category) == (
        "Grade assignments",
        "Mark submissions and give feedback.",
        "Courses",
    )
    assert (permission.risks, permission.requires) == ((PermissionRisk.DELETES,), (viewing,))


CORE_PERMISSIONS = [
    "email.whitelist.read",
    "email.whitelist.create",
    "email.whitelist.delete",
    "role.create",
    "role.read",
    "role.update",
    "role.delete",
    "group.create",
    "group.read",
    "group.update",
    "group.delete",
    "permission.read",
    "analytics.read",
    "audit.read",
    "user.read",
    "llm.config.create",
    "llm.config.read",
    "llm.config.update",
    "llm.config.delete",
    "plugin.use",
    "plugin.manage",
    "file.upload",
]

RISKS = {
    "role.create": {PermissionRisk.DELEGATES_ACCESS},
    "role.update": {PermissionRisk.DELEGATES_ACCESS},
    "group.update": {PermissionRisk.DELEGATES_ACCESS},
    "user.read": {PermissionRisk.PRIVATE_DATA},
    "audit.read": {PermissionRisk.PRIVATE_DATA},
    "role.delete": {PermissionRisk.DELETES},
    "group.delete": {PermissionRisk.DELETES},
    "email.whitelist.delete": {PermissionRisk.DELETES},
}


@pytest.mark.parametrize("name", CORE_PERMISSIONS)
def test_a_core_permission_has_a_label_a_description_and_a_category(name: str) -> None:
    permission = get_permission(name)
    assert permission.label and permission.description and permission.category


@pytest.mark.parametrize("name", CORE_PERMISSIONS)
def test_a_core_permission_carries_the_risks_decided_for_it(name: str) -> None:
    permission = get_permission(name)
    assert set(permission.risks) == RISKS.get(name, set())


def test_core_permission_text_is_marked_for_translation() -> None:
    extracted = get_marked_messages(Path(core_permissions.__file__).parent)

    for name in CORE_PERMISSIONS:
        permission = get_permission(name)
        assert {permission.label, permission.description, permission.category} <= extracted, name
