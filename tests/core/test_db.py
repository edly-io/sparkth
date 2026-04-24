"""Tests for database engine configuration."""

import inspect


def test_async_engine_has_explicit_pool_config() -> None:
    """Verify async_engine is created with explicit pool_size and max_overflow."""
    # Verify the source code contains the pool configuration parameters
    import app.core.db

    source = inspect.getsource(app.core.db)

    # Check that the source code contains the pool configuration parameters
    assert "pool_size=3" in source
    assert "max_overflow=2" in source
    assert "pool_recycle=1800" in source

    # Verify the engine is actually created and usable
    from app.core.db import async_engine

    assert async_engine is not None
