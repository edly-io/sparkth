# Sparkth Plugin Guide

Quick guide for creating Sparkth plugins with API routes and MCP tools.


## Plugin Config Definition
Define a config class for the plugin that must inherit from `app.plugins.config_base:PluginConfig`

```python
# app/core_plugins/myappplugin/config.py
from pydantic import Field
from app.plugins.config_base import PluginConfig

class MyAppPluginConfig(PluginConfig):
    config_field: str = Field(..., description="...")

    # define additional fields as required
```

### LLM-Aware Plugins

If your plugin lets users pick an AI model to power some feature (e.g. answer synthesis, content generation), add `llm_config_id` and `llm_model_override` to the config class. These two fields work as a pair: `llm_config_id` points to one of the user's saved LLM configurations (provider + API key), and `llm_model_override` lets them swap in a different model from the same provider without creating a new configuration.

```python
# app/core_plugins/myappplugin/config.py
from pydantic import Field
from app.plugins.config_base import PluginConfig

class MyAppPluginConfig(PluginConfig):
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

Register a Pydantic configuration class when your plugin has user-configurable settings that the system should validate and normalize — and always for LMS plugins that rely on credential injection. Plugins with no user-facing configuration can skip this entirely (the built-in `google-drive` plugin has no entry in `PLUGIN_CONFIG_CLASSES`).

When you do register one, add your plugin’s config class to the `PLUGIN_CONFIG_CLASSES` mapping. **The dict key must be the plugin's _derived_ name** — see [Plugin Name Derivation](#plugin-name-derivation) below. For a class named `FooBarPlugin` the key is `foo-bar`.

```python
# app/plugins/__init__.py

from app.core_plugins.myappplugin.config import MyAppPluginConfig

# ...

PLUGIN_CONFIG_CLASSES = {
    "canvas": CanvasConfig,
    "open-edx": OpenEdxConfig,
    "my-app": MyAppPluginConfig  # key = derived plugin name, not an arbitrary label
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
# app/core_plugins/myappplugin/adapter.py
from app.llm.adapter import LLMConfigAdapter

class MyAppPluginConfigAdapter(LLMConfigAdapter):
    pass
```

**2. Register it in `PLUGIN_ADAPTERS`**

```python
# app/plugins/adapters.py
from app.core_plugins.myappplugin.adapter import MyAppPluginConfigAdapter

PLUGIN_ADAPTERS: dict[str, LLMConfigAdapter] = {
    ...
    "my-app": MyAppPluginConfigAdapter(),
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

class MyAppPluginConfigAdapter(LLMConfigAdapter):
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
class MyAppPluginConfigAdapter(LLMConfigAdapter):
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
class MyAppPluginConfigAdapter(LLMConfigAdapter):
    async def sync_cache(
        self,
        *,
        session: AsyncSession,
        user_id: int,
        stored_config: dict[str, Any],
    ) -> None:
        await cache.delete(f"myappplugin:{user_id}")
```


## Plugin Name Derivation

You do **not** choose the plugin name freely. The `PluginLoader` instantiates each plugin with a name it derives from the class name (`_class_name_to_plugin_name` in `app/plugins/loader.py`): it strips a trailing `Plugin` suffix and kebab-cases the rest.

| Class name | Derived name |
|---|---|
| `CanvasPlugin` | `canvas` |
| `OpenEdxPlugin` | `open-edx` |
| `MyAppPlugin` | `my-app` |
| `Slack` (no suffix) | `slack` |

This derived name is what gets passed to your `__init__` and is the key you must use in `PLUGIN_CONFIG_CLASSES` and `PLUGIN_ADAPTERS`. Name your class so the derived name is what you want.


## Basic Plugin Structure

The loader constructs every plugin as `plugin_class(plugin_name)` (`app/plugins/loader.py`), so `__init__` **must accept the derived `plugin_name` as its first positional argument** and pass it straight through to `super().__init__()`. Do not hard-code the name.

```python
# app/core_plugins/myappplugin/plugin.py
from app.plugins.base import SparkthPlugin, tool
from fastapi import APIRouter
from app.core_plugins.myappplugin.config import MyAppPluginConfig

# Create router outside the class
router = APIRouter(prefix="/my-app", tags=["My Plugin"])

@router.get("/")
async def get_data():
    return {"message": "Hello from my plugin"}

@router.post("/items")
async def create_item(data: dict):
    return {"created": True}


# Plugin class
class MyAppPlugin(SparkthPlugin):
    def __init__(self, plugin_name: str) -> None:
        super().__init__(
            plugin_name,                  # name is supplied by the plugin loader
            MyAppPluginConfig,               # config_schema (positional)
            version="1.0.0",
            description="My plugin description",
        )
        # Add the router
        self.add_route(router)

    # MCP Tools using @tool decorator
    @tool(description="Process some input", category="utilities")
    async def process_data(self, input: str) -> str:
        """Process the input and return result."""
        return f"Processed: {input}"
```

### Where do plugin routes get mounted?

By default, plugin routes are served at **the path in the router's own `prefix`**, mounted at the application root — there is no automatic `/api/v1` prefix. The router above (`prefix="/my-app"`) is reachable at `http://localhost:7727/my-app/`.

To mount your routes under a different base, override `get_route_prefix()` on the plugin class (it returns `None` by default, meaning "root"). For example, the built-in `chat` plugin returns `"/api/v1"` so its routes land under `/api/v1/chat`.

## Register in core/config.py
```python
PLUGINS = [
    "app.core_plugins.canvas.plugin:CanvasPlugin",
    "app.core_plugins.openedx.plugin:OpenEdxPlugin",
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

class MyAppPlugin(SparkthPlugin):
    def __init__(self, plugin_name: str) -> None:
        super().__init__(plugin_name, MyAppPluginConfig)
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

# Plugin (class name WeatherPlugin → derived name "weather")
class WeatherPlugin(SparkthPlugin):
    def __init__(self, plugin_name: str) -> None:
        super().__init__(plugin_name, version="1.0.0")
        self.add_route(router)

    @tool(description="Get weather for a city", category="weather")
    async def get_weather(self, city: str) -> dict:
        return {"city": city, "temperature": 20, "unit": "celsius"}
```

## Testing

```bash
# Start the FastAPI server locally (http://0.0.0.0:7727)
make backend.up.dev

# Test API (routes mount at the router's own prefix by default — see below)
curl http://localhost:7727/my-app/
```

For real-world examples, see `core_plugins/canvas/` directory.
