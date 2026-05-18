"""Shared plugin adapter base for plugins that reference an LLMConfig."""

from typing import Any

from sqlmodel import col, select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.llm.exceptions import LLMConfigValidationError
from app.llm.providers import get_models_for_provider
from app.models.llm import LLMConfig

_EMPTY_LLM_FIELDS: dict[str, None] = {"llm_config_name": None, "llm_provider": None, "llm_model": None}


class LLMConfigAdapter:
    """Base adapter for plugins that hold an optional llm_config_id reference.

    preprocess_config: validates the referenced LLMConfig is owned by the user.
    postprocess_config: resolves llm_config_id to name/provider/model for the frontend.
    """

    @staticmethod
    async def _fetch_llm_config_any(
        session: AsyncSession,
        user_id: int,
        config_id: int,
    ) -> LLMConfig | None:
        """Fetch a config regardless of is_active state (for preprocess validation)."""
        result = await session.exec(
            select(LLMConfig).where(
                LLMConfig.id == config_id,
                LLMConfig.user_id == user_id,
                col(LLMConfig.is_deleted) == False,  # noqa: E712
            )
        )
        return result.first()

    @staticmethod
    def _parse_config_id(raw: Any) -> int:
        """Convert a raw config_id value (int or str) to int, raising ValueError on bad input."""
        try:
            return int(raw)
        except (ValueError, TypeError) as exc:
            raise ValueError(f"llm_config_id must be an integer, got {raw!r}") from exc

    async def preprocess_config(
        self,
        *,
        session: AsyncSession,
        user_id: int,
        incoming_config: dict[str, Any],
    ) -> dict[str, Any]:
        raw_id = incoming_config.get("llm_config_id")
        model_override = incoming_config.get("llm_model_override")

        if raw_id is None:
            if model_override is not None:
                raise ValueError(
                    "llm_model_override requires llm_config_id to be set "
                    "(the provider cannot be determined without a linked LLM config)."
                )
            return incoming_config

        config_id = self._parse_config_id(raw_id)
        llm = await self._fetch_llm_config_any(session, user_id, config_id)
        if llm is None:
            raise ValueError(f"llm_config_id {config_id} not found or does not belong to this user.")
        if not llm.is_active:
            raise ValueError("This record is deactivated. Reactivate it in AI Keys or select a different config.")

        if model_override is not None:
            allowed = get_models_for_provider(llm.provider)
            if model_override not in allowed:
                raise LLMConfigValidationError(
                    f"Model '{model_override}' not available for provider '{llm.provider}'. "
                    f"Allowed: {', '.join(allowed)}"
                )

        return {**incoming_config, "llm_config_id": config_id}

    async def postprocess_config(
        self,
        *,
        session: AsyncSession,
        user_id: int,
        stored_config: dict[str, Any],
    ) -> dict[str, Any]:
        config = dict(stored_config)
        raw_id = config.get("llm_config_id")
        config_id: int | None = None
        if raw_id is not None:
            try:
                config_id = int(raw_id)
            except (ValueError, TypeError):
                config_id = None
        llm = await self._fetch_llm_config_any(session, user_id, config_id) if config_id is not None else None
        if llm is None:
            config.update(_EMPTY_LLM_FIELDS)
        else:
            config.update({"llm_config_name": llm.name, "llm_provider": llm.provider, "llm_model": llm.model})
        return config

    async def sync_cache(
        self,
        *,
        session: AsyncSession,
        user_id: int,
        stored_config: dict[str, Any],
    ) -> None:
        pass
