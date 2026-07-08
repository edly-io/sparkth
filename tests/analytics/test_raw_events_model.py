from sparkth.core.analytics.models import analytics_metadata, raw_events


def test_raw_events_is_registered_on_analytics_metadata() -> None:
    assert "raw_events" in analytics_metadata.tables
    assert raw_events is analytics_metadata.tables["raw_events"]


def test_raw_events_has_expected_columns() -> None:
    assert set(raw_events.columns.keys()) == {
        "occurred_at",
        "received_at",
        "event_type",
        "event_version",
        "actor_id",
        "payload",
    }


def test_raw_events_nullability() -> None:
    assert raw_events.columns["occurred_at"].nullable is False
    assert raw_events.columns["event_type"].nullable is False
    assert raw_events.columns["event_version"].nullable is False
    assert raw_events.columns["payload"].nullable is False
    assert raw_events.columns["actor_id"].nullable is True


def test_raw_events_has_no_primary_key() -> None:
    assert len(raw_events.primary_key.columns) == 0
