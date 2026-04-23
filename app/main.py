import asyncio
import logging
import sys
from collections.abc import AsyncIterator, Callable
from contextlib import asynccontextmanager
from enum import Enum
from importlib.metadata import PackageNotFoundError, version
from typing import Any, Union, cast

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from starlette.types import ASGIApp

from app.api.v1.api import api_router
from app.core.config import get_settings
from app.core_plugins.chat.routes import chat_router
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
        loaded_plugins = await plugin_manager.load_all_enabled()
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
            except (AttributeError, TypeError, ValueError) as e:
                logger.error(f"Failed to register routes for plugin '{plugin_name}': {e}")

        for plugin_name, plugin in loaded_plugins.items():
            try:
                middleware_list = plugin.get_middleware()
                if not middleware_list:
                    continue

                for middleware_item in middleware_list:
                    mw = cast(Callable[[ASGIApp], ASGIApp], middleware_item.cls)
                    application.add_middleware(mw, **cast(dict[str, Any], middleware_item.kwargs))
            except (AttributeError, TypeError, ValueError) as e:
                logger.error(f"Failed to register middleware for plugin '{plugin_name}': {e}")

    except (ImportError, RuntimeError, OSError) as e:
        logger.error(f"Plugin initialization failed: {e}")

    yield

    try:
        plugin_manager.disable_all_loaded()
        plugin_manager.unload_all()
    except (RuntimeError, AttributeError) as e:
        logger.error(f"Plugin cleanup failed: {e}")


try:
    __version__ = version("sparkth")
except PackageNotFoundError:
    __version__ = "unknown"
    logger.warning("Package 'sparkth' not found; version set to 'unknown'")

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

            # Load embedding model before server starts accepting requests.
            # asyncio.to_thread keeps the event loop unblocked during model loading.
            from app.rag.provider import init_provider

            await asyncio.to_thread(init_provider)

            # Mount frontend static files AFTER plugin routes are registered,
            # so plugin API routes take precedence over the catch-all "/" mount.
            frontend_settings = get_settings()
            if frontend_settings.FRONTEND_DIR.exists():
                application.mount(
                    "/", StaticFiles(directory=frontend_settings.FRONTEND_DIR, html=True), name="frontend"
                )

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
app.include_router(chat_router, prefix="/api/v1")
