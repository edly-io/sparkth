# Sparkth Plugin Guide

Quick guide for creating Sparkth plugins with API routes and MCP tools.


## Plugin Config Definition
Define a config class for the plugin that must inherit from `sparkth.lib.plugins:PluginConfig`

```python
# sparkth/plugins/myappplugin/config.py
from pydantic import Field
from sparkth.lib.plugins import PluginConfig

class MyAppPluginConfig(PluginConfig):
    config_field: str = Field(..., description="...")

    # define additional fields as required
```

### LLM-Aware Plugins

If your plugin lets users pick an AI model to power some feature (e.g. answer synthesis, content generation), add `llm_config_id` and `llm_model_override` to the config class. These two fields work as a pair: `llm_config_id` points to one of the user's saved LLM configurations (provider + API key), and `llm_model_override` lets them swap in a different model from the same provider without creating a new configuration.

```python
# sparkth/plugins/myappplugin/config.py
from pydantic import Field
from sparkth.lib.plugins import PluginConfig

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

Valid `llm_model_override` values must be a legal model for the linked `LLMConfig`'s provider. The single source of truth is `PROVIDER_MODELS` in `sparkth/llm/providers.py`.


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

Both methods default to `None` on the base class, so non-LMS plugins require no changes. The injection is fully automatic once the config class is contributed to the `CONFIG_SCHEMAS` hook (see below).


## Register the plugin configuration class

Register a Pydantic configuration class when your plugin has user-configurable settings that the system should validate and normalize — and always for LMS plugins that rely on credential injection. Plugins with no user-facing configuration can skip this entirely.

When you do register one, contribute your config class to the `CONFIG_SCHEMAS` hook from your plugin's `__init__`, right after calling `super().__init__(...)`. The system resolves config classes by the plugin's _derived_ name (the value passed to `__init__` — see [Plugin Name Derivation](#plugin-name-derivation) below), so no name string is needed at the call site.

```python
# sparkth/plugins/myappplugin/plugin.py

from sparkth.plugins.myappplugin.config import MyAppPluginConfig
from sparkth.lib.config.hooks import CONFIG_SCHEMAS
from sparkth.lib.plugins import SparkthPlugin


class MyAppPlugin(SparkthPlugin):
    def __init__(self, plugin_name: str) -> None:
        super().__init__(plugin_name)
        CONFIG_SCHEMAS.add_item(self, MyAppPluginConfig)
```


## Plugin Config Adapters (LLM-Aware Plugins)

If your plugin config includes `llm_config_id` and `llm_model_override`, register a config adapter so the system validates them at write time and resolves them for the frontend at read time. Without an adapter the fields are stored as plain values with no cross-field checks.

### What the adapter does

`LLMConfigAdapter` (import from `sparkth.lib.llm`) hooks into the config pipeline via three
methods — `preprocess_config` (validates on save), `postprocess_config` (resolves read-only
fields for the frontend), and `sync_cache` (a no-op override point for cache invalidation).
See the [`LLMConfigAdapter` reference](../reference/lib.md#llm) for the exact signatures and
behaviour.

### Adding an adapter for your plugin

**1. Create the adapter class**

For the default behaviour (LLM config ownership check + model override validation) a thin subclass is all you need:

```python
# sparkth/plugins/myappplugin/adapter.py
from sparkth.llm.adapter import LLMConfigAdapter

class MyAppPluginConfigAdapter(LLMConfigAdapter):
    pass
```

**2. Register it in `CONFIG_ADAPTERS`**

In your plugin's `__init__`, add the adapter alongside the config schema:

```python
# sparkth/plugins/myappplugin/plugin.py
from sparkth.plugins.myappplugin.adapter import MyAppPluginConfigAdapter
from sparkth.plugins.myappplugin.config import MyAppPluginConfig
from sparkth.lib.config.hooks import CONFIG_ADAPTERS, CONFIG_SCHEMAS
from sparkth.lib.plugins import SparkthPlugin


class MyAppPlugin(SparkthPlugin):
    def __init__(self, plugin_name: str) -> None:
        super().__init__(plugin_name)
        CONFIG_SCHEMAS.add_item(self, MyAppPluginConfig)
        CONFIG_ADAPTERS.add_item(self, MyAppPluginConfigAdapter())
```

That's it. `preprocess_config` and `postprocess_config` are now wired in automatically for every POST and PUT to your plugin's config endpoint.

### Overriding adapter methods

Override a method when the default behaviour isn't enough. Always call `super()` first in `preprocess_config` and `postprocess_config` so the base LLM validation still runs.

**Custom preprocessing** — validate an extra field before saving:

```python
from typing import Any
from sqlmodel.ext.asyncio.session import AsyncSession
from sparkth.llm.adapter import LLMConfigAdapter

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

