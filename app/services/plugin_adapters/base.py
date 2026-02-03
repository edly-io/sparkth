from typing import Protocol

from sqlalchemy.ext.asyncio import AsyncSession


class PluginConfigAdapter(Protocol):
    async def preprocess_config(
        self,
        *,
        session: AsyncSession,
        user_id: int,
        incoming_config: dict[str, any],
    ) -> dict[str, any]:
        return incoming_config

    async def postprocess_config(
        self,
        *,
        session: AsyncSession,
        user_id: int,
        stored_config: dict[str, any],
    ) -> dict[str, any]:
        return stored_config
