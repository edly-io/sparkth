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

### LLM-Aware Plugins

If your plugin lets users pick an AI model to power some feature (e.g. answer synthesis, content generation), add `llm_config_id` and `llm_model_override` to the config class. These two fields work as a pair: `llm_config_id` points to one of the user's saved LLM configurations (provider + API key), and `llm_model_override` lets them swap in a different model from the same provider without creating a new configuration.

```python
# app/core_plugins/myplugin/config.py
from pydantic import Field
from app.plugins.config_base import PluginConfig

class MyPluginConfig(PluginConfig):
    llm_config_id: int | None = Field(
        default=None,
        description="ID of an LLMConfig row for AI features. None disables AI.",
    )
    llm_model_override: str | None = Field(
        default=None,
        description="Override the model from the selected LLMConfig. None uses the config's model.",
    )
```

On its own, these are plain optional integers and strings — Pydantic only checks the types. Cross-field validation (does `llm_config_id` actually belong to this user? is `llm_model_override` a valid model for the linked provider?) requires a config adapter, described in the [Plugin Config Adapters](#plugin-config-adapters-llm-aware-plugins) section below.

#### Supported providers and models

The current implementation supports three providers. Valid `llm_model_override` values must come from this list for the provider of the linked `LLMConfig`.

| Provider | Valid models |
|---|---|
| `openai` | `gpt-4o`, `gpt-4o-mini`, `o1`, `o1-mini`, `o3-mini` |
| `anthropic` | `claude-opus-4-5`, `claude-sonnet-4-5`, `claude-haiku-4-5`, `claude-sonnet-4-20250514` |
| `google` | `gemini-2.0-flash`, `gemini-1.5-pro`, `gemini-1.5-flash` |

The canonical source is `PROVIDER_MODELS` in `app/llm/providers.py`. That dict is the single truth for validation — the table above is a snapshot, so check the source when in doubt.


### LMS Plugins: Automatic Credential Injection

If your plugin is an LMS (i.e. it has tools that require stored credentials), override two methods on the config class. The chat system will then automatically inject the user's stored credentials into the LLM system prompt — no manual wiring needed.

```python
class MyLmsConfig(PluginConfig):
    api_url: str = Field(..., description="LMS API URL")
    api_key: str = Field(..., description="LMS API key")

    @classmethod
    def lms_tool_prefix(cls) -> str:
        """
        Prefix shared by all tool names for this LMS (e.g. "mylms_").
        Used to detect whether any active tools belong to this LMS before
        hitting the database.
        """
        return "mylms_"

    def to_lms_credentials_hint(self) -> str:
        """
        Human-readable credential block included in the LLM system prompt.
        Return None (or omit the override) for non-LMS plugins.
        """
        return (
            "My <LMS> credentials:\n"
            f"  api_url: {self.api_url}\n"
            f"  api_key: {self.api_key}"
        )
```

Both methods default to `None` on the base class, so non-LMS plugins require no changes. The injection is fully automatic once the config class is registered in `PLUGIN_CONFIG_CLASSES`.


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


## Plugin Config Adapters (LLM-Aware Plugins)

If your plugin config includes `llm_config_id` and `llm_model_override`, register a config adapter so the system validates them at write time and resolves them for the frontend at read time. Without an adapter the fields are stored as plain values with no cross-field checks.

### What the adapter does

`LLMConfigAdapter` (from `app.llm.adapter`) hooks into the config pipeline via three methods:

| Method | When called | What it does |
|---|---|---|
| `preprocess_config` | Before saving config (POST and PUT) | Verifies `llm_config_id` belongs to the user and is active. Validates `llm_model_override` is a legal model for that config's provider. Raises `ValueError` on any violation. |
| `postprocess_config` | Before returning config in API responses | Resolves `llm_config_id` into `llm_config_name`, `llm_provider`, and `llm_model` read-only fields for the frontend. |
| `sync_cache` | After a successful PUT | No-op by default; override to invalidate or warm caches when config changes. |

### Adding an adapter for your plugin

**1. Create the adapter class**

For the default behaviour (LLM config ownership check + model override validation) a thin subclass is all you need:

```python
# app/core_plugins/myplugin/adapter.py
from app.llm.adapter import LLMConfigAdapter

class MyPluginConfigAdapter(LLMConfigAdapter):
    pass
```

**2. Register it in `PLUGIN_ADAPTERS`**

```python
# app/plugins/adapters.py
from app.core_plugins.myplugin.adapter import MyPluginConfigAdapter

PLUGIN_ADAPTERS: dict[str, LLMConfigAdapter] = {
    ...
    "myplugin": MyPluginConfigAdapter(),
}
```

That's it. `preprocess_config` and `postprocess_config` are now wired in automatically for every POST and PUT to your plugin's config endpoint.

### Overriding adapter methods

Override a method when the default behaviour isn't enough. Always call `super()` first in `preprocess_config` and `postprocess_config` so the base LLM validation still runs.

**Custom preprocessing** — validate an extra field before saving:

```python
from typing import Any
from sqlmodel.ext.asyncio.session import AsyncSession
from app.llm.adapter import LLMConfigAdapter

class MyPluginConfigAdapter(LLMConfigAdapter):
    async def preprocess_config(
        self,
        *,
        session: AsyncSession,
        user_id: int,
        incoming_config: dict[str, Any],
    ) -> dict[str, Any]:
        result = await super().preprocess_config(
            session=session,
            user_id=user_id,
            incoming_config=incoming_config,
        )
        if result.get("webhook_url") and not result["webhook_url"].startswith("https://"):
            raise ValueError("webhook_url must use HTTPS.")
        return result
```

**Custom postprocessing** — attach extra derived fields to the response:

```python
class MyPluginConfigAdapter(LLMConfigAdapter):
    async def postprocess_config(
        self,
        *,
        session: AsyncSession,
        user_id: int,
        stored_config: dict[str, Any],
    ) -> dict[str, Any]:
        result = await super().postprocess_config(
            session=session,
            user_id=user_id,
            stored_config=stored_config,
        )
        result["some_derived_field"] = compute_something(result)
        return result
```

**Cache invalidation** — clear a Redis key when config is updated:

```python
class MyPluginConfigAdapter(LLMConfigAdapter):
    async def sync_cache(
        self,
        *,
        session: AsyncSession,
        user_id: int,
        stored_config: dict[str, Any],
    ) -> None:
        await cache.delete(f"myplugin:{user_id}")
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