You do **not** choose the plugin name freely. The `PluginLoader` instantiates each plugin with a name it derives from the class name (`_class_name_to_plugin_name` in `sparkth/core/plugins/loader.py`): it strips a trailing `Plugin` suffix and kebab-cases the rest.

| Class name | Derived name |
|---|---|
| `CanvasPlugin` | `canvas` |
| `OpenEdxPlugin` | `open-edx` |
| `MyAppPlugin` | `my-app` |
| `Slack` (no suffix) | `slack` |

This derived name is what gets passed to your `__init__`, what the `CONFIG_SCHEMAS` hook resolves config classes by, and what `get_plugin_adapter` uses to look up your adapter from `CONFIG_ADAPTERS`. Name your class so the derived name is what you want.


## Basic Plugin Structure

The loader constructs every plugin as `plugin_class(plugin_name)` (`sparkth/core/plugins/loader.py`), so `__init__` **must accept the derived `plugin_name` as its first positional argument** and pass it straight through to `super().__init__()`. Do not hard-code the name.

A plugin contributes its capabilities from its `__init__`:
routes via `register_router`, MCP tools to `MCP_TOOLS`, a config schema to `CONFIG_SCHEMAS`, permissions via `Permission.create`, scope kinds via `PermissionScope.create` / `ObjectlessPermissionScope.create`, analytics event schemas via `register_event_schema` and exception→HTTP mappings via `register_status` / `register_exception_handler`.

```python
# sparkth/plugins/myappplugin/plugin.py
from fastapi import APIRouter

from sparkth.plugins.myappplugin.config import MyAppPluginConfig
from sparkth.lib.analytics import AnalyticsEventSchema, register_event_schema
from sparkth.lib.config.hooks import CONFIG_SCHEMAS
from sparkth.lib.mcp.hooks import MCP_TOOLS, Tool
from sparkth.lib.permissions import Permission
from sparkth.lib.routes import register_router
from sparkth.lib.plugins import SparkthPlugin

# Create router outside the class
router = APIRouter()

@router.get("/")
async def get_data():
    return {"message": "Hello from my plugin"}


# An analytics event this plugin emits. `event_type` MUST be namespaced under the
# plugin name; `version` lets the payload evolve without breaking older producers.
class MyAppDataProcessed(AnalyticsEventSchema):
    event_type = "myappplugin.data_processed"
    version = 1

    input_length: int


# Plugin class
class MyAppPlugin(SparkthPlugin):
    def __init__(self, plugin_name: str) -> None:
        super().__init__(plugin_name)  # name is supplied by the plugin loader
        CONFIG_SCHEMAS.add_item(self, MyAppPluginConfig)
        register_router(self, router)
        MCP_TOOLS.add_item(self, Tool(process_data, category="utilities"))
        Permission.create("myapp.process")
        register_event_schema(self, MyAppDataProcessed)

async def process_data(input: str) -> str:
    """Process some input and return the result."""
    return f"Processed: {input}"
```

Scope kinds register the same way, through `PermissionScope.create("course", parent=...)` (or `ObjectlessPermissionScope.create(...)` for a singleton scope) — the scope classes come from `sparkth.lib.permissions.scopes`. See the [permissions guide](permissions.md) for how scope hierarchy and assignments work.

Analytics event schemas register through `register_event_schema(self, MyEvent)`: define an `AnalyticsEventSchema` subclass (from `sparkth.lib.analytics`) declaring its own `event_type` and `version`, then register it from `__init__`. The `event_type` **must** be namespaced under the plugin's name (`"myappplugin.data_processed"`), or registration raises `EventNamespaceError` at import; a second class claiming the same `(event_type, version)` raises `DuplicateEventTypeError`. Emit a registered event server-side with `ingest_event` (also from `sparkth.lib.analytics`). See the "Analytics Event Schemas" section of the project README for the full write path.

### Where do plugin routes get mounted?

`register_router` mounts the router at `/api/v1/<plugin-name>` automatically, derived
from the plugin instance. The router above is reachable at
`http://localhost:7727/api/v1/my-app/`.

### Rendering plugin exceptions as HTTP responses

A plugin's domain exceptions stay HTTP-agnostic (plain `Exception` subclasses). To control
how one renders as an HTTP response, map it to a status from `__init__` — the mapping is wired
onto the app at startup:

