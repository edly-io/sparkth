def test_analytics_read_permission_is_exported_from_lib() -> None:
    from sparkth.lib.permissions import ANALYTICS_READ

    assert ANALYTICS_READ.name == "analytics.read"
