from __future__ import annotations
"""
Plugin migrations helper module.

Provides utilities for managing database migrations from plugins.
"""

import os
import subprocess
from pathlib import Path
from typing import Optional

from alembic.config import Config
from alembic import command

from app.hooks.catalog import Filters


class PluginMigrationManager:
    """
    Manager for plugin database migrations.
    
    Handles generation and application of migrations for plugin models.
    """
    
    def __init__(self, plugin_name: Optional[str] = None):
        """
        Initialize the migration manager.
        
        :param plugin_name: Name of the plugin (optional, for plugin-specific operations)
        """
        self.plugin_name = plugin_name
        self.alembic_cfg = Config("alembic.ini")
    
    def get_plugin_models(self, plugin_name: Optional[str] = None) -> list[type]:
        """
        Get all models for a specific plugin or all plugin models.
        
        :param plugin_name: Filter models by plugin name (optional)
        :return: List of model classes
        """
        plugin_name = plugin_name or self.plugin_name
        models = []
        
        for model_class in Filters.SQLMODEL_MODELS.iterate():
            if plugin_name:
                # Check if model belongs to this plugin
                module_name = model_class.__module__
                if f"sparkth-plugins.{plugin_name}" in module_name or \
                   f"sparkth-plugins/{plugin_name}" in module_name or \
                   plugin_name in module_name:
                    models.append(model_class)
            else:
                models.append(model_class)
        
        return models
    
    def create_migration(self, message: str, plugin_name: Optional[str] = None) -> str:
        """
        Create a new migration for plugin models.
        
        Uses Alembic's autogenerate feature to detect model changes.
        
        :param message: Migration message/description
        :param plugin_name: Plugin name to include in migration file
        :return: Path to the generated migration file
        """
        plugin_name = plugin_name or self.plugin_name
        
        # Prefix message with plugin name for clarity
        if plugin_name:
            full_message = f"{plugin_name}: {message}"
        else:
            full_message = f"plugins: {message}"
        
        # Generate migration using Alembic
        command.revision(
            self.alembic_cfg,
            message=full_message,
            autogenerate=True
        )
        
        # Get the generated migration file path
        versions_dir = Path("app/migrations/versions")
        migrations = sorted(versions_dir.glob("*.py"), key=lambda p: p.stat().st_mtime)
        
        if migrations:
            latest_migration = migrations[-1]
            return str(latest_migration)
        
        return ""
    
    def apply_migrations(self, target: str = "head") -> None:
        """
        Apply pending migrations.
        
        :param target: Target revision (default: "head" for latest)
        """
        command.upgrade(self.alembic_cfg, target)
    
    def rollback_migrations(self, steps: str = "-1") -> None:
        """
        Rollback migrations.
        
        :param steps: Number of steps to rollback (default: "-1" for one step back)
        """
        command.downgrade(self.alembic_cfg, steps)
    
    def get_current_revision(self) -> Optional[str]:
        """
        Get the current migration revision.
        
        :return: Current revision hash or None
        """
        try:
            result = subprocess.run(
                ["alembic", "current"],
                capture_output=True,
                text=True,
                check=True
            )
            # Parse output to get revision
            output = result.stdout.strip()
            if output and " " in output:
                return output.split()[0]
            return None
        except subprocess.CalledProcessError:
            return None
    
    def list_plugin_models(self, plugin_name: Optional[str] = None) -> list[dict[str, str]]:
        """
        List all models for a plugin with their table names.
        
        :param plugin_name: Plugin name (optional)
        :return: List of dicts with model info
        """
        plugin_name = plugin_name or self.plugin_name
        models = self.get_plugin_models(plugin_name)
        
        model_info = []
        for model in models:
            info = {
                "name": model.__name__,
                "table": getattr(model, "__tablename__", ""),
                "module": model.__module__,
            }
            model_info.append(info)
        
        return model_info


def ensure_plugin_table_naming(plugin_name: str, table_name: str) -> str:
    """
    Ensure plugin table names are properly namespaced.
    
    Adds plugin prefix if not already present.
    
    :param plugin_name: Name of the plugin
    :param table_name: Proposed table name
    :return: Namespaced table name
    """
    # Convert plugin name to safe table prefix
    safe_prefix = plugin_name.replace("-", "_").replace(".", "_").lower()
    
    # Check if already prefixed
    if not table_name.startswith(f"{safe_prefix}_"):
        return f"{safe_prefix}_{table_name}"
    
    return table_name
