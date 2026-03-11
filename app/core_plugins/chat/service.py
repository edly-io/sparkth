import json
from datetime import datetime, timezone
from typing import Any

from sqlmodel import col, func, select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.logger import get_logger
from app.core_plugins.chat.cache import CacheService
from app.core_plugins.chat.encryption import EncryptionService
from app.core_plugins.chat.models import Conversation, Message, MessageType, ProviderAPIKey

logger = get_logger(__name__)


class ChatService:
    def __init__(self, encryption_service: EncryptionService, cache_service: CacheService):
        self.encryption = encryption_service
        self.cache = cache_service

    @staticmethod
    def mask_api_key(api_key: str) -> str:
        """Return a masked version of the key, e.g. 'sk-...abcd'."""
        suffix = api_key[-4:] if len(api_key) >= 4 else api_key
        parts = api_key.split("-", maxsplit=1)
        prefix = parts[0] + "-" if len(parts) >= 2 else ""
        return f"{prefix}****{suffix}"

    async def create_api_key(
        self,
        session: AsyncSession,
        user_id: int,
        provider: str,
        api_key: str,
    ) -> ProviderAPIKey:
        await self.deactivate_old_keys(user_id, provider, session)

        cache_key = self.cache.make_key("api_key", str(user_id), provider.lower())
        await self.cache.delete(cache_key)

        encrypted_key = self.encryption.encrypt(api_key)
        masked = self.mask_api_key(api_key)

        db_key = ProviderAPIKey(
            user_id=user_id,
            provider=provider.lower(),
            encrypted_key=encrypted_key,
            masked_key=masked,
            is_active=True,
        )
        session.add(db_key)
        await session.flush()
        await session.refresh(db_key)

        logger.info(f"Created API key for user {user_id}, provider {provider}")

        return db_key

    async def deactivate_old_keys(self, user_id: int, provider: str, session: AsyncSession) -> None:
        existing_statement = (
            select(ProviderAPIKey)
            .where(
                ProviderAPIKey.user_id == user_id,
                ProviderAPIKey.provider == provider.lower(),
                ProviderAPIKey.is_active == True,
            )
            .with_for_update()
        )
        result = await session.exec(existing_statement)
        existing_keys = result.all()
        for key in existing_keys:
            key.is_active = False
            session.add(key)

    async def get_api_key(
        self,
        session: AsyncSession,
        user_id: int,
        provider: str,
    ) -> str | None:
        provider = provider.lower()
        cache_key = self.cache.make_key("api_key", str(user_id), provider)
        cached_encrypted = await self.cache.get(cache_key)

        if cached_encrypted:
            try:
                decrypted = self.encryption.decrypt(cached_encrypted)
                logger.debug(f"API key cache hit for user {user_id}, provider {provider}")
                return decrypted
            except ValueError as e:
                logger.warning(f"Failed to decrypt cached API key, evicting: {e}")
                await self.cache.delete(cache_key)

        statement = (
            select(ProviderAPIKey)
            .where(
                ProviderAPIKey.user_id == user_id,
                ProviderAPIKey.provider == provider,
                ProviderAPIKey.is_active == True,  # noqa: E712
                ProviderAPIKey.deleted_at == None,
            )
            .order_by(col(ProviderAPIKey.created_at).desc())
        )
        result = await session.exec(statement)
        db_key = result.first()

        if not db_key:
            logger.warning(f"No API key found for user {user_id}, provider {provider}")
            return None

        try:
            decrypted_key = self.encryption.decrypt(db_key.encrypted_key)
        except ValueError as e:
            logger.error(f"Failed to decrypt DB API key for user {user_id}, provider {provider}: {e}")
            raise

        await self.cache.set(cache_key, db_key.encrypted_key)

        db_key.last_used_at = datetime.now(timezone.utc)
        session.add(db_key)

        return decrypted_key

    async def list_api_keys(self, session: AsyncSession, user_id: int) -> list[ProviderAPIKey]:
        statement = select(ProviderAPIKey).where(
            ProviderAPIKey.user_id == user_id, ProviderAPIKey.deleted_at == None, ProviderAPIKey.is_active == True
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

        db_key.deleted_at = datetime.now(timezone.utc)
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
        )
        result = await session.exec(statement)
        return result.first()

    async def list_conversations(
        self, session: AsyncSession, user_id: int, limit: int = 50, offset: int = 0
    ) -> tuple[list[Conversation], int]:
        count_statement = select(func.count(col(Conversation.id))).where(
            Conversation.user_id == user_id,
        )
        total = (await session.exec(count_statement)).one()

        statement = (
            select(Conversation)
            .where(
                Conversation.user_id == user_id,
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
        is_error: bool = False,
        message_type: MessageType = "text",
        attachment_name: str | None = None,
        attachment_size: int | None = None,
    ) -> Message:
        metadata_json = json.dumps(metadata) if metadata else None

        message = Message(
            conversation_id=conversation_id,
            role=role,
            content=content,
            tokens_used=tokens_used,
            cost=cost,
            model_metadata=metadata_json,
            is_error=is_error,
            message_type=message_type,
            attachment_name=attachment_name,
            attachment_size=attachment_size,
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
        self,
        session: AsyncSession,
        conversation_id: int,
        limit: int | None = None,
        offset: int | None = None,
        exclude_errors: bool = True,
    ) -> list[Message]:
        """
        Return conversation messages, optionally excluding error messages.
        """
        statement = (
            select(Message).where(Message.conversation_id == conversation_id).order_by(col(Message.created_at).asc())
        )

        if exclude_errors:
            statement = statement.where(Message.is_error == False)  # noqa: E712

        if limit is not None:
            statement = statement.limit(limit)

        if offset is not None:
            statement = statement.offset(offset)

        result = await session.exec(statement)
        return list(result.all())
