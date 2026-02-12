import logging
from collections.abc import Sequence
from typing import Any

import pydantic
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.models.plugin import Plugin, UserPlugin
from app.plugins import PLUGIN_CONFIG_CLASSES
from app.plugins.config_base import PluginConfig


class ConfigValidationError(Exception):
    pass


class InternalServerError(Exception):
    pass


class PluginDisabledError(Exception):
    pass


class UserPluginResponse(pydantic.BaseModel):
    """Response model for user plugin information."""

    plugin_name: str
    enabled: bool
    config: dict[str, Any]
    is_core: bool


def get_plugin_service() -> PluginService:
    return PluginService()


class PluginService:
    """
    Business logic related to Plugin persistence and state.
    """

    @staticmethod
    def initial_config(schema: dict[str, Any]) -> dict[str, Any]:
        """
        Populate config dict with all keys from schema set to None.
        """
        if not schema or "properties" not in schema:
            return {}
        return {key: None for key in schema["properties"].keys()}

    @staticmethod
    def validate_user_config(plugin: Plugin, user_config: dict[str, Any]) -> dict[str, Any]:
        """
        Validate and normalize user configuration against plugin's Pydantic config model.

        Uses the plugin.config_schema directly instead of dynamically loading config.py.

        Raises:
            ConfigValidationError: if config_schema is not a subclass of PluginConfig or if validation fails
        """

        config_class = PLUGIN_CONFIG_CLASSES.get(plugin.name)
        if not config_class:
            logging.error(f"Plugin '{plugin.name}' config class is missing or invalid")
            raise InternalServerError(f"Plugin '{plugin.name}' cannot be configured at this time.")

        if not issubclass(config_class, PluginConfig):
            logging.error(f"'{plugin.name.title()}Config' must inherit from plugins.config_base.PluginConfig")
            raise InternalServerError(f"Plugin '{plugin.name}' cannot be configured at this time.")

        try:
            validated_config = config_class(**user_config)
        except pydantic.ValidationError as e:
            raise ConfigValidationError(e.errors())

        return validated_config.model_dump(mode="json")

    async def get_by_name(self, session: AsyncSession, name: str) -> Plugin | None:
        statement = select(Plugin).where(Plugin.name == name, Plugin.deleted_at == None)
        result = await session.exec(statement)
        return result.one_or_none()

    async def get_or_create(
        self,
        session: AsyncSession,
        name: str,
        is_core: bool,
        schema: dict[str, Any],
        enabled: bool = True,
    ) -> Plugin:
        plugin = await self.get_by_name(session, name)

        if plugin is not None:
            return plugin

        plugin = Plugin(
            name=name,
            is_core=is_core,
            config_schema=schema,
            enabled=enabled,
        )

        session.add(plugin)
        await session.commit()
        await session.refresh(plugin)

        return plugin

    async def get_all(
        self,
        session: AsyncSession,
        include_disabled: bool = True,
        include_deleted: bool = False,
    ) -> Sequence[Plugin]:
        """
        Get all plugins.

        Args:
            session: Database session
            include_disabled: Whether to include disabled plugins
            include_deleted: Whether to include soft-deleted plugins

        Returns:
            list of Plugin objects
        """
        statement = select(Plugin)

        if not include_deleted:
            statement = statement.where(Plugin.deleted_at == None)

        if not include_disabled:
            statement = statement.where(Plugin.enabled == True)

        result = await session.exec(statement)
        return result.all()

    async def get_user_plugin_map(
        self,
        session: AsyncSession,
        user_id: int | None,
    ) -> dict[str, UserPlugin]:
        statement = (
            select(UserPlugin, Plugin)
            .join(Plugin)
            .where(
                UserPlugin.user_id == user_id,
                UserPlugin.deleted_at == None,
                Plugin.deleted_at == None,
            )
        )
        result = await session.exec(statement)
        results = result.all()

        return {plugin.name: user_plugin for user_plugin, plugin in results}

    async def get_user_plugin(
        self,
        session: AsyncSession,
        user_id: int | None,
        plugin_id: int | None,
    ) -> UserPlugin | None:
        statement = select(UserPlugin).where(
            UserPlugin.user_id == user_id,
            UserPlugin.plugin_id == plugin_id,
            UserPlugin.deleted_at == None,
        )
        result = await session.exec(statement)
        return result.one_or_none()

    async def update_user_plugin_enabled(
        self,
        session: AsyncSession,
        user_id: int,
        plugin_id: int,
        enabled: bool,
    ) -> UserPlugin:
        user_plugin = await self.get_user_plugin(
            session,
            user_id,
            plugin_id,
        )

        if user_plugin:
            user_plugin.enabled = enabled
        else:
            user_plugin = UserPlugin(
                user_id=user_id,
                plugin_id=plugin_id,
                enabled=enabled,
                config={},
            )
            session.add(user_plugin)

        await session.commit()
        await session.refresh(user_plugin)

        return user_plugin

    async def create_user_plugin(
        self, session: AsyncSession, user_id: int, plugin_id: int, user_config: dict[str, Any]
    ) -> UserPlugin:
        user_plugin = UserPlugin(user_id=user_id, plugin_id=plugin_id, enabled=True, config=user_config)

        session.add(user_plugin)
        await session.commit()
        await session.refresh(user_plugin)
        return user_plugin

    async def update_user_plugin_config(
        self,
        session: AsyncSession,
        user_id: int,
        plugin: Plugin,
        user_config: dict[str, Any],
    ) -> UserPlugin:
        if plugin.id is None:
            raise InternalServerError("Plugin must be persisted before creating user plugin")

        user_plugin = await self.get_user_plugin(
            session,
            user_id,
            plugin.id,
        )

        if user_plugin:
            if not user_plugin.enabled:
                raise PluginDisabledError("Cannot update plugin configuration while the plugin is disabled")
            merged_config = {**user_plugin.config, **user_config}
        else:
            merged_config = user_config

        try:
            validated_config = self.validate_user_config(plugin, merged_config)
        except ConfigValidationError as err:
            raise err

        if user_plugin:
            user_plugin.config = validated_config
        else:
            user_plugin = UserPlugin(
                user_id=user_id,
                plugin_id=plugin.id,
                enabled=True,
                config=validated_config,
            )
            session.add(user_plugin)

        await session.commit()
        await session.refresh(user_plugin)

        return user_plugin
