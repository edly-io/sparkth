import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from importlib.metadata import PackageNotFoundError, version

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from starlette.types import Lifespan

from app.api.v1.api import api_router
from app.core.config import get_settings
from app.core.routes.hooks import PLUGIN_ROUTERS
from app.lib.log import configure_logging, get_logger
from app.lib.plugins import PluginAccessMiddleware, get_plugin_loader
from app.mcp.server import mcp, register_plugin_tools
from app.services.plugin import get_plugin_service

configure_logging()

logger = get_logger(__name__)

settings = get_settings()


@asynccontextmanager
async def plugin_lifespan() -> AsyncIterator[None]:
    """
    Plugin lifespan context manager.

    Owns the stateful side of plugins: ensures every plugin has a DB row on
    startup and unloads plugins on shutdown. Route registration is DB-free and
    happens in assemble_app(), not here.
    """
    plugin_service = get_plugin_service()
    await plugin_service.get_or_create_all()

    yield

    try:
        get_plugin_loader().unload_all()
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
        async with plugin_lifespan():
            logger.info("Registering MCP tools from plugins...")
            register_plugin_tools()
            all_tools = await asyncio.create_task(mcp.get_tools())
            logger.info(f"MCP server ready with {len(all_tools)} total tool(s) registered")

            # Mount frontend static files AFTER plugin routes are registered,
            # so plugin API routes take precedence over the catch-all "/" mount.
            frontend_settings = get_settings()
            if frontend_settings.FRONTEND_DIR.exists():
                application.mount(
                    "/", StaticFiles(directory=frontend_settings.FRONTEND_DIR, html=True), name="frontend"
                )

            yield


def _register_plugin_routes(application: FastAPI) -> None:
    """Register every loaded plugin's routers. DB-free: only imports and include_router."""
    plugin_loader = get_plugin_loader()
    loaded_plugins = plugin_loader.get_loaded_plugins()
    if loaded_plugins:
        loaded_plugin_names = [name for name, _plugin in loaded_plugins]
        logger.info(f"Loaded {len(loaded_plugins)} plugin(s): {', '.join(loaded_plugin_names)}")

    for _plugin, router in PLUGIN_ROUTERS.iter_items():
        application.include_router(router)


def assemble_app(lifespan: Lifespan[FastAPI] | None = None) -> FastAPI:
    """
    Build the fully-routed FastAPI app. DB-free: no I/O and no event loop required.

    Pass lifespan=None (the default) for codegen and tests that only need the
    route map; production startup passes the real lifespan below.
    """
    application = FastAPI(lifespan=lifespan)
    application.mount("/ai", mcp_app)
    application.add_middleware(
        PluginAccessMiddleware,
        exclude_paths=[
            "/docs",
            "/redoc",
            "/openapi.json",
            "/plugins",
            "/api/v1/auth",
        ],
    )
    application.include_router(api_router, prefix="/api/v1")
    _register_plugin_routes(application)
    return application


app = assemble_app(lifespan=lifespan)
