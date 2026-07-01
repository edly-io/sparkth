import app.api.v1.auth as api_auth
import app.lib.auth as lib_auth


def test_get_current_user_lives_in_lib_auth() -> None:
    assert callable(lib_auth.get_current_user)


def test_get_current_user_reexported_from_api_auth_is_same_object() -> None:
    # The test harness overrides get_current_user imported from app.api.v1.auth, while the
    # permission dependency imports it from app.lib.auth. dependency_overrides keys on object
    # identity, so the re-export MUST be the very same function object.
    assert api_auth.get_current_user is lib_auth.get_current_user
