from typing import Any, Protocol

from sqlalchemy.ext.asyncio import AsyncSession


class PluginConfigAdapter(Protocol):
    async def preprocess_config(
        self,
        *,
        session: AsyncSession,
        user_id: int,
        incoming_config: dict[str, Any],
    ) -> dict[str, Any]:
        return incoming_config

    async def postprocess_config(
        self,
        *,
        stored_config: dict[str, Any],
    ) -> dict[str, Any]:
        return stored_config
