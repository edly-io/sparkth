from typing import Any

from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core_plugins.chat.cache import get_cache_service
from app.core_plugins.chat.encryption import get_encryption_service
from app.core_plugins.chat.models import ProviderAPIKey
from app.core_plugins.chat.routes import get_chat_system_config
from app.core_plugins.chat.service import ChatService
from app.services.plugin_adapters.base import PluginConfigAdapter


class ChatPluginConfigAdapter(PluginConfigAdapter):
    async def preprocess_config(
        self,
        *,
        session: AsyncSession,
        user_id: int,
        incoming_config: dict[str, Any],
    ) -> dict[str, Any]:
        """
        Intercepts raw user input before validation/persistence.
        Extracts `api_key`, stores it in ProviderAPIKey, and replaces it
        with the resulting `provider_api_key_ref` (the DB row ID).
        """
        config = dict(incoming_config)
        api_key = config.pop("api_key", None)
        provider = config.get("provider")

        db_key: ProviderAPIKey | None = None
        if provider:
            result = await session.exec(
                select(ProviderAPIKey).where(
                    ProviderAPIKey.user_id == user_id,
                    ProviderAPIKey.provider == provider,
                    ProviderAPIKey.is_active == True,
                )
            )
            db_key = result.one_or_none()

        # Guard 1: no key provided — preserve existing ref rather than dropping it.
        # Guard 2: key matches the stored masked value — the frontend echoed back the
        #          display string without the user touching the field; do not re-encrypt.
        if not api_key or (db_key is not None and api_key == db_key.masked_key):
            if db_key is not None:
                config["provider_api_key_ref"] = db_key.id
            return config

        if not provider:
            raise ValueError("Provider is required when api_key is provided")

        system_config = get_chat_system_config()
        service = ChatService(
            encryption_service=get_encryption_service(system_config.encryption_key),
            cache_service=get_cache_service(
                system_config.redis_url,
                system_config.redis_key_ttl,
            ),
        )

        db_key = await service.create_api_key(
            session=session,
            user_id=user_id,
            provider=provider,
            api_key=api_key,
        )

        config["provider_api_key_ref"] = db_key.id
        return config

    async def postprocess_config(
        self,
        *,
        session: AsyncSession,
        user_id: int,
        stored_config: dict[str, Any],
    ) -> dict[str, Any]:
        """
        Sanitises config before returning it to the client.
        Replaces the internal `provider_api_key_ref` ID with:
          - `api_key`: e.g. "sk-...abcd", or None if no key stored
        """
        config = dict(stored_config)
        ref = config.pop("provider_api_key_ref", None)

        if ref is not None:
            statement = select(ProviderAPIKey).where(
                ProviderAPIKey.id == ref,
                ProviderAPIKey.user_id == user_id,
                ProviderAPIKey.is_active == True,
            )
            result = await session.exec(statement)
            db_key = result.one_or_none()
            config["api_key"] = db_key.masked_key if db_key is not None else None
        else:
            config["api_key"] = None

        return config

    async def sync_cache(
        self,
        *,
        session: AsyncSession,
        user_id: int,
        stored_config: dict[str, Any],
    ) -> None:
        ref = stored_config.get("provider_api_key_ref")
        provider = stored_config.get("provider")
        if not ref or not provider:
            return

        statement = select(ProviderAPIKey).where(
            ProviderAPIKey.id == ref,
            ProviderAPIKey.user_id == user_id,
            ProviderAPIKey.is_active == True,
        )
        result = await session.exec(statement)
        db_key = result.one_or_none()
        if not db_key:
            return

        system_config = get_chat_system_config()
        cache = get_cache_service(system_config.redis_url, system_config.redis_key_ttl)
        cache_key = cache.make_key("api_key", str(user_id), provider)
        await cache.set(cache_key, db_key.encrypted_key)
