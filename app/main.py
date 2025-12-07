from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api.v1.api import api_router
from app.hooks.catalog import Actions, Filters
from app.plugins import discover_plugins, load_all
from app.plugins.manager import get_manager


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Lifespan context manager for the FastAPI application.
    
    This handles startup and shutdown events, including plugin initialization.
    """
    # Startup: Discover and load sparkth-plugins
    print("Discovering sparkth-plugins...")
    discover_plugins()
    
    # Load enabled sparkth-plugins
    manager = get_manager()
    enabled_plugins = manager.get_enabled_plugins()
    if enabled_plugins:
        print(f"Loading sparkth-plugins: {', '.join(enabled_plugins)}")
        load_all(enabled_plugins)
    else:
        print("No sparkth-plugins enabled")
    
    # Register plugin routers
    for name, router in Filters.API_ROUTERS.iterate():
        app.include_router(router)
        print(f"Registered plugin router: {name}")
    
    # Trigger startup actions
    Actions.APP_STARTUP.do()
    
    yield
    
    # Shutdown: Trigger shutdown actions
    Actions.APP_SHUTDOWN.do()


app = FastAPI(lifespan=lifespan, title="Sparkth API", version="1.0.0")

# Include core API router
app.include_router(api_router, prefix="/api/v1")


@app.get("/")
def read_root() -> dict[str, str]:
    return {"message": "Welcome to the Sparkth API"}


@app.get("/plugins")
def list_plugins() -> dict[str, list[str]]:
    """
    List all installed and loaded sparkth-plugins.
    """
    from app.plugins import iter_installed, iter_loaded
    
    return {
        "installed": list(iter_installed()),
        "loaded": list(iter_loaded()),
    }


@app.get("/plugins/info")
def plugins_info() -> dict[str, str]:
    """
    Get detailed information about all sparkth-plugins.
    """
    from app.plugins import iter_info
    
    return dict(iter_info())
