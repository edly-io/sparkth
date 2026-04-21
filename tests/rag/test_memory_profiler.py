"""Tests for the memory profiler utility."""

import logging

import pytest

from app.rag.memory_profiler import log_memory_snapshot, profile_memory


def _make_settings(enabled: bool) -> object:
    """Create a lightweight settings stub with MEMORY_PROFILING_ENABLED."""

    class _Stub:
        MEMORY_PROFILING_ENABLED: bool = enabled

    return _Stub()


@pytest.fixture(autouse=True)
def _enable_propagation() -> None:
    """Allow caplog to capture logs from the sparkth logger tree."""
    logging.getLogger("sparkth").propagate = True


class TestProfileMemoryDisabled:
    """When profiling is disabled, the context manager is a no-op."""

    async def test_no_log_when_disabled(self, caplog: pytest.LogCaptureFixture) -> None:
        monkeypatch = pytest.MonkeyPatch()
        monkeypatch.setattr(
            "app.rag.memory_profiler.get_settings",
            lambda: _make_settings(False),
        )
        try:
            with caplog.at_level(logging.INFO):
                async with profile_memory("test_stage"):
                    pass
        finally:
            monkeypatch.undo()

        assert not any("MEMPROF" in r.message for r in caplog.records)

    async def test_block_still_executes_when_disabled(self) -> None:
        monkeypatch = pytest.MonkeyPatch()
        monkeypatch.setattr(
            "app.rag.memory_profiler.get_settings",
            lambda: _make_settings(False),
        )
        try:
            executed = False
            async with profile_memory("test_stage"):
                executed = True
        finally:
            monkeypatch.undo()

        assert executed


class TestProfileMemoryEnabled:
    """When profiling is enabled, one MEMPROF line is emitted."""

    async def test_emits_memprof_line(self, caplog: pytest.LogCaptureFixture) -> None:
        monkeypatch = pytest.MonkeyPatch()
        monkeypatch.setattr(
            "app.rag.memory_profiler.get_settings",
            lambda: _make_settings(True),
        )
        try:
            with caplog.at_level(logging.INFO):
                async with profile_memory("test_stage", file="doc.pdf"):
                    pass
        finally:
            monkeypatch.undo()

        memprof_lines = [r.message for r in caplog.records if "MEMPROF" in r.message]
        assert len(memprof_lines) == 1
        line = memprof_lines[0]

        assert "stage=test_stage" in line
        assert "file=doc.pdf" in line
        assert "duration_ms=" in line
        assert "py_peak_kb=" in line
        assert "py_current_delta_kb=" in line
        assert "rss_start_mb=" in line
        assert "rss_end_mb=" in line
        assert "rss_delta_mb=" in line

    async def test_formats_none_as_dash(self, caplog: pytest.LogCaptureFixture) -> None:
        monkeypatch = pytest.MonkeyPatch()
        monkeypatch.setattr(
            "app.rag.memory_profiler.get_settings",
            lambda: _make_settings(True),
        )
        try:
            with caplog.at_level(logging.INFO):
                async with profile_memory("test_stage", file=None):
                    pass
        finally:
            monkeypatch.undo()

        memprof_lines = [r.message for r in caplog.records if "MEMPROF" in r.message]
        assert len(memprof_lines) == 1
        assert "file=-" in memprof_lines[0]


class TestProfileMemoryExceptionHandling:
    """Log line is emitted even when the block raises, and the exception propagates."""

    async def test_log_on_exception(self, caplog: pytest.LogCaptureFixture) -> None:
        monkeypatch = pytest.MonkeyPatch()
        monkeypatch.setattr(
            "app.rag.memory_profiler.get_settings",
            lambda: _make_settings(True),
        )
        try:
            with caplog.at_level(logging.INFO):
                with pytest.raises(ValueError, match="boom"):
                    async with profile_memory("failing_stage"):
                        raise ValueError("boom")
        finally:
            monkeypatch.undo()

        memprof_lines = [r.message for r in caplog.records if "MEMPROF" in r.message]
        assert len(memprof_lines) == 1
        assert "stage=failing_stage" in memprof_lines[0]


class TestLogMemorySnapshot:
    """log_memory_snapshot emits a one-shot RSS sample."""

    def test_no_log_when_disabled(self, caplog: pytest.LogCaptureFixture) -> None:
        monkeypatch = pytest.MonkeyPatch()
        monkeypatch.setattr(
            "app.rag.memory_profiler.get_settings",
            lambda: _make_settings(False),
        )
        try:
            with caplog.at_level(logging.INFO):
                log_memory_snapshot("test_snap")
        finally:
            monkeypatch.undo()

        assert not any("MEMPROF" in r.message for r in caplog.records)

    def test_emits_snapshot_when_enabled(self, caplog: pytest.LogCaptureFixture) -> None:
        monkeypatch = pytest.MonkeyPatch()
        monkeypatch.setattr(
            "app.rag.memory_profiler.get_settings",
            lambda: _make_settings(True),
        )
        try:
            with caplog.at_level(logging.INFO):
                log_memory_snapshot("test_snap", extra_key="val")
        finally:
            monkeypatch.undo()

        memprof_lines = [r.message for r in caplog.records if "MEMPROF" in r.message]
        assert len(memprof_lines) == 1
        line = memprof_lines[0]
        assert "snapshot" in line
        assert "label=test_snap" in line
        assert "rss_mb=" in line
        assert "extra_key=val" in line
