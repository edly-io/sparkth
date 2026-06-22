"""Verify the migration to drop embedding columns was generated correctly."""

from pathlib import Path


def _find_migration_file() -> Path | None:
    """Find the migration file that drops embedding columns."""
    versions_dir = Path(__file__).parent.parent.parent / "app" / "migrations" / "app" / "versions"
    for f in versions_dir.glob("*.py"):
        content = f.read_text()
        if "drop_embedding_columns" in f.name or ("embedding" in content and "drop_column" in content):
            return f
    return None


def test_migration_file_exists() -> None:
    """A migration file dropping the embedding columns must exist."""
    migration = _find_migration_file()
    assert migration is not None, (
        "No migration file found. Run: alembic revision --autogenerate -m 'drop embedding columns from document_chunks'"
    )


def test_migration_drops_embedding_column() -> None:
    migration = _find_migration_file()
    assert migration is not None
    content = migration.read_text()
    assert "embedding" in content
    assert "drop_column" in content or "op.drop_column" in content
