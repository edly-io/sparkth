import logging
import sys
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api.v1.api import api_router
from app.mcp.main import register_plugin_tools
from app.mcp.server import mcp
from app.plugins import get_plugin_manager
from app.plugins.middleware import PluginAccessMiddleware

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)

logger = logging.getLogger(__name__)


@asynccontextmanager
async def plugin_lifespan(application: FastAPI):
    """
    Plugin lifespan context manager.
    Handles plugin loading on startup and cleanup on shutdown.
    """
    # Startup: Discover and load all enabled plugins
    plugin_manager = get_plugin_manager()
    try:
        loaded_plugins = plugin_manager.load_all_enabled()
        if loaded_plugins:
            logger.info(f"Loaded {len(loaded_plugins)} plugin(s): {', '.join(loaded_plugins.keys())}")

        # Enable all loaded plugins
        plugin_manager.enable_all_loaded()

        # Register plugin routes
        for plugin_name, plugin in loaded_plugins.items():
            try:
                routes = plugin.get_routes()
                if routes:
                    for router in routes:
                        prefix = plugin.get_route_prefix()
                        tags = plugin.get_route_tags()
                        application.include_router(router, prefix=prefix if prefix else "", tags=tags if tags else None)
            except Exception as e:
                logger.error(f"Failed to register routes for plugin '{plugin_name}': {e}")

        # Register plugin middleware
        for plugin_name, plugin in loaded_plugins.items():
            try:
                middleware_list = plugin.get_middleware()
                if middleware_list:
                    for middleware in middleware_list:
                        application.add_middleware(middleware.cls, **middleware.options)
            except Exception as e:
                logger.error(f"Failed to register middleware for plugin '{plugin_name}': {e}")

    except Exception as e:
        logger.error(f"Plugin initialization failed: {e}")

    yield

    # Shutdown: Cleanup plugins
    try:
        plugin_manager.disable_all_loaded()
        plugin_manager.unload_all()
    except Exception as e:
        logger.error(f"Plugin cleanup failed: {e}")


mcp_app = mcp.http_app(path="/")


@asynccontextmanager
async def lifespan(application: FastAPI):
    """
    Application lifespan that executes both MCP and plugin lifespans.
    """
    # Run MCP lifespan startup
    async with mcp_app.lifespan(application):
        # Run plugin lifespan startup
        async with plugin_lifespan(application):
            # Register MCP tools from plugins after plugins are loaded
            logger.info("Registering MCP tools from plugins...")
            register_plugin_tools()

            # Log total number of registered MCP tools
            import asyncio

            all_tools = await asyncio.create_task(mcp.get_tools())
            logger.info(f"MCP server ready with {len(all_tools)} total tool(s) registered")

            yield
        # Plugin lifespan shutdown happens here
    # MCP lifespan shutdown happens here


app = FastAPI(lifespan=lifespan)
app.mount("/mcp", mcp_app)

# Add Plugin Access Control Middleware
# This middleware checks user permissions for plugin routes
app.add_middleware(
    PluginAccessMiddleware,
    exclude_paths=[
        "/docs",
        "/redoc",
        "/openapi.json",
        "/",
        "/plugins",
        "/api/v1/auth",  # Auth endpoints should always be accessible
    ],
)
# Include core API routes
app.include_router(api_router, prefix="/api/v1")


@app.get("/")
def read_root() -> dict[str, str]:
    return {"message": "Welcome to the Sparkth API"}


@app.get("/plugins")
def list_plugins() -> dict[str, list]:
    """
    List all available plugins and their status.
    """
    plugin_manager = get_plugin_manager()
    return {"plugins": plugin_manager.list_all_plugins()}