```python
from sparkth.lib.exceptions.handlers import register_exception_handler

class MyAppError(Exception):
    """Raised when the plugin cannot process a request."""

# inside MyAppPlugin.__init__:
register_exception_handler(MyAppError, 409)
```

Now any route that raises `MyAppError` returns `409` with `{"detail": str(exc)}` — no
per-route `try/except`. A mapping on a base exception also catches its subclasses.

## Register in core/config.py
```python
PLUGINS = [
    "sparkth.plugins.canvas.plugin:CanvasPlugin",
    "sparkth.plugins.openedx.plugin:OpenEdxPlugin",
    # add your plugin here
]
```

Format: `"path.to.module:ClassName"`

## Adding Database Models (Optional)

Define your models as `table=True` SQLModel classes and import them at the top
of your plugin module. Importing the module registers the tables in
`SQLModel.metadata`, which is all Alembic autogenerate needs — there is no
separate registration step.

```python
# Importing the model registers its table in SQLModel.metadata for Alembic.
from sparkth.plugins.my_app.models import MyModel  # noqa: F401


class MyAppPlugin(SparkthPlugin):
    def __init__(self, plugin_name: str) -> None:
        super().__init__(plugin_name)
        CONFIG_SCHEMAS.add_item(self, MyAppPluginConfig)
        register_router(self, router)
```

Then create migration:
```bash
alembic revision --autogenerate -m "my_plugin_add_model"
alembic upgrade head
```

## MCP Tools

A tool is a plugin method registered with the `MCP_TOOLS` hook via a `Tool`
(`sparkth/lib/mcp/hooks.py`). The tool's **name** is the method name, its **description**
is the method's docstring, and its input schema is auto-generated from the signature.
Register each tool in `__init__`; pass an optional `category` to group it.

```python
class MyAppPlugin(SparkthPlugin):
    def __init__(self, plugin_name: str) -> None:
        super().__init__(plugin_name)
        MCP_TOOLS.add_item(self, Tool(my_tool, category="my-category"))

async def my_tool(param1: str, param2: int = 0) -> dict:
    """One-line summary the LLM sees as the tool description.

    Args:
        param1: First parameter
        param2: Optional parameter
    """
    return {"result": f"{param1}-{param2}"}
```

When a plugin has many tools, register them with a loop:

```python
tools: list[tuple[Callable[..., Any], str]] = [
    (my_tool, "my-category"),
    (other_tool, "my-category"),
]
for handler, category in tools:
    MCP_TOOLS.add_item(self, Tool(handler, category=category))
```

### Tool executions are audited

`Tool` wraps the handler with `sparkth.lib.audit.audited_tool` at
construction: every execution, on every surface (the MCP server, chat, RAG),
records a `tool.invoked` event *before* the handler runs and a
`tool.completed` or `tool.failed` event after. Handlers must be `async`; the
wrapper rejects a sync handler with a `TypeError` at construction. The write
is fail-closed: if the invocation record cannot be committed, the tool call
is refused with `sparkth.lib.audit.exceptions.AuditCaptureError`. Tool
arguments are redacted before persistence (any `auth` payload and secret-named
keys like `token` or `password` are replaced wholesale), and exception
messages recorded on failure are scrubbed of secret-keyed values and length
bounded, but do not put secrets or free-text PII in argument names or values
that redaction cannot recognize. Handlers need no audit code of their own.

## Complete Example

```python
from fastapi import APIRouter

from sparkth.lib.mcp.hooks import MCP_TOOLS, Tool
from sparkth.lib.routes import register_router
from sparkth.lib.plugins import SparkthPlugin

# Router
router = APIRouter()

@router.get("/{city}")
async def get_weather_route(city: str):
    return {"city": city, "temp": 20}

# Plugin (class name WeatherPlugin → derived name "weather")
class WeatherPlugin(SparkthPlugin):
    def __init__(self, plugin_name: str) -> None:
        super().__init__(plugin_name)
        register_router(self, router)
        MCP_TOOLS.add_item(self, Tool(self.get_weather, category="weather"))

    async def get_weather(self, city: str) -> dict:
        """Get the current weather for a city."""
        return {"city": city, "temperature": 20, "unit": "celsius"}
```

## Testing

```bash
# Start the FastAPI server locally (http://0.0.0.0:7727)
make backend.up.dev

# Test API (routes mount at /api/v1/<plugin-name>)
curl http://localhost:7727/api/v1/my-app/
```

For real-world examples, see the `sparkth/plugins/canvas/` directory.
