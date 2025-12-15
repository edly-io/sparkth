# Sparkth Plugin Guide

Quick guide for creating Sparkth plugins with API routes and MCP tools.

## Basic Plugin Structure

```python
# sparkth-plugins/my-plugin/plugin.py
from app.plugins.base import SparkthPlugin, tool
from fastapi import APIRouter

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
        )
        # Add the router
        self.add_route(router)
    
    # MCP Tools using @tool decorator
    @tool(description="Process some input", category="utilities")
    async def process_data(self, input: str) -> str:
        """Process the input and return result."""
        return f"Processed: {input}"
```

## Register in plugins.json

```json
{
  "my-plugin": {
    "enabled": true,
    "module": "sparkth-plugins.my-plugin.plugin:MyPlugin"
  }
}
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

For real-world examples, see `sparkth-plugins/canvas/` directory.
