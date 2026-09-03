from collections.abc import Sequence
from typing import Any

import pydantic
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from sparkth.core.models.plugin import Plugin, UserPlugin
from sparkth.core.plugins import get_plugin_loader
from sparkth.core.plugins.config_base import PluginConfig
from sparkth.lib.config import get_plugin_adapter, get_plugin_config_schema
from sparkth.lib.db import session_scope
from sparkth.lib.frontend import get_plugin_display_info, get_plugin_sidebar_entry, plugin_has_frontend
from sparkth.lib.frontend.hooks import DisplayInfo, SidebarEntry
from sparkth.lib.i18n import _
from sparkth.lib.i18n import gettext as translate
from sparkth.lib.log import get_logger

logger = get_logger(__name__)


async def system_disabled_plugin_names(session: AsyncSession) -> set[str]:
    """Names of the plugins an administrator has switched off system-wide.

    Answers "which plugins are off?" rather than "which are on?" on purpose. A plugin
    with no row in the registry — one that has never reached ``get_or_create_all`` —
    is simply absent from the result and so stays reachable, matching how the HTTP
    gate treats an unknown plugin. Asking the question the other way round would make
    every plugin unreachable until its row existed.

    One query serves a whole request, so a caller checking many plugins (listing the
    tools on the MCP server, say) does not issue a query per plugin.

    Args:
        session: The async database session to read the registry through.

    Returns:
        The set of disabled plugin names, empty when every registered plugin is on.
    """
    statement = select(Plugin.name).where(Plugin.enabled == False, Plugin.deleted_at == None)
    result = await session.exec(statement)
    return set(result.all())


class ConfigValidationError(Exception):
    pass


class InternalServerError(Exception):
    pass


class PluginDisabledError(Exception):
    pass


