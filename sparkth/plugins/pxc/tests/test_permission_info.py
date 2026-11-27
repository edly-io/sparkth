"""Every permission the plugin declares says what it is for, under the plugin's own category."""

from pathlib import Path

import pytest

import sparkth.plugins.pxc.permissions as plugin_permissions
from sparkth.lib.permissions import PermissionRisk, get_permission
from sparkth.lib.testing import get_marked_messages

PERMISSIONS = [
    "pxc.activity.read",
    "pxc.activity.update",
    "pxc.activity.delete",
    "pxc.activity.place",
    "pxc.activity.play",
    "pxc.activity.edit",
]
# Deleting an activity removes it, and its learners' data, from every course that placed it.
RISKS: dict[str, set[PermissionRisk]] = {"pxc.activity.delete": {PermissionRisk.DELETES}}


@pytest.mark.parametrize("name", PERMISSIONS)
def test_a_permission_has_a_label_a_description_and_the_plugins_category(name: str) -> None:
    permission = get_permission(name)
    assert permission.label and permission.description and permission.category


@pytest.mark.parametrize("name", PERMISSIONS)
def test_a_permission_carries_its_risks(name: str) -> None:
    permission = get_permission(name)
    assert set(permission.risks) == RISKS.get(name, set())


def test_the_permission_text_is_marked_for_translation() -> None:
    extracted = get_marked_messages(Path(plugin_permissions.__file__).parent)

    for name in PERMISSIONS:
        permission = get_permission(name)
        assert {permission.label, permission.description, permission.category} <= extracted, name
