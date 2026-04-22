"""Memory profiling utilities for the RAG pipeline.

Provides an async context manager that measures peak Python allocations
(tracemalloc), RSS delta (psutil), and wall-clock duration for a named stage.
Emits one structured log line per stage when MEMORY_PROFILING_ENABLED is true.
"""

import asyncio
import logging
import logging.handlers
import time
import tracemalloc
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any, AsyncGenerator

import psutil

from app.core.config import get_settings
from app.core.logger import get_logger

logger = get_logger(__name__)


def _find_project_root(start: Path | None = None) -> Path:
    """Find project root by searching upward for pyproject.toml."""
    current = start or Path(__file__).resolve().parent
    while current != current.parent:
        if (current / "pyproject.toml").exists():
            return current
        current = current.parent
    # Fallback: use current directory if no marker found
    return Path(__file__).resolve().parent.parent.parent


# Logs directory and file path (created lazily when profiling is enabled)
PROJECT_ROOT = _find_project_root()
LOG_DIR = PROJECT_ROOT / "logs"
LOG_FILE_PATH = LOG_DIR / "ram-logs.txt"

# Nesting depth counter for tracemalloc start/stop — prevents inner profilers
# from stopping tracemalloc while an outer profiler is still measuring.
_tracing_depth: int = 0

# Lazy-initialized logger and handler (set up only when profiling is enabled)
_memprof_handler: logging.handlers.RotatingFileHandler | None = None
_memprof_logger: logging.Logger | None = None


def _ensure_log_dir_and_handler() -> None:
    """Create logs directory and set up rotating file handler (called only when profiling is active)."""
    global _memprof_handler, _memprof_logger

    LOG_DIR.mkdir(parents=True, exist_ok=True)

    if _memprof_handler is None:
        _memprof_handler = logging.handlers.RotatingFileHandler(
            LOG_FILE_PATH,
            maxBytes=1 * 1024 * 1024,  # 1MB
            backupCount=5,
            encoding="utf-8",
        )
        _memprof_logger = logging.getLogger("sparkth.app.rag.memory_profiler.file")
        _memprof_logger.setLevel(logging.INFO)
        _memprof_logger.addHandler(_memprof_handler)
        _memprof_logger.propagate = False  # Don't duplicate to console logger


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

    _ensure_log_dir_and_handler()

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

        # Log to console (sync - fast, no I/O)
        logger.info(log_line)

        # Log to file with rotation (offloaded to thread pool to avoid blocking event loop)
        assert _memprof_logger is not None  # noqa: S101  # Set by _ensure_log_dir_and_handler()
        asyncio.create_task(asyncio.to_thread(_memprof_logger.info, log_line))


def log_memory_snapshot(label: str, **extra: Any) -> None:
    """Emit a one-shot RSS sample as a MEMPROF log line."""
    if not get_settings().MEMORY_PROFILING_ENABLED:
        return

    _ensure_log_dir_and_handler()

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

    # Log to console (sync - fast, no I/O)
    logger.info(log_line)

    # Log to file with rotation
    # Offload to thread pool if there's a running event loop, otherwise write sync
    assert _memprof_logger is not None  # noqa: S101  # Set by _ensure_log_dir_and_handler()
    try:
        asyncio.get_running_loop()
        asyncio.create_task(asyncio.to_thread(_memprof_logger.info, log_line))
    except RuntimeError:
        # No running event loop (sync call) - write synchronously
        _memprof_logger.info(log_line)
