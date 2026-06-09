from fastapi import APIRouter

from app.lib.hooks import PluginCollectionHook

# Each item is a (router, prefix, tags) triple contributed by a plugin.
ROUTES: PluginCollectionHook[tuple[APIRouter, str, list[str]]] = PluginCollectionHook()
