from typing import Any

from sqlmodel.ext.asyncio.session import AsyncSession

from sparkth.lib.plugins import ConfigAdapter
from sparkth.plugins.openedx.client import access_token_cache


class OpenEdxConfigAdapter(ConfigAdapter):
    """Drops the user's cached Open edX access token when their settings are saved.

    The token was granted with the previous credentials, so the next call must grant a new one.
    """

    async def sync_cache(self, *, session: AsyncSession, user_id: int, stored_config: dict[str, Any]) -> None:
        cache, key = access_token_cache(user_id)
        await cache.delete(key)
