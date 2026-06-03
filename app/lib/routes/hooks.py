from fastapi import APIRouter

from app.lib.hooks import PluginCollectionHook

# Each item is a (prefix, tags, router) triple contributed by a plugin.
ROUTES: PluginCollectionHook[tuple[str, list[str], APIRouter]] = PluginCollectionHook()
