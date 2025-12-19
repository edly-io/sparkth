from typing import Any

from sqlmodel import Session, select

from app.models.plugin import Plugin, UserPlugin


class ConfigValidationError(Exception):
    pass


def get_plugin_service() -> PluginService:
    return PluginService()


class PluginService:
    """
    Business logic related to Plugin persistence and state.
    """

    def get_by_name(self, session: Session, name: str) -> Plugin | None:
        statement = select(Plugin).where(Plugin.name == name, Plugin.deleted_at.is_(None))
        return session.exec(statement).first()

    def get_or_create(
        self,
        session: Session,
        name: str,
        is_builtin: bool,
        schema: dict,
        enabled: bool = True,
    ) -> Plugin:
        plugin = self.get_by_name(session, name)

        if plugin is not None:
            return plugin

        plugin = Plugin(
            name=name,
            is_builtin=is_builtin,
            config_schema=schema,
            enabled=enabled,
        )

        session.add(plugin)
        session.commit()
        session.refresh(plugin)

        return plugin

    def get_all(
        self,
        session: Session,
        include_disabled: bool = True,
        include_deleted: bool = False,
    ) -> list[Plugin]:
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
            statement = statement.where(Plugin.deleted_at.is_(None))

        if not include_disabled:
            statement = statement.where(Plugin.enabled.is_(True))

        return session.exec(statement).all()

    def get_user_plugin_map(
        self,
        session: Session,
        user_id: int,
    ) -> dict[str, UserPlugin]:
        statement = (
            select(UserPlugin, Plugin)
            .join(Plugin)
            .where(
                # Plugin.is_builtin is True,
                UserPlugin.user_id == user_id,
                UserPlugin.deleted_at.is_(None),
                Plugin.deleted_at.is_(None),
            )
        )
        results = session.exec(statement).all()

        return {plugin.name: user_plugin for user_plugin, plugin in results}

    def get_user_plugin(
        self,
        session: Session,
        user_id: int,
        plugin_id: int,
    ) -> UserPlugin | None:
        statement = select(UserPlugin).where(
            UserPlugin.user_id == user_id,
            UserPlugin.plugin_id == plugin_id,
            UserPlugin.deleted_at.is_(None),
        )
        return session.exec(statement).first()

    def set_user_plugin_enabled(
        self,
        session: Session,
        user_id: int,
        plugin: Plugin,
        enabled: bool,
    ) -> UserPlugin:
        user_plugin: UserPlugin = self.get_user_plugin(
            session,
            user_id,
            plugin.id,
        )

        if user_plugin:
            user_plugin.enabled = enabled
        else:
            user_plugin = UserPlugin(
                user_id=user_id,
                plugin_id=plugin.id,
                enabled=enabled,
                config={},
            )
            session.add(user_plugin)

        session.commit()
        session.refresh(user_plugin)

        return user_plugin

    def validate_user_config(self, plugin: Plugin, user_config: dict[str, Any]) -> dict[str, Any]:
        """
        Validate and normalize user configuration against plugin schema.

        Returns the normalized config with defaults applied.
        Raises ConfigValidationError if validation fails.
        """
        schema = plugin.config_schema
        validated_config = {}
        errors = []

        for key, schema_def in schema.items():
            value = user_config.get(key)

            if schema_def.get("required", False) and value is None:
                if schema_def.get("default") is not None:
                    value = schema_def["default"]
                else:
                    errors.append(f"Required field '{key}' is missing")
                    continue

            if value is None:
                value = schema_def.get("default")

            if value is None:
                continue

            expected_type = schema_def.get("type")
            if expected_type == "string" and not isinstance(value, str):
                errors.append(f"Field '{key}' must be a string")
            elif expected_type == "integer" and not isinstance(value, int):
                errors.append(f"Field '{key}' must be an integer")
            elif expected_type == "boolean" and not isinstance(value, bool):
                errors.append(f"Field '{key}' must be a boolean")
            elif expected_type == "array" and not isinstance(value, list):
                errors.append(f"Field '{key}' must be an array")

            validated_config[key] = value

        unexpected = set(user_config.keys()) - set(schema.keys())
        if unexpected:
            errors.append(f"Unexpected fields: {', '.join(unexpected)}")

        if errors:
            raise ConfigValidationError("; ".join(errors))

        return validated_config

    def create_user_plugin(
        self, session: Session, user_id: int, plugin: Plugin, user_config: dict
    ) -> UserPlugin | None:
        try:
            validated_config = self.validate_user_config(plugin, user_config)
        except ConfigValidationError as err:
            raise err

        user_plugin = UserPlugin(user_id=user_id, plugin_id=plugin.id, enabled=True, config=validated_config)

        session.add(user_plugin)
        session.commit()
        return user_plugin
