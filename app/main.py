import asyncio
import logging
import sys
from collections.abc import AsyncIterator, Callable
from contextlib import asynccontextmanager
from enum import Enum
from importlib.metadata import version
from typing import Any, Union, cast

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from starlette.types import ASGIApp

from app.api.v1.api import api_router
from app.core.config import get_settings
from app.mcp.main import register_plugin_tools
from app.mcp.server import mcp
from app.plugins import get_plugin_manager
from app.plugins.middleware import PluginAccessMiddleware

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)


logger = logging.getLogger(__name__)


settings = get_settings()


@asynccontextmanager
async def plugin_lifespan(application: FastAPI) -> AsyncIterator[None]:
    """
    Plugin lifespan context manager.
    Handles plugin loading on startup and cleanup on shutdown.
    """
    plugin_manager = get_plugin_manager()
    try:
        loaded_plugins = plugin_manager.load_all_enabled()
        if loaded_plugins:
            logger.info(f"Loaded {len(loaded_plugins)} plugin(s): {', '.join(loaded_plugins.keys())}")

        plugin_manager.enable_all_loaded()

        for plugin_name, plugin in loaded_plugins.items():
            try:
                routes = plugin.get_routes()
                if routes:
                    for router in routes:
                        prefix = plugin.get_route_prefix()
                        tags = plugin.get_route_tags()
                        tags_param: Union[list[Union[str, Enum]], None] = (
                            cast(Union[list[Union[str, Enum]], None], tags) if tags else None
                        )
                        application.include_router(router, prefix=prefix if prefix else "", tags=tags_param)
            except Exception as e:
                logger.error(f"Failed to register routes for plugin '{plugin_name}': {e}")

        for plugin_name, plugin in loaded_plugins.items():
            try:
                middleware_list = plugin.get_middleware()
                if not middleware_list:
                    continue

                for middleware_item in middleware_list:
                    mw = cast(Callable[[ASGIApp], ASGIApp], middleware_item.cls)
                    application.add_middleware(mw, **cast(dict[str, Any], middleware_item.kwargs))
            except Exception as e:
                logger.error(f"Failed to register middleware for plugin '{plugin_name}': {e}")

    except Exception as e:
        logger.error(f"Plugin initialization failed: {e}")

    yield

    try:
        plugin_manager.disable_all_loaded()
        plugin_manager.unload_all()
    except Exception as e:
        logger.error(f"Plugin cleanup failed: {e}")


__version__ = version("sparkth")

# Note: Using path="/" causes connection issues with Claude
mcp_app = mcp.http_app(path="/mcp")


@asynccontextmanager
async def lifespan(application: FastAPI) -> AsyncIterator[None]:
    """
    Application lifespan that executes both MCP and plugin lifespans.
    """
    async with mcp_app.lifespan(application):
        async with plugin_lifespan(application):
            logger.info("Registering MCP tools from plugins...")
            register_plugin_tools()
            all_tools = await asyncio.create_task(mcp.get_tools())
            logger.info(f"MCP server ready with {len(all_tools)} total tool(s) registered")

            yield


app = FastAPI(lifespan=lifespan)
app.mount("/ai", mcp_app)


app.add_middleware(
    PluginAccessMiddleware,
    exclude_paths=[
        "/docs",
        "/redoc",
        "/openapi.json",
        "/plugins",
        "/api/v1/auth",
    ],
)


app.include_router(api_router, prefix="/api/v1")

# Serve frontend static files
settings = get_settings()
if settings.FRONTEND_DIR.exists():
    app.mount("/", StaticFiles(directory=settings.FRONTEND_DIR, html=True), name="frontend")
