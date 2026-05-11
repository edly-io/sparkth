"""LLMConfigService — CRUD and key resolution for LLMConfig."""

from datetime import datetime, timezone

from sqlalchemy.exc import IntegrityError
from sqlmodel import col, select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.cache import CacheService, get_cache_service
from app.core.config import get_settings
from app.core.encryption import EncryptionService, get_encryption_service
from app.core.logger import get_logger
from app.llm.exceptions import (
    LLMConfigDuplicateNameError,
    LLMConfigInactiveError,
    LLMConfigModelNotSetError,
    LLMConfigNotFoundError,
    LLMConfigValidationError,
)
from app.llm.providers import get_models_for_provider
from app.models.llm import LLMConfig

logger = get_logger(__name__)

_CACHE_PREFIX = "llm_config"


class LLMConfigService:
    def __init__(self, encryption: EncryptionService, cache: CacheService) -> None:
        """Initialize with encryption and cache services."""
        self.encryption = encryption
        self.cache = cache

    @staticmethod
    def mask_key(api_key: str) -> str:
        """Return a masked version of the API key, preserving the provider prefix and last 4 chars."""
        if len(api_key) <= 4:
            return "****"
        suffix = api_key[-4:]
        parts = api_key.split("-", maxsplit=1)
        prefix = parts[0] + "-" if len(parts) >= 2 else ""
        return f"{prefix}****{suffix}"

    async def create(
        self,
        session: AsyncSession,
        user_id: int,
        name: str,
        provider: str,
        model: str,
        api_key: str,
    ) -> LLMConfig:
        """Create a new LLM config, encrypting the API key. Raises ValueError on duplicate name."""
        config = LLMConfig(
            user_id=user_id,
            name=name,
            provider=provider.lower(),
            model=model,
            encrypted_key=self.encryption.encrypt(api_key),
            masked_key=self.mask_key(api_key),
        )
        session.add(config)
        try:
            await session.flush()
        except IntegrityError as exc:
            await session.rollback()
            raise LLMConfigDuplicateNameError(name) from exc
        await session.refresh(config)
        logger.info("Created LLMConfig id=%s for user_id=%s provider=%s", config.id, user_id, provider)
        return config

    async def list(self, session: AsyncSession, user_id: int) -> list[LLMConfig]:
        """Return all non-deleted and active LLM configs for a user, newest first."""
        result = await session.exec(
            select(LLMConfig)
            .where(
                col(LLMConfig.user_id) == user_id,
                col(LLMConfig.is_deleted) == False,  # noqa: E712
                col(LLMConfig.is_active) == True,  # noqa: E712
            )
            .order_by(col(LLMConfig.created_at).desc())
        )
        return list(result.all())

    async def get(self, session: AsyncSession, user_id: int, config_id: int) -> LLMConfig | None:
        """Fetch a single non-deleted LLM config by ID and user, or None if not found."""
        result = await session.exec(
            select(LLMConfig).where(
                LLMConfig.id == config_id,
                col(LLMConfig.user_id) == user_id,
                col(LLMConfig.is_deleted) == False,  # noqa: E712
            )
        )
        return result.first()

    async def update(
        self,
        session: AsyncSession,
        user_id: int,
        config_id: int,
        name: str | None = None,
        model: str | None = None,
    ) -> LLMConfig:
        """Update name and/or model of an existing config. Raises ValueError if not found or duplicate name."""
        config = await self.get(session, user_id, config_id)
        if config is None:
            raise LLMConfigNotFoundError(config_id, user_id)
        if name is not None:
            config.name = name
        if model is not None:
            allowed = get_models_for_provider(config.provider)
            if model not in allowed:
                raise LLMConfigValidationError(
                    f"Model '{model}' not available for provider '{config.provider}'. Allowed: {', '.join(allowed)}"
                )
            config.model = model
        config.update_timestamp()
        session.add(config)
        try:
            await session.flush()
        except IntegrityError as exc:
            await session.rollback()
            raise LLMConfigDuplicateNameError(config.name) from exc
        await session.refresh(config)
        logger.info("Updated LLMConfig id=%s for user_id=%s", config.id, user_id)
        return config

    async def rotate_key(
        self,
        session: AsyncSession,
        user_id: int,
        config_id: int,
        api_key: str,
    ) -> LLMConfig:
        """Replace the API key for a config, updating encryption and invalidating cache."""
        config = await self.get(session, user_id, config_id)
        if config is None:
            raise LLMConfigNotFoundError(config_id, user_id)
        config.encrypted_key = self.encryption.encrypt(api_key)
        config.masked_key = self.mask_key(api_key)
        config.update_timestamp()
        session.add(config)
        await session.flush()
        await session.refresh(config)
        cache_key = self.cache.make_key(_CACHE_PREFIX, str(user_id), str(config_id))
        await self.cache.delete(cache_key)
        return config

    async def delete(self, session: AsyncSession, user_id: int, config_id: int) -> bool:
        """Soft-delete a config and evict its cache entry. Returns False if not found."""
        config = await self.get(session, user_id, config_id)
        if config is None:
            return False
        config.soft_delete()
        session.add(config)
        await session.flush()
        cache_key = self.cache.make_key(_CACHE_PREFIX, str(user_id), str(config_id))
        await self.cache.delete(cache_key)
        logger.info("Soft-deleted LLMConfig id=%s for user_id=%s", config_id, user_id)
        return True

    async def set_active(self, session: AsyncSession, user_id: int, config_id: int, is_active: bool) -> LLMConfig:
        """Activate or deactivate a config. Bypasses the is_active filter so inactive configs can be re-activated."""
        result = await session.exec(
            select(LLMConfig).where(
                LLMConfig.id == config_id,
                col(LLMConfig.user_id) == user_id,
                col(LLMConfig.is_deleted) == False,  # noqa: E712
            )
        )
        config = result.first()
        if config is None:
            raise LLMConfigNotFoundError(config_id, user_id)
        config.is_active = is_active
        config.update_timestamp()
        session.add(config)
        await session.flush()
        await session.refresh(config)
        logger.info("Set LLMConfig id=%s is_active=%s for user_id=%s", config_id, is_active, user_id)
        return config

    async def resolve(self, session: AsyncSession, user_id: int, config_id: int) -> tuple[LLMConfig, str]:
        """Return (config, decrypted_api_key). Caches by (user_id, config_id). Updates last_used_at."""
        config = await self.get(session, user_id, config_id)
        if config is None:
            raise LLMConfigNotFoundError(config_id, user_id)
        if not config.model:
            raise LLMConfigModelNotSetError(
                f"LLMConfig {config_id} has no model set. Update it via PATCH /api/v1/llm/configs/{config_id} before use."
            )
        if not config.is_active:
            raise LLMConfigInactiveError(config_id, user_id)
        cache_key = self.cache.make_key(_CACHE_PREFIX, str(user_id), str(config_id))
        cached = await self.cache.get(cache_key)
        if cached:
            try:
                return config, self.encryption.decrypt(cached)
            except ValueError as exc:
                logger.warning("Cached key for config_id=%s invalid, evicting: %s", config_id, exc)
                await self.cache.delete(cache_key)

        decrypted = self.encryption.decrypt(config.encrypted_key)
        await self.cache.set(cache_key, config.encrypted_key)
        config.last_used_at = datetime.now(timezone.utc)
        session.add(config)
        await session.flush()
        return config, decrypted


def get_llm_service() -> LLMConfigService:
    settings = get_settings()
    return LLMConfigService(
        encryption=get_encryption_service(settings.LLM_ENCRYPTION_KEY),
        cache=get_cache_service(settings.REDIS_URL, settings.REDIS_KEY_TTL),
    )
