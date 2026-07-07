"""Tests for the centralized logging library (sparkth.lib.log)."""

import logging

import pytest

from sparkth.lib.log import configure_logging, get_logger


def test_get_logger_is_namespaced_under_sparkth() -> None:
    log = get_logger("example.module")
    assert isinstance(log, logging.Logger)
    assert log.name == "sparkth.example.module"


def test_get_logger_does_not_double_prefix_sparkth_names() -> None:
    # Modules pass ``__name__`` (e.g. "sparkth.main"), which is already under the
    # sparkth namespace — it must not become "sparkth.sparkth.main".
    assert get_logger("sparkth.main").name == "sparkth.main"
    assert get_logger("sparkth").name == "sparkth"


def test_get_logger_returns_same_instance() -> None:
    assert get_logger("example.same") is get_logger("example.same")


def test_configure_logging_sets_up_root_handler() -> None:
    root = logging.getLogger()
    # Drop any pre-existing handlers so we observe configure_logging's effect.
    original_handlers = list(root.handlers)
    root.handlers.clear()

    try:
        configure_logging()

        assert root.handlers, "configure_logging should install a root handler"
        assert root.level == logging.INFO
    finally:
        # Restore handlers
        root.handlers = original_handlers


def test_get_logger_records_propagate_to_root(caplog: pytest.LogCaptureFixture) -> None:
    configure_logging()
    log = get_logger("example.propagation")
    with caplog.at_level(logging.INFO):
        log.info("hello from sparkth")
    assert any(record.message == "hello from sparkth" for record in caplog.records)
