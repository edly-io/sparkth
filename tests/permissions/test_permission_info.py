"""A permission keeps what it says it is for: a label, a description, a category, its risks and what it needs."""

import pytest

from sparkth.core.permissions import PERMISSIONS, Permission, get_permission
from sparkth.core.permissions.enums import PermissionRisk


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
