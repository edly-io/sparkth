from pathlib import Path


def test_migration_drops_scope_check_constraint() -> None:
    versions = Path(__file__).parent.parent.parent / "sparkth" / "migrations" / "app" / "versions"
    matches = [
        p
        for p in versions.glob("*.py")
        if "ck_role_assignment_scope" in p.read_text() and "drop_constraint" in p.read_text()
    ]
    assert matches, "a migration dropping ck_role_assignment_scope must exist"
