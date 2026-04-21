"""Shared plugin adapter base for plugins that reference an LLMConfig."""

from typing import Any

from sqlmodel import col, select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.models.llm import LLMConfig
from app.services.plugin_adapters.base import PluginConfigAdapter


class LLMConfigPluginAdapter(PluginConfigAdapter):
    """Base adapter for plugins that hold an optional llm_config_id reference.

    preprocess_config: validates the referenced LLMConfig is owned by the user.
    postprocess_config: resolves llm_config_id to name/provider/model for the frontend.
    """

    async def preprocess_config(
        self,
        *,
        session: AsyncSession,
        user_id: int,
        incoming_config: dict[str, Any],
    ) -> dict[str, Any]:
        config_id = incoming_config.get("llm_config_id")
        if config_id is None:
            return incoming_config

        result = await session.exec(
            select(LLMConfig).where(
                LLMConfig.id == config_id,
                LLMConfig.user_id == user_id,
                col(LLMConfig.is_deleted) == False,  # noqa: E712
                col(LLMConfig.is_active) == True,  # noqa: E712
            )
        )
        if result.first() is None:
            raise ValueError(f"llm_config_id {config_id} not found or does not belong to this user.")
        return incoming_config

    async def postprocess_config(
        self,
        *,
        session: AsyncSession,
        user_id: int,
        stored_config: dict[str, Any],
    ) -> dict[str, Any]:
        config = dict(stored_config)
        config_id = config.get("llm_config_id")

        if config_id is None:
            config.update({"llm_config_name": None, "llm_provider": None, "llm_model": None})
            return config

        result = await session.exec(
            select(LLMConfig).where(
                LLMConfig.id == config_id,
                LLMConfig.user_id == user_id,
                col(LLMConfig.is_deleted) == False,  # noqa: E712
                col(LLMConfig.is_active) == True,  # noqa: E712
            )
        )
        llm = result.first()
        if llm is None:
            config.update({"llm_config_name": None, "llm_provider": None, "llm_model": None})
        else:
            config.update(
                {
                    "llm_config_name": llm.name,
                    "llm_provider": llm.provider,
                    "llm_model": llm.model,
                }
            )
        return config

    async def sync_cache(
        self,
        *,
        session: AsyncSession,
        user_id: int,
        stored_config: dict[str, Any],
    ) -> None:
        pass
