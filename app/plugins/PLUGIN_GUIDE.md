# Sparkth Plugin Guide

Quick guide for creating Sparkth plugins with API routes and MCP tools.


## Plugin Config Definition
Define a config class for the plugin that must inherit from `app.plugins.config_base:PluginConfig`

```python
# sparkth_plugins/myplugin/config.py
from pydantic import Field
from app.plugins.config_base import PluginConfig

class MyPluginConfig(PluginConfig):
    config_field: str = Field(..., description="...")
    
    # define additional fields as required

```


## Register the plugin configuration class
Each plugin must register its Pydantic configuration class so the system can validate and normalize user-provided configuration.

Add your plugin’s config class to the `PLUGIN_CONFIG_CLASSES` mapping.

```python
# app/plugins/__init__.py

from app.sparkth_plugins.myplugin.config import MyPluginConfig

# ...

PLUGIN_CONFIG_CLASSES = {
    "canvas": CanvasConfig, 
    "open-edx": OpenEdxConfig,
    "myplugin": MyPluginConfig  # List your plugin config class
}

```


## Basic Plugin Structure

```python
# sparkth_plugins/myplugin/plugin.py
from app.plugins.base import SparkthPlugin, tool
from fastapi import APIRouter
from app.sparkth_plugins.myplugin.config import MyPluginConfig

# Create router outside the class
router = APIRouter(prefix="/my-plugin", tags=["My Plugin"])

@router.get("/")
async def get_data():
    return {"message": "Hello from my plugin"}

@router.post("/items")
async def create_item(data: dict):
    return {"created": True}


# Plugin class
class MyPlugin(SparkthPlugin):
    def __init__(self):
        super().__init__(
            name="my-plugin",
            version="1.0.0",
            description="My plugin description"
            config_schema=MyPluginConfig    # Also register the config class with the plugin
        )
        # Add the router
        self.add_route(router)
    
    # MCP Tools using @tool decorator
    @tool(description="Process some input", category="utilities")
    async def process_data(self, input: str) -> str:
        """Process the input and return result."""
        return f"Processed: {input}"
```

## Register in core/config.py
```python
PLUGINS = [
    "app.core_plugins.canvas.plugin:CanvasPlugin",
    "app.core_plugins.openedx.plugin:OpenEdXPlugin",
    # add your plugin here
]
```

Format: `"path.to.module:ClassName"`

## Adding Database Models (Optional)

```python
from sqlmodel import SQLModel, Field

class MyModel(SQLModel, table=True):
    __tablename__ = "my_plugin_items"
    id: int = Field(primary_key=True)
    title: str

class MyPlugin(SparkthPlugin):
    def __init__(self):
        super().__init__(name="my-plugin")
        self.add_model(MyModel)  # Register model
        self.add_route(router)   # Register router
```

Then create migration:
```bash
alembic revision --autogenerate -m "my_plugin_add_model"
alembic upgrade head
```

## MCP Tools

Tools are defined using the `@tool` decorator on class methods:

```python
@tool(description="Tool description", category="category")
async def my_tool(self, param1: str, param2: int = 0) -> dict:
    """
    Tool documentation.
    
    Args:
        param1: First parameter
        param2: Optional parameter
    
    Returns:
        Result dictionary
    """
    return {"result": f"{param1}-{param2}"}
```

## Complete Example

```python
from app.plugins.base import SparkthPlugin, tool
from fastapi import APIRouter

# Router
router = APIRouter(prefix="/weather", tags=["Weather"])

@router.get("/{city}")
async def get_weather(city: str):
    return {"city": city, "temp": 20}

# Plugin
class WeatherPlugin(SparkthPlugin):
    def __init__(self):
        super().__init__(name="weather-plugin", version="1.0.0")
        self.add_route(router)
    
    @tool(description="Get weather for a city", category="weather")
    async def get_weather(self, city: str) -> dict:
        return {"city": city, "temperature": 20, "unit": "celsius"}
```

## Testing

```bash
# Start server
make start

# Test API
curl http://localhost:8000/api/v1/my-plugin/
```

For real-world examples, see `core_plugins/canvas/` directory.
