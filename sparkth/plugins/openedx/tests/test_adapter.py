from httpx import AsyncClient
from sqlmodel.ext.asyncio.session import AsyncSession

from sparkth.core.models.plugin import Plugin
from sparkth.core.models.user import User
from sparkth.plugins.openedx.adapter import OpenEdxConfigAdapter
from sparkth.plugins.openedx.client import access_token_cache
from sparkth.plugins.openedx.constants import OPENEDX_PLUGIN_NAME
from sparkth.plugins.openedx.tests.conftest import OPENEDX_CONFIG, FakeRedis


async def seed_tokens(*user_ids: int) -> None:
    for user_id in user_ids:
        cache, key = access_token_cache(user_id)
        await cache.set(key, f"token-{user_id}")


async def test_saving_settings_drops_only_that_users_cached_token(fake_redis: FakeRedis, session: AsyncSession) -> None:
    await seed_tokens(1, 2)

    await OpenEdxConfigAdapter().sync_cache(session=session, user_id=1, stored_config={})

    assert set(fake_redis.store) == {"openedx:access-token:2"}


async def test_the_config_route_drops_the_cached_token(
    fake_redis: FakeRedis, client: AsyncClient, current_user: User, session: AsyncSession
) -> None:
    session.add(Plugin(name=OPENEDX_PLUGIN_NAME, is_core=True, enabled=True))
    await session.commit()
    await seed_tokens(current_user.id or 0)

    response = await client.put(
        f"/api/v1/user-plugins/{OPENEDX_PLUGIN_NAME}/config", json={"config": OPENEDX_CONFIG.model_dump(mode="json")}
    )

    assert response.status_code == 200
    assert fake_redis.store == {}
