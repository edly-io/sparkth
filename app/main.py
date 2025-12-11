import logging
import sys
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api.v1.api import api_router
from app.mcp.server import mcp
from app.plugins import PluginManager


mcp_app = mcp.http_app(path="/")

app = FastAPI(lifespan=mcp_app.lifespan)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)

logger = logging.getLogger(__name__)

# Global plugin manager instance
plugin_manager = PluginManager()


@asynccontextmanager
async def lifespan(application: FastAPI):
    """
    FastAPI lifespan context manager.
    Handles plugin loading on startup and cleanup on shutdown.
    """
    # Startup: Discover and load all enabled plugins
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
                        application.include_router(
                            router,
                            prefix=prefix if prefix else "",
                            tags=tags if tags else None
                        )
            except Exception as e:
                logger.error(f"Failed to register routes for plugin '{plugin_name}': {e}")
        
        # Register plugin middleware
        for plugin_name, plugin in loaded_plugins.items():
            try:
                middleware_list = plugin.get_middleware()
                if middleware_list:
                    for middleware in middleware_list:
                        application.add_middleware(middleware)
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


# Create FastAPI app with plugin-aware lifespan
app = FastAPI(
    title="Sparkth API",
    description="Sparkth API with Plugin System",
    version="1.0.0",
    lifespan=lifespan
)

# Include core API routes
app.include_router(api_router, prefix="/api/v1")

app.mount("/mcp", mcp_app)


@app.get("/")
def read_root() -> dict[str, str]:
    return {"message": "Welcome to the Sparkth API"}


@app.get("/plugins")
def list_plugins() -> dict[str, list]:
    """
    List all available plugins and their status.
    """
    return {
        "plugins": plugin_manager.list_all_plugins()
    }
