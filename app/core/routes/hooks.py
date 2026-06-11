from fastapi import APIRouter

from app.lib.hooks import PluginHook

# Each item is a (router, prefix, tags) triple contributed by a plugin.
PLUGIN_ROUTERS: PluginHook[APIRouter] = PluginHook()