class UserPluginResponse(pydantic.BaseModel):
    """Response model for user plugin information.

    ``display``, ``sidebar``, and ``has_frontend`` carry the read-only
    frontend-facing metadata the plugin declared through the
    ``sparkth.lib.frontend`` hooks; build responses with :meth:`for_plugin`
    so they are always populated.
    """

    plugin_name: str
    enabled: bool
    config: dict[str, Any]
    is_core: bool
    display: DisplayInfo | None = None
    sidebar: SidebarEntry | None = None
    has_frontend: bool = False

    @classmethod
    def for_plugin(cls, plugin_name: str, enabled: bool, config: dict[str, Any], is_core: bool) -> "UserPluginResponse":
        """Build a response carrying the frontend metadata declared for ``plugin_name``.

        The declared display and sidebar strings are ``gettext_noop``-marked
        source messages; this is their rendering boundary, so they are
        translated into the request locale here.
        """
        display = get_plugin_display_info(plugin_name)
        if display is not None:
            display = DisplayInfo(translate(display.display_name), translate(display.description), display.icon)
        sidebar = get_plugin_sidebar_entry(plugin_name)
        if sidebar is not None:
            sidebar = SidebarEntry(translate(sidebar.label), sidebar.icon, sidebar.order)
        return cls(
            plugin_name=plugin_name,
            enabled=enabled,
            config=config,
            is_core=is_core,
            display=display,
            sidebar=sidebar,
            has_frontend=plugin_has_frontend(plugin_name),
        )


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
    def config_with_schema_keys(schema: dict[str, Any], config: dict[str, Any] | None) -> dict[str, Any]:
        """
        Stored config, with every schema key it lacks present as None.

        The settings UI renders one field per key it receives, so a plugin whose config
        was never saved -- an empty dict, as created by enabling it -- must still report
        its declared fields.
        """
        return {**PluginService.initial_config(schema), **(config or {})}

    @staticmethod
    def validate_user_config(plugin: Plugin, user_config: dict[str, Any]) -> dict[str, Any]:
        """
        Validate and normalize user configuration against plugin's Pydantic config model.

        Uses the plugin.config_schema directly instead of dynamically loading config.py.

        Raises:
            ConfigValidationError: if config_schema is not a subclass of PluginConfig or if validation fails
        """

        config_class = get_plugin_config_schema(plugin.name)
        if not config_class:
            logger.error(f"Plugin '{plugin.name}' config class is missing or invalid")
            raise InternalServerError(_("Plugin '{name}' cannot be configured at this time.").format(name=plugin.name))

        if not issubclass(config_class, PluginConfig):
            logger.error(
                f"'{plugin.name.title()}Config' must inherit from sparkth.core.plugins.config_base.PluginConfig"
            )
            raise InternalServerError(_("Plugin '{name}' cannot be configured at this time.").format(name=plugin.name))

        try:
            validated_config = config_class(**user_config)
        except pydantic.ValidationError as e:
            raise ConfigValidationError(e.errors())

        return validated_config.model_dump(mode="json")

    @staticmethod
    async def apply_preprocess(
        plugin_name: str,
        session: AsyncSession,
        user_id: int,
        incoming_config: dict[str, Any],
    ) -> dict[str, Any]:
        """Run the plugin's preprocess adapter if one is registered."""
        adapter = get_plugin_adapter(plugin_name)
        if adapter:
            return await adapter.preprocess_config(
                session=session,
                user_id=user_id,
                incoming_config=incoming_config,
            )
        return incoming_config

    @staticmethod
    async def apply_postprocess(
        plugin_name: str,
        session: AsyncSession,
        user_id: int,
        stored_config: dict[str, Any],
    ) -> dict[str, Any]:
        """Run the plugin's postprocess adapter if one is registered."""
        adapter = get_plugin_adapter(plugin_name)
        if adapter:
            return await adapter.postprocess_config(
                session=session,
                user_id=user_id,
                stored_config=stored_config,
            )
        return stored_config

    @staticmethod
    async def apply_cache_sync(
        plugin_name: str,
        session: AsyncSession,
        user_id: int,
        stored_config: dict[str, Any],
    ) -> None:
        adapter = get_plugin_adapter(plugin_name)
        if adapter:
            await adapter.sync_cache(session=session, user_id=user_id, stored_config=stored_config)

    async def get_by_name(self, session: AsyncSession, name: str) -> Plugin | None:
        statement = select(Plugin).where(Plugin.name == name, Plugin.deleted_at == None)
        result = await session.exec(statement)
        return result.one_or_none()

    async def get_or_create_all(self) -> None:
        """
        Ensure every loaded plugin has a row in the database.

        Called once at startup. Fetches existing plugins in a single query and
        upserts all loaded plugins in one transaction. Only ``config_schema`` is
        refreshed on existing rows — ``enabled`` is left untouched so a plugin a
        user disabled stays disabled across restarts.
        """
        loaded = get_plugin_loader().get_loaded_plugins()
        async with session_scope() as session:
            result = await session.exec(select(Plugin).where(Plugin.deleted_at == None))
            existing = {plugin.name: plugin for plugin in result.all()}

            for _name, plugin_instance in loaded:
                config_class = get_plugin_config_schema(plugin_instance.name)
                schema = config_class.model_json_schema() if config_class else {}
                current = existing.get(plugin_instance.name)
                if current is None:
                    # New plugins are enabled by default and considered core.
                    session.add(Plugin(name=plugin_instance.name, config_schema=schema, is_core=True, enabled=True))
                elif current.config_schema != schema:
                    current.config_schema = schema

            await session.commit()

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
                raise PluginDisabledError(_("Cannot update plugin configuration while the plugin is disabled"))
            merged_config = {**user_plugin.config, **user_config}
        else:
            merged_config = user_config

        config_class = get_plugin_config_schema(plugin.name)
        if config_class:
            known_fields = set(config_class.model_fields.keys())
            merged_config = {k: v for k, v in merged_config.items() if k in known_fields}

        # Run adapter preprocessing on the full merged config so cross-field
        # validators see the complete final state, not just the partial incoming dict.
        merged_config = await PluginService.apply_preprocess(plugin.name, session, user_id, merged_config)

        validated_config = self.validate_user_config(plugin, merged_config)

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

        await session.flush()
        await session.refresh(user_plugin)

        return user_plugin
