# Sparkth Plugin System

The Sparkth Plugin System is a powerful, extensible architecture based on Actions and Filters that allows developers to extend and customize Sparkth's functionality without modifying the core codebase.

## Architecture Overview

The plugin system is consists of:

1. **Hooks System** - Actions and Filters for extension points
2. **Plugin Discovery** - Automatic discovery from entrypoints and local files
3. **Plugin Manager** - Configuration and lifecycle management
4. **Context Isolation** - Clean plugin loading/unloading

## Core Concepts

### Actions

Actions are hooks that trigger callbacks at specific moments in the application lifecycle. They don't return values - they just execute code.

```python
from app.hooks.catalog import Actions

@Actions.APP_STARTUP.add()
def on_startup():
    print("Application is starting!")
```

### Filters

Filters transform data by passing it through a chain of callbacks. Each callback receives a value, modifies it, and returns it.

```python
from app.hooks.catalog import Filters

@Filters.API_ROUTERS.add()
def add_my_router(routers):
    from my_plugin import router
    routers.append(("my-plugin", router))
    return routers
```

## Available Hooks

### Actions

- **`CORE_READY`** - Triggered when the application is ready (plugin discovery)
- **`PLUGIN_LOADED`** - Triggered when a plugin is loaded
- **`PLUGINS_LOADED`** - Triggered after all plugins are loaded
- **`PLUGIN_UNLOADED`** - Triggered when a plugin is unloaded
- **`APP_STARTUP`** - Triggered on FastAPI startup
- **`APP_SHUTDOWN`** - Triggered on FastAPI shutdown

### Filters

- **`PLUGINS_INSTALLED`** - List of installed plugins
- **`PLUGINS_LOADED`** - List of loaded plugins
- **`PLUGINS_INFO`** - Plugin information (name, version)
- **`API_ROUTERS`** - FastAPI routers to register
- **`MCP_SERVERS`** - MCP server instances
- **`MCP_TOOLS`** - MCP tool functions
- **`CONFIG_DEFAULTS`** - Default configuration values
- **`CONFIG_OVERRIDES`** - Configuration overrides
- **`CONFIG_UNIQUE`** - Unique configuration (passwords, secrets)
- **`API_MIDDLEWARE`** - FastAPI middleware
- **`STARTUP_TASKS`** - Tasks to run on startup
- **`SHUTDOWN_TASKS`** - Tasks to run on shutdown

## Creating a Plugin

### Method 1: Local Plugin File

Create a `.py` file in `~/.sparkth/plugins/`:

```python
# ~/.sparkth/sparkth-plugins/my_plugin.py
from fastapi import APIRouter
from app.hooks.catalog import Actions, Filters

__version__ = "1.0.0"

# Create API endpoints
router = APIRouter(prefix="/my-plugin")

@router.get("/hello")
async def hello():
    return {"message": "Hello from my plugin!"}

# Register the router
Filters.API_ROUTERS.add_item(("my-plugin", router))

# Add startup logic
@Actions.APP_STARTUP.add()
def on_startup():
    print("My plugin started!")
```

### Method 2: Python Package

1. Create a Python package:

```
my_sparkth_plugin/
├── pyproject.toml
└── my_sparkth_plugin/
    └── __init__.py
```

2. In `pyproject.toml`, add the entrypoint:

```toml
[project]
name = "my-sparkth-plugin"
version = "1.0.0"

[project.entry-points."sparkth.plugin.v1"]
my-plugin = "my_sparkth_plugin"
```

3. In `my_sparkth_plugin/__init__.py`:

```python
from fastapi import APIRouter
from app.hooks.catalog import Actions, Filters

router = APIRouter(prefix="/my-plugin")

@router.get("/status")
async def status():
    return {"status": "active"}

Filters.API_ROUTERS.add_item(("my-plugin", router))
```

4. Install the package:

```bash
pip install -e .
```

## Adding MCP Tools

Plugins can add MCP (Model Context Protocol) tools:

```python
from fastmcp import FastMCP
from app.hooks.catalog import Filters

mcp = FastMCP("my-plugin")

@mcp.tool
async def my_custom_tool(input: str) -> str:
    """
    A custom MCP tool.
    
    Args:
        input: The input string
    """
    return f"Processed: {input}"

# Register the MCP server
Filters.MCP_TOOLS.add_item(mcp)
```

## Plugin Configuration

### Enabling/Disabling Plugins

```python
from app.plugins.manager import get_manager

manager = get_manager()

# Enable a plugin
manager.enable_plugin("my-plugin")

# Disable a plugin
manager.disable_plugin("my-plugin")

# Check if enabled
if manager.is_enabled("my-plugin"):
    print("Plugin is enabled")
```

### Plugin Settings

```python
from app.hooks.catalog import Filters

# Add default configuration
Filters.CONFIG_DEFAULTS.add_items([
    ("MY_PLUGIN_API_KEY", ""),
    ("MY_PLUGIN_ENABLED", True),
])

# Access configuration
from app.plugins.manager import get_manager

manager = get_manager()
config = manager.get_plugin_config("my-plugin")
api_key = config.get("api_key", "")
```

## Plugin Lifecycle

1. **Discovery** - Application starts, `CORE_READY` action triggers plugin discovery
2. **Loading** - Enabled plugins are loaded via `load_all()`
3. **Registration** - Plugin hooks are registered within plugin context
4. **Startup** - `APP_STARTUP` action triggers plugin startup tasks
5. **Runtime** - Plugins receive callbacks via actions/filters
6. **Shutdown** - `APP_SHUTDOWN` action triggers cleanup
7. **Unloading** - `PLUGIN_UNLOADED` action clears plugin hooks

## API Endpoints

Once integrated with FastAPI, the following endpoints are available:

- **`GET /plugins`** - List installed and loaded plugins
- **`GET /plugins/info`** - Get detailed plugin information
- **`GET /plugins/{plugin-name}/*`** - Plugin-specific endpoints


## Best Practices

1. **Prefix Configuration Keys** - Use `PLUGINNAME_KEY` format
2. **Document Tools** - Add clear docstrings to MCP tools
3. **Handle Errors** - Use try/except in callbacks
4. **Clean Up Resources** - Use shutdown actions for cleanup
5. **Version Your Plugin** - Include `__version__` attribute
6. **Test Isolation** - Ensure plugin works independently
7. **Use Priorities** - Set callback priorities when order matters

## Priority System

Control callback execution order:

```python
from app.hooks import priorities

@Actions.APP_STARTUP.add(priority=priorities.HIGH)
def early_startup():
    """Runs early (priority 5)"""
    pass

@Actions.APP_STARTUP.add(priority=priorities.LOW)
def late_startup():
    """Runs late (priority 15)"""
    pass
```

Priority levels:
- `HIGHEST = 0` - Run first
- `HIGH = 5`
- `DEFAULT = 10`
- `LOW = 15`
- `LOWEST = 20` - Run last

## Further Reading

- [FastAPI Documentation](https://fastapi.tiangolo.com/)
- [FastMCP Documentation](https://github.com/jlowin/fastmcp)
