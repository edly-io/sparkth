"""
API endpoints for user-level plugin management.
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select
from pydantic import BaseModel

from app.core.db import get_session
from app.models.user import User
from app.models.plugin import UserPlugin
from app.api.v1.utils import  get_current_user
from app.plugins.manager import get_manager
from app.plugins import discover_plugins

router = APIRouter(prefix="/user/plugins", tags=["user-plugins"])


class PluginInfo(BaseModel):
    """Plugin information response."""
    name: str
    enabled: bool
    system_enabled: bool
    config: dict = {}


class PluginConfigUpdate(BaseModel):
    """Plugin configuration update request."""
    config: dict


@router.get("/available")
async def list_available_plugins(
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session)
):
    """
    List all available plugins for the user.
    
    Returns plugins that are system-enabled, showing whether
    each plugin is enabled for the current user.
    """
    discover_plugins()
    manager = get_manager()
    
    system_enabled = manager.get_enabled_plugins()
    user_prefs = manager.get_user_plugin_preferences(current_user.id, session)
    
    plugins = []
    for plugin_name in system_enabled:
        pref = user_prefs.get(plugin_name, {})
        plugins.append({
            "name": plugin_name,
            "enabled": pref.get("enabled", True),  # Default to enabled
            "system_enabled": True,
            "config": pref.get("config", {})
        })
    
    return {"plugins": plugins}


@router.get("/enabled")
async def list_enabled_plugins(
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session)
):
    """
    List plugins enabled for the current user.
    
    Returns only the plugin names that are both system-enabled
    and enabled for the user.
    """
    discover_plugins()
    manager = get_manager()
    
    enabled = manager.get_user_enabled_plugins(current_user.id, session)
    
    return {"plugins": enabled}


@router.put("/{plugin_name}/enable")
async def enable_plugin(
    plugin_name: str,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session)
):
    """Enable a plugin for the current user."""
    manager = get_manager()
    
    try:
        pref = manager.set_user_plugin_preference(
            current_user.id, plugin_name, True, session
        )
        return {
            "message": f"Plugin '{plugin_name}' enabled",
            "plugin": {
                "name": pref.plugin_name,
                "enabled": pref.enabled,
                "config": pref.config
            }
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.put("/{plugin_name}/disable")
async def disable_plugin(
    plugin_name: str,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session)
):
    """Disable a plugin for the current user."""
    manager = get_manager()
    
    try:
        pref = manager.set_user_plugin_preference(
            current_user.id, plugin_name, False, session
        )
        return {
            "message": f"Plugin '{plugin_name}' disabled",
            "plugin": {
                "name": pref.plugin_name,
                "enabled": pref.enabled,
                "config": pref.config
            }
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))



@router.put("/{plugin_name}/config")
async def update_plugin_config(
    plugin_name: str,
    config_update: PluginConfigUpdate,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session)
):
    """Update user's configuration for a specific plugin."""
    manager = get_manager()
    
    # Check if plugin is system-enabled
    if plugin_name not in manager.get_enabled_plugins():
        raise HTTPException(status_code=404, detail="Plugin not available")
    
    pref = manager.set_user_plugin_config(
        current_user.id, plugin_name, config_update.config, session
    )
    
    return {
        "message": f"Configuration updated for '{plugin_name}'",
        "plugin": {
            "name": pref.plugin_name,
            "enabled": pref.enabled,
            "config": pref.config
        }
    }