"""Give the test caller the default role, so key routes are reachable at their own user scope."""

import pytest


@pytest.fixture(autouse=True)
def _default_role(default_user_roles: object) -> None:
    """Hold the default role for every test in this package."""
