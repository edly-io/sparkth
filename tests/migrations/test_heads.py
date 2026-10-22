"""Each Alembic lineage must resolve `head` to a single revision.

Two branches that each add a migration on the same parent split the lineage into
several heads, and `alembic upgrade head` then fails at deploy time with
`MultipleHeads`.
"""

import pytest
from alembic.config import Config
from alembic.script import ScriptDirectory


@pytest.mark.parametrize("config_file", ["alembic.ini", "alembic_analytics.ini"])
def test_lineage_has_a_single_head(config_file: str) -> None:
    script = ScriptDirectory.from_config(Config(config_file))

    assert script.get_current_head() is not None
