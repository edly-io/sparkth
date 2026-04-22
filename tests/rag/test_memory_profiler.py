"""Tests for the memory profiler utility."""

import logging
from pathlib import Path

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


@pytest.fixture(autouse=True)
def mock_log_file_path(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Redirect LOG_FILE_PATH to a temp file to avoid disk side effects."""
    temp_log = tmp_path / "ram-logs.txt"
    monkeypatch.setattr("app.rag.memory_profiler.LOG_FILE_PATH", temp_log)
    return temp_log


class TestProfileMemoryDisabled:
    """When profiling is disabled, the context manager is a no-op."""

    async def test_no_log_when_disabled(
        self, caplog: pytest.LogCaptureFixture, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(
            "app.rag.memory_profiler.get_settings",
            lambda: _make_settings(False),
        )
        with caplog.at_level(logging.INFO):
            async with profile_memory("test_stage"):
                pass

        assert not any("MEMPROF" in r.message for r in caplog.records)

    async def test_block_still_executes_when_disabled(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(
            "app.rag.memory_profiler.get_settings",
            lambda: _make_settings(False),
        )
        executed = False
        async with profile_memory("test_stage"):
            executed = True

        assert executed


class TestProfileMemoryEnabled:
    """When profiling is enabled, one MEMPROF line is emitted."""

    async def test_emits_memprof_line(self, caplog: pytest.LogCaptureFixture, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(
            "app.rag.memory_profiler.get_settings",
            lambda: _make_settings(True),
        )
        with caplog.at_level(logging.INFO):
            async with profile_memory("test_stage", file="doc.pdf"):
                pass

        memprof_lines = [r.message for r in caplog.records if "MEMPROF" in r.message]
        assert len(memprof_lines) == 1
        line = memprof_lines[0]

        assert "stage=test_stage" in line
        assert "file=doc.pdf" in line
        assert "duration_ms=" in line
        assert "py_peak_delta_kb=" in line
        assert "py_current_delta_kb=" in line
        assert "rss_start_mb=" in line
        assert "rss_end_mb=" in line
        assert "rss_delta_mb=" in line

    async def test_formats_none_as_dash(
        self, caplog: pytest.LogCaptureFixture, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(
            "app.rag.memory_profiler.get_settings",
            lambda: _make_settings(True),
        )
        with caplog.at_level(logging.INFO):
            async with profile_memory("test_stage", file=None):
                pass

        memprof_lines = [r.message for r in caplog.records if "MEMPROF" in r.message]
        assert len(memprof_lines) == 1
        assert "file=-" in memprof_lines[0]


class TestProfileMemoryExceptionHandling:
    """Log line is emitted even when the block raises, and the exception propagates."""

    async def test_log_on_exception(self, caplog: pytest.LogCaptureFixture, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(
            "app.rag.memory_profiler.get_settings",
            lambda: _make_settings(True),
        )
        with caplog.at_level(logging.INFO):
            with pytest.raises(ValueError, match="boom"):
                async with profile_memory("failing_stage"):
                    raise ValueError("boom")

        memprof_lines = [r.message for r in caplog.records if "MEMPROF" in r.message]
        assert len(memprof_lines) == 1
        assert "stage=failing_stage" in memprof_lines[0]


class TestNestedProfileMemory:
    """Nested profile_memory calls must not interfere with each other."""

    async def test_nested_profiling_emits_both_lines(
        self, caplog: pytest.LogCaptureFixture, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(
            "app.rag.memory_profiler.get_settings",
            lambda: _make_settings(True),
        )
        with caplog.at_level(logging.INFO):
            async with profile_memory("outer"):
                async with profile_memory("inner"):
                    pass

        memprof_lines = [r.message for r in caplog.records if "MEMPROF" in r.message]
        assert len(memprof_lines) == 2
        stages = [line.split("stage=")[1].split()[0] for line in memprof_lines]
        assert "inner" in stages
        assert "outer" in stages

    async def test_nested_profiling_inner_does_not_zero_outer_peak(
        self, caplog: pytest.LogCaptureFixture, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Inner reset_peak must not make outer py_peak_delta_kb negative or zero."""
        monkeypatch.setattr(
            "app.rag.memory_profiler.get_settings",
            lambda: _make_settings(True),
        )
        with caplog.at_level(logging.INFO):
            async with profile_memory("outer"):
                async with profile_memory("inner"):
                    pass

        memprof_lines = [r.message for r in caplog.records if "MEMPROF" in r.message]
        assert len(memprof_lines) == 2

        # Inner line is emitted first (inner exits first)
        inner_line = next(line for line in memprof_lines if "stage=inner" in line)
        outer_line = next(line for line in memprof_lines if "stage=outer" in line)

        # Both should have valid (not '-') peak delta values
        assert "py_peak_delta_kb=" in inner_line
        assert "py_peak_delta_kb=" in outer_line

        # Outer peak delta must not be '-' (which would happen if inner
        # called reset_peak and zeroed the outer measurement)
        outer_peak = outer_line.split("py_peak_delta_kb=")[1].split()[0]
        assert outer_peak != "-"

    async def test_tracemalloc_not_stopped_prematurely(
        self, caplog: pytest.LogCaptureFixture, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """After inner exits, tracemalloc must still be running for outer."""
        import tracemalloc

        monkeypatch.setattr(
            "app.rag.memory_profiler.get_settings",
            lambda: _make_settings(True),
        )
        with caplog.at_level(logging.INFO):
            async with profile_memory("outer"):
                async with profile_memory("inner"):
                    pass
                # tracemalloc should still be tracing here
                assert tracemalloc.is_tracing()


class TestLogMemorySnapshot:
    """log_memory_snapshot emits a one-shot RSS sample."""

    def test_no_log_when_disabled(self, caplog: pytest.LogCaptureFixture, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(
            "app.rag.memory_profiler.get_settings",
            lambda: _make_settings(False),
        )
        with caplog.at_level(logging.INFO):
            log_memory_snapshot("test_snap")

        assert not any("MEMPROF" in r.message for r in caplog.records)

    def test_emits_snapshot_when_enabled(
        self, caplog: pytest.LogCaptureFixture, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(
            "app.rag.memory_profiler.get_settings",
            lambda: _make_settings(True),
        )
        with caplog.at_level(logging.INFO):
            log_memory_snapshot("test_snap", extra_key="val")

        memprof_lines = [r.message for r in caplog.records if "MEMPROF" in r.message]
        assert len(memprof_lines) == 1
        line = memprof_lines[0]
        assert "snapshot" in line
        assert "label=test_snap" in line
        assert "rss_mb=" in line
        assert "extra_key=val" in line
