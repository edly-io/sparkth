from typing import Any

from sqlmodel.ext.asyncio.session import AsyncSession

from app.core_plugins.chat.cache import get_cache_service
from app.core_plugins.chat.encryption import get_encryption_service
from app.core_plugins.chat.routes import get_chat_system_config
from app.core_plugins.chat.service import ChatService


class ChatPluginConfigAdapter:
    async def preprocess_config(
        self,
        *,
        session: AsyncSession,
        user_id: int,
        incoming_config: dict[str, Any],
    ) -> dict[str, Any]:
        api_key = incoming_config.pop("api_key", None)
        provider = incoming_config.get("provider")

        if not api_key:
            return incoming_config

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

        incoming_config["provider_api_key_ref"] = db_key.id
        return incoming_config

    async def postprocess_config(
        self,
        *,
        stored_config: dict[str, Any],
    ) -> dict[str, Any]:
        config = dict(stored_config)
        config.pop("provider_api_key_id", None)

        if "provider" in config:
            config["has_api_key"] = True

        return config
