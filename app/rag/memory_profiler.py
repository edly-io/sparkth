"""Memory profiling utilities for the RAG pipeline.

Provides an async context manager that measures peak Python allocations
(tracemalloc), RSS delta (psutil), and wall-clock duration for a named stage.
Emits one structured log line per stage when MEMORY_PROFILING_ENABLED is true.
"""

import time
import tracemalloc
from contextlib import asynccontextmanager
from typing import Any, AsyncGenerator

import psutil

from app.core.config import get_settings
from app.core.logger import get_logger

logger = get_logger(__name__)


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
    """Async context manager that profiles memory for a named pipeline stage."""
    if not get_settings().MEMORY_PROFILING_ENABLED:
        yield
        return

    started_tracing = False
    if not tracemalloc.is_tracing():
        tracemalloc.start()
        started_tracing = True

    tracemalloc.reset_peak()

    rss_start: float | None = None
    rss_end: float | None = None
    try:
        rss_start = psutil.Process().memory_info().rss / (1024 * 1024)
    except psutil.Error:
        rss_start = None

    t0 = time.perf_counter()

    try:
        yield
    finally:
        duration_ms = round((time.perf_counter() - t0) * 1000, 1)

        current_kb: float | None = None
        peak_kb: float | None = None
        if tracemalloc.is_tracing():
            current, peak = tracemalloc.get_traced_memory()
            current_kb = round(current / 1024, 1)
            peak_kb = round(peak / 1024, 1)

        if started_tracing and tracemalloc.is_tracing():
            tracemalloc.stop()

        try:
            rss_end = psutil.Process().memory_info().rss / (1024 * 1024)
        except psutil.Error:
            rss_end = None

        rss_delta: float | None = None
        if rss_start is not None and rss_end is not None:
            rss_delta = round(rss_end - rss_start, 1)

        logger.info(
            _build_log_line(
                stage,
                extra,
                duration_ms=duration_ms,
                py_peak_kb=peak_kb,
                py_current_kb=current_kb,
                rss_start_mb=round(rss_start, 1) if rss_start is not None else None,
                rss_end_mb=round(rss_end, 1) if rss_end is not None else None,
                rss_delta_mb=rss_delta,
            )
        )


def log_memory_snapshot(label: str, **extra: Any) -> None:
    """Emit a one-shot RSS sample as a MEMPROF log line."""
    if not get_settings().MEMORY_PROFILING_ENABLED:
        return

    rss_mb: float | None = None
    try:
        rss_mb = round(psutil.Process().memory_info().rss / (1024 * 1024), 1)
    except psutil.Error:
        rss_mb = None

    logger.info(
        _build_log_line(
            "snapshot",
            {"label": label, **extra},
            rss_mb=rss_mb,
        )
    )
