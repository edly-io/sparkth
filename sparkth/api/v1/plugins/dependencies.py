"""FastAPI dependencies gating and scoping the plugin endpoints."""

from fastapi import Depends
from sqlmodel.ext.asyncio.session import AsyncSession

from sparkth.core.models.user import User
from sparkth.lib.auth import get_current_user
from sparkth.lib.db import get_async_session
from sparkth.lib.permissions import PLUGIN_USE, get_accessible_scope_object_ids
from sparkth.lib.permissions.scopes import PLUGIN

require_plugin_use = PLUGIN_USE.require(PLUGIN, "plugin_name")


async def get_usable_plugin_names(
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_async_session),
) -> set[str] | None:
    """Return the names of the plugins the caller may use, or ``None`` when they may use every plugin."""
    return await get_accessible_scope_object_ids(current_user, PLUGIN_USE, PLUGIN, session)
