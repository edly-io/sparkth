from sqlalchemy import MetaData, text
from sqlmodel import SQLModel

from sparkth.core.analytics.db import get_analytics_engine
from sparkth.core.analytics.models import analytics_metadata
from sparkth.core.db import get_engine
from sparkth.lib.db import analytics_session_scope
from sparkth.lib.settings import get_settings


def test_settings_exposes_analytics_database_url() -> None:
    settings = get_settings()
    assert settings.ANALYTICS_DATABASE_URL
    assert settings.ANALYTICS_DATABASE_URL.startswith("sqlite+aiosqlite://")


def test_analytics_engine_is_distinct_from_app_engine() -> None:
    assert get_analytics_engine() is not get_engine()
    # the analytics engine is built from the analytics URL, not the app URL
    assert "aiosqlite" in str(get_analytics_engine().url)


async def test_analytics_session_scope_opens_working_session() -> None:
    async with analytics_session_scope() as session:
        result = await session.execute(text("SELECT 1"))
        assert result.scalar_one() == 1


def test_analytics_metadata_is_separate_from_sqlmodel_metadata() -> None:
    assert isinstance(analytics_metadata, MetaData)
    assert analytics_metadata is not SQLModel.metadata
