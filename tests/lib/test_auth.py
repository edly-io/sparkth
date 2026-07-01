import app.api.v1.auth as api_auth
import app.lib.auth as lib_auth


def test_get_current_user_lives_in_lib_auth() -> None:
    assert callable(lib_auth.get_current_user)


def test_get_current_user_not_reexported_from_api_auth() -> None:
    # get_current_user has a single canonical home in app.lib.auth; every caller (routes, the
    # permission dependency, and the test harness's dependency_overrides) imports it from there
    # so they all share one object. app.api.v1.auth must NOT re-export it — a compat shim would
    # split the canonical location and let a dependency_overrides key silently miss.
    assert not hasattr(api_auth, "get_current_user")
