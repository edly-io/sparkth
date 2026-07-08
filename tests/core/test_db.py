"""Tests for database engine configuration."""

import inspect


def test_engine_has_explicit_pool_config() -> None:
    """Verify the engine is created with explicit pool_size and max_overflow."""
    # Verify the source code contains the pool configuration parameters
    import sparkth.core.db

    source = inspect.getsource(sparkth.core.db)

    # Check that the source code contains the pool configuration parameters
    assert "pool_size=3" in source
    assert "max_overflow=2" in source
    assert "pool_recycle=1800" in source

    # Verify the engine provider builds a usable engine
    from sparkth.core.db import get_engine

    assert get_engine() is not None
