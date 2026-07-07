"""Tests for the centralized logging library (sparkth.lib.log)."""

import logging

import pytest

from sparkth.lib.log import configure_logging, get_logger


def test_get_logger_is_namespaced_under_sparkth() -> None:
    log = get_logger("app.example.module")
    assert isinstance(log, logging.Logger)
    assert log.name == "sparkth.app.example.module"


def test_get_logger_returns_same_instance() -> None:
    assert get_logger("app.same") is get_logger("app.same")


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
    log = get_logger("app.propagation")
    with caplog.at_level(logging.INFO):
        log.info("hello from sparkth")
    assert any(record.message == "hello from sparkth" for record in caplog.records)
