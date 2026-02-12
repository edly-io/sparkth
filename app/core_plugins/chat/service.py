import json
from datetime import datetime
from typing import Any

from sqlmodel import col, select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.logger import get_logger
from app.core_plugins.chat.cache import CacheService
from app.core_plugins.chat.config import api_key_settings
from app.core_plugins.chat.encryption import EncryptionService
from app.core_plugins.chat.models import Conversation, Message, ProviderAPIKey

logger = get_logger(__name__)


class ChatService:
    def __init__(self, encryption_service: EncryptionService, cache_service: CacheService):
        self.encryption = encryption_service
        self.cache = cache_service

    async def create_api_key(self, session: AsyncSession, user_id: int, provider: str, api_key: str) -> ProviderAPIKey:
        encrypted_key = self.encryption.encrypt(api_key)

        db_key = ProviderAPIKey(
            user_id=user_id,
            provider=provider,
            encrypted_key=encrypted_key,
            is_active=True,
        )

        session.add(db_key)
        await session.commit()
        await session.refresh(db_key)

        logger.info(f"Created API key for user {user_id}, provider {provider}")

        cache_key = self.cache.make_key("api_key", str(user_id), provider)
        await self.cache.set(cache_key, api_key)

        return db_key

    async def get_api_key(self, session: AsyncSession, user_id: int, provider: str) -> str | None:
        cache_key = self.cache.make_key("api_key", str(user_id), provider)
        cached_key = await self.cache.get(cache_key)

        if cached_key:
            logger.debug(f"API key cache hit for user {user_id}, provider {provider}")
            return cached_key

        statement = select(ProviderAPIKey).where(
            ProviderAPIKey.user_id == user_id,
            ProviderAPIKey.provider == provider,
            ProviderAPIKey.is_active == True,  # noqa: E712
            ProviderAPIKey.deleted_at == None,
        )
        result = await session.exec(statement)
        db_key = result.first()

        if not db_key:
            env_key = api_key_settings.get_default_key()
            if env_key:
                logger.info("Using default API key from environment for Anthropic")
                await self.cache.set(cache_key, env_key)
                return env_key

            logger.warning(f"No API key found for user {user_id}, provider {provider}")
            return None

        try:
            decrypted_key = self.encryption.decrypt(db_key.encrypted_key)
            await self.cache.set(cache_key, decrypted_key)

            db_key.last_used_at = datetime.utcnow()
            session.add(db_key)
            await session.commit()

            return decrypted_key
        except Exception as e:
            logger.error(f"Failed to decrypt API key: {e}")
            return None

    async def list_api_keys(self, session: AsyncSession, user_id: int) -> list[ProviderAPIKey]:
        statement = select(ProviderAPIKey).where(
            ProviderAPIKey.user_id == user_id,
            ProviderAPIKey.deleted_at == None,
        )
        result = await session.exec(statement)
        return list(result.all())

    async def delete_api_key(self, session: AsyncSession, user_id: int, key_id: int) -> bool:
        statement = select(ProviderAPIKey).where(
            ProviderAPIKey.id == key_id,
            ProviderAPIKey.user_id == user_id,
            ProviderAPIKey.deleted_at == None,
        )
        result = await session.exec(statement)
        db_key = result.first()

        if not db_key:
            return False

        db_key.deleted_at = datetime.utcnow()
        session.add(db_key)
        await session.commit()

        cache_key = self.cache.make_key("api_key", str(user_id), db_key.provider)
        await self.cache.delete(cache_key)

        logger.info(f"Deleted API key {key_id} for user {user_id}")
        return True

    async def create_conversation(
        self,
        session: AsyncSession,
        user_id: int,
        api_key_id: int,
        provider: str,
        model: str,
        title: str | None = None,
        system_prompt: str | None = None,
        tools_config: str | None = None,
    ) -> Conversation:
        conversation = Conversation(
            user_id=user_id,
            api_key_id=api_key_id,
            provider=provider,
            model=model,
            title=title,
            system_prompt=system_prompt,
        )

        session.add(conversation)
        await session.commit()
        await session.refresh(conversation)

        logger.info(f"Created conversation {conversation.id} for user {user_id}")
        return conversation

    async def get_conversation(self, session: AsyncSession, conversation_id: int, user_id: int) -> Conversation | None:
        statement = select(Conversation).where(
            Conversation.id == conversation_id,
            Conversation.user_id == user_id,
            Conversation.deleted_at == None,
        )
        result = await session.exec(statement)
        return result.first()

    async def list_conversations(
        self, session: AsyncSession, user_id: int, limit: int = 50, offset: int = 0
    ) -> tuple[list[Conversation], int]:
        count_statement = select(Conversation).where(
            Conversation.user_id == user_id,
            Conversation.deleted_at == None,
        )
        count_result = await session.exec(count_statement)
        total = len(list(count_result.all()))

        statement = (
            select(Conversation)
            .where(
                Conversation.user_id == user_id,
                Conversation.deleted_at == None,
            )
            .order_by(col(Conversation.created_at).desc())
            .offset(offset)
            .limit(limit)
        )
        result = await session.exec(statement)
        conversations = list(result.all())

        return conversations, total

    async def add_message(
        self,
        session: AsyncSession,
        conversation_id: int,
        role: str,
        content: str,
        tokens_used: int | None = None,
        cost: float | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> Message:
        metadata_json = json.dumps(metadata) if metadata else None

        message = Message(
            conversation_id=conversation_id,
            role=role,
            content=content,
            tokens_used=tokens_used,
            cost=cost,
            model_metadata=metadata_json,
        )

        session.add(message)

        if tokens_used or cost:
            statement = select(Conversation).where(Conversation.id == conversation_id)
            result = await session.exec(statement)
            conversation = result.first()

            if conversation:
                if tokens_used:
                    conversation.total_tokens_used += tokens_used
                if cost:
                    conversation.total_cost += cost
                session.add(conversation)

        await session.commit()
        await session.refresh(message)

        return message

    async def get_conversation_messages(
        self, session: AsyncSession, conversation_id: int, limit: int | None = None
    ) -> list[Message]:
        statement = (
            select(Message).where(Message.conversation_id == conversation_id).order_by(col(Message.created_at).asc())
        )

        if limit:
            statement = statement.limit(limit)

        result = await session.exec(statement)
        return list(result.all())
