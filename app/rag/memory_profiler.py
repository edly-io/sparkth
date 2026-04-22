"""Memory profiling utilities for the RAG pipeline.

Provides an async context manager that measures peak Python allocations
(tracemalloc), RSS delta (psutil), and wall-clock duration for a named stage.
Emits one structured log line per stage when MEMORY_PROFILING_ENABLED is true.
"""

import time
import tracemalloc
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any, AsyncGenerator

import psutil

from app.core.config import get_settings
from app.core.logger import get_logger

logger = get_logger(__name__)

# Ensure logs directory exists and write to logs/ram-logs.txt
LOG_FILE_PATH = Path(__file__).parent.parent.parent / "logs" / "ram-logs.txt"
LOG_FILE_PATH.parent.mkdir(parents=True, exist_ok=True)

# Nesting depth counter for tracemalloc start/stop — prevents inner profilers
# from stopping tracemalloc while an outer profiler is still measuring.
_tracing_depth: int = 0


def clear_ram_logs() -> None:
    """Clear the RAM profiling log file."""
    if LOG_FILE_PATH.exists():
        LOG_FILE_PATH.unlink()
        logger.info("Cleared RAM logs file")


def _fmt(value: Any) -> str:
    """Format a profiling value — None becomes '-'."""
    return "-" if value is None else str(value)


def _build_log_line(stage: str, extra: dict[str, Any], **fields: Any) -> str:
    """Build a MEMPROF log line from stage name, extra kwargs, and computed fields."""
    parts = [f"stage={stage}"]
    for k, v in extra.items():
        parts.append(f"{k}={_fmt(v)}")
    for k, v in fields.items():
        parts.append(f"{k}={_fmt(v)}")
    return "MEMPROF " + " ".join(parts)


@asynccontextmanager
async def profile_memory(stage: str, **extra: Any) -> AsyncGenerator[None, None]:
    """Async context manager that profiles memory for a named pipeline stage.

    Safe for nested use: uses a reference counter for tracemalloc start/stop
    and snapshot diffs instead of reset_peak() so inner profilers don't
    corrupt outer measurements.
    """
    global _tracing_depth

    if not get_settings().MEMORY_PROFILING_ENABLED:
        yield
        return

    if not tracemalloc.is_tracing():
        tracemalloc.start()
    _tracing_depth += 1

    # Snapshot baseline — diff after yield instead of reset_peak
    peak_before: int | None = None
    current_before: int | None = None
    if tracemalloc.is_tracing():
        current_before, peak_before = tracemalloc.get_traced_memory()

    rss_start: float | None = None
    try:
        rss_start = psutil.Process().memory_info().rss / (1024 * 1024)
    except psutil.Error:
        rss_start = None

    t0 = time.perf_counter()

    try:
        yield
    finally:
        duration_ms = round((time.perf_counter() - t0) * 1000, 1)

        peak_delta_kb: float | None = None
        current_delta_kb: float | None = None
        if tracemalloc.is_tracing() and peak_before is not None and current_before is not None:
            current_after, peak_after = tracemalloc.get_traced_memory()
            peak_delta_kb = round((peak_after - peak_before) / 1024, 1)
            current_delta_kb = round((current_after - current_before) / 1024, 1)

        _tracing_depth -= 1
        if _tracing_depth == 0 and tracemalloc.is_tracing():
            tracemalloc.stop()

        rss_end: float | None = None
        try:
            rss_end = psutil.Process().memory_info().rss / (1024 * 1024)
        except psutil.Error:
            rss_end = None

        rss_delta: float | None = None
        if rss_start is not None and rss_end is not None:
            rss_delta = round(rss_end - rss_start, 1)

        log_line = _build_log_line(
            stage,
            extra,
            duration_ms=duration_ms,
            py_peak_delta_kb=peak_delta_kb,
            py_current_delta_kb=current_delta_kb,
            rss_start_mb=round(rss_start, 1) if rss_start is not None else None,
            rss_end_mb=round(rss_end, 1) if rss_end is not None else None,
            rss_delta_mb=rss_delta,
        )

        # Log to console
        logger.info(log_line)

        # Log to file
        with open(LOG_FILE_PATH, "a", encoding="utf-8") as f:
            f.write(log_line + "\n")


def log_memory_snapshot(label: str, **extra: Any) -> None:
    """Emit a one-shot RSS sample as a MEMPROF log line."""
    if not get_settings().MEMORY_PROFILING_ENABLED:
        return

    rss_mb: float | None = None
    try:
        rss_mb = round(psutil.Process().memory_info().rss / (1024 * 1024), 1)
    except psutil.Error:
        rss_mb = None

    log_line = _build_log_line(
        "snapshot",
        {"label": label, **extra},
        rss_mb=rss_mb,
    )

    # Log to console
    logger.info(log_line)

    # Log to file
    with open(LOG_FILE_PATH, "a", encoding="utf-8") as f:
        f.write(log_line + "\n")
