from app.permissions.constants import SCOPE_GLOBAL
from app.permissions.exceptions import RoleNotFound


def test_scope_global_constant() -> None:
    assert SCOPE_GLOBAL == "global"


def test_role_not_found_carries_name() -> None:
    exc = RoleNotFound("teacher")
    assert exc.role_name == "teacher"
    assert "teacher" in str(exc)
