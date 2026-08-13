# Architectural Patterns

Patterns that appear across multiple files in the Sparkth codebase.

---

## 1. Plugin System: Hook-Based Contribution

**Files:** `sparkth/lib/hooks.py`, `sparkth/lib/mcp/hooks.py`, `sparkth/lib/routes.py`, `sparkth/lib/config/hooks.py`, `sparkth/lib/analytics/hooks.py`, `sparkth/plugins/*/plugin.py`

A plugin contributes its capabilities from its `__init__` — one consistent pattern
across all contribution types (a `PluginCollectionHook` holds many items per plugin,
a `PluginHook` holds one; `sparkth/lib/hooks.py` also defines a `SingleNamedItemHook` —
a flat, name-keyed set not grouped by plugin — used for the permission/scope vocabulary):

```
SparkthPlugin.__init__          # super().__init__("my-app") declares the plugin name
  ├── register_router(self, router)                                   # sparkth/lib/routes.py
  ├── MCP_TOOLS.add_item(self, Tool(self.my_tool, category="..."))   # sparkth/lib/mcp/hooks.py
  ├── CONFIG_SCHEMAS.add_item(self, MyPluginConfig)                  # sparkth/lib/config/hooks.py
  ├── CONFIG_ADAPTERS.add_item(self, MyConfigAdapter())              # sparkth/lib/config/hooks.py
  ├── DISPLAY_INFO.add_item(self, DisplayInfo("My App", "..."))      # sparkth/lib/frontend/hooks.py
  ├── SIDEBAR_ENTRIES.add_item(self, SidebarEntry("My App", ...))    # sparkth/lib/frontend/hooks.py
  ├── FRONTEND_APPS.add_item(self, FrontendApp())                    # sparkth/lib/frontend/hooks.py
  └── register_event_schema(self, MyEvent)                           # sparkth/lib/analytics
```

Every plugin declares its own kebab-case name by passing it positionally to
`super().__init__()`; the loader (`sparkth/core/plugins/loader.py`) constructs each class
with no arguments and never derives a name from the class name.

`register_router` (`sparkth/lib/routes.py`) mounts the router at `/api/v1/<plugin-name>`,
deriving both the prefix and OpenAPI tags from the plugin instance automatically.

A `Tool` (`sparkth/lib/mcp/hooks.py`) derives its name from the handler method, its
description from the handler docstring, and its input schema from the signature.
Consumers iterate the hooks: `sparkth/mcp/main.py` registers `MCP_TOOLS` with the FastMCP
server, the chat tool registry converts them to LangChain tools, and `sparkth/main.py`
mounts plugin routes.

Every plugin also declares a `PluginConfig` (Pydantic model) that drives per-user configuration stored in the DB. See `sparkth/core/plugins/config_base.py` for the base class.

A plugin may also contribute a `CONFIG_ADAPTERS` entry (`sparkth/lib/config/hooks.py`): an
`LLMConfigAdapter` that pre/post-processes its stored config. `PluginService` resolves it by
plugin name via `get_plugin_adapter` (`sparkth/lib/config`), so the framework never names a concrete plugin.

A plugin may also register analytics event schemas via `register_event_schema(self, MyEvent)`
(`sparkth/lib/analytics`): self-describing `AnalyticsEventSchema` subclasses that declare their own
`event_type`/`version`. Registration runs at import time from the plugin's `__init__` and adds
to the `ANALYTICS_EVENTS` hook the gateway resolves against. `register_event_schema`
enforces three startup-fatal guards a plain permission does not need: the `event_type` must be
namespaced under the plugin name (`EventNamespaceError`), a different class on an existing
`(event_type, version)` is a `DuplicateEventTypeError`, and a schema missing its identity
ClassVars is a `TypeError`. All events are emitted server-side via `ingest_event`.

Plugin registration list lives at `sparkth/core/config.py:PLUGINS` as `"module.path:ClassName"` strings.

---

## 2. Plugin Lifecycle Management

**Files:** `sparkth/core/plugins/loader.py`, `sparkth/main.py` (`assemble_app()` + lifespan handler)

The `PluginLoader` singleton manages discovery → load → unload. Route registration is DB-free and happens in `assemble_app()` at import time, so the full route map (and OpenAPI schema) exists without a running server. The FastAPI lifespan context manager owns the stateful side: it calls `get_plugin_service().get_or_create_all()` on startup and unloads plugins on shutdown. Each plugin can contribute:

- **Routes:** via `register_router` (`sparkth/lib/routes.py`), mounted with `FastAPI.include_router()`
- **Middleware:** Starlette middleware
- **MCP tools:** via the `MCP_TOOLS` hook (see §1)

Two middlewares gate what a disabled plugin can still do, one per transport, both reading
the flag at request time rather than at registration:

- `PluginAccessMiddleware` (`sparkth/core/plugins/middleware.py`) gates **HTTP routes** on
  the caller's per-user plugin preference and the system-wide switch.
- `PluginToolAccessMiddleware` (`sparkth/mcp/access.py`) gates **MCP tools** on the
  system-wide switch alone — `/ai/mcp` has no authenticated caller (see §11).

---

## 3. FastAPI Layered Architecture

**Files:** `sparkth/main.py`, `sparkth/api/v1/`, `sparkth/services/`, `sparkth/core/db.py`

```
Request → Middleware → APIRouter → Endpoint function → Service layer → AsyncSession
```

- Endpoint functions stay thin; business logic lives in `sparkth/services/`
- All DB access is async: `AsyncSession` injected via `Depends(get_async_session)`
- Plugin routes are mounted dynamically by the plugin loader at startup

---

## 4. Dependency Injection via FastAPI `Depends`

**Files:** `sparkth/api/v1/auth.py`, `sparkth/api/v1/user.py`, `sparkth/core/db.py`

Auth and DB session are injected uniformly:

```python
async def endpoint(
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_async_session),
):
```

`get_current_user` validates the Bearer JWT and returns the `User` ORM object. This pattern is used in every protected endpoint.

---

## 5. Database: Async-First SQLModel

**Files:** `sparkth/core/db.py`, `sparkth/core/models/base.py`, `sparkth/core/models/*.py`

- A single `async_engine` (asyncpg) backs all application and CLI database access, obtained via `session_scope` / `get_async_session` (`sparkth/lib/db.py`)
- URL conversion handled in `db.py`: `postgresql://` → `postgresql+asyncpg://`
- Alembic migrations are the one exception: `sparkth/migrations/env.py` builds its own synchronous engine, converting the URL back to `postgresql://`
- SQLite used for tests; PostgreSQL for production
- All models inherit from `TimestampedModel` (adds `created_at`, `updated_at`) or `SoftDeleteModel` (adds `deleted_at`)

---

## 6. Settings: `pydantic-settings` Singleton

**File:** `sparkth/core/config.py`

`Settings` class loads from `.env` via pydantic-settings. `get_settings()` is wrapped with `@lru_cache` so configuration is loaded once per process. All modules import `get_settings()` rather than accessing env vars directly.

---

## 7. JWT + OAuth2 Authentication

**Files:** `sparkth/core/security.py`, `sparkth/api/v1/auth.py`, `sparkth/core/google_auth.py`

- Tokens: HS512, 8-day expiry, signed with `SECRET_KEY`
- Passwords: Argon2 via pwdlib
- Google OAuth2: Authlib OIDC flow; callback at `/api/v1/auth/google/callback`
- `HTTPBearer` security scheme used on all protected routes

---

## 8. Custom Exception Hierarchy

**File:** `sparkth/core/plugins/exceptions.py`

```
PluginError (base)
├── PluginLoadError
├── PluginValidationError
```

Plugin code raises typed exceptions; FastAPI translates them to `HTTPException` at the endpoint layer. MCP tools raise `AuthenticationError` for credential issues.

---

## 9. Chat Plugin: Service + LLM Layer + Encryption

**Files:** `sparkth/plugins/chat/service.py`, `sparkth/plugins/chat/intent_router.py`, `sparkth/plugins/chat/middleware.py`, `sparkth/llm/providers.py`, `sparkth/llm/service.py`, `sparkth/core/encryption.py`, `sparkth/core/cache.py`

- `ChatService` owns conversation logic and history management
- LLM backends (OpenAI, Anthropic, Google) are abstracted in the shared `sparkth/llm/` layer — `providers.py` (provider registry + valid models) and `service.py` — not inside the chat plugin
- `RAGIntentRouter` (`intent_router.py`) decides how to route a user turn
- Stored LLM API keys are encrypted at rest with Fernet via `EncryptionService` (`sparkth/core/encryption.py`); key from `LLM_ENCRYPTION_KEY`. Conversation contents themselves are not encrypted
- Redis (`sparkth/core/cache.py`) backs the rate limiting enforced in `chat/middleware.py` — per-minute request/chat limits and a concurrent-stream cap, configured in `chat/config.py`

---

## 10. Frontend: Lazy-Loaded Plugin Routes

**Files:** `frontend/lib/plugins/`, `frontend/app/dashboard/[pluginName]/page.tsx`, `frontend/plugins/index.ts`

Each frontend plugin exports a `PluginDefinition` with `loadComponent: () => import("./Plugin")`. The dashboard's dynamic route `[pluginName]` resolves the plugin from the registry and renders it via `next/dynamic`. `generateStaticParams()` returns the known plugin names so Next.js can pre-generate routes at build time.

---

## 11. MCP Tool Registration Pipeline

**Files:** `sparkth/mcp/server.py`, `sparkth/lib/mcp/hooks.py`

`register_plugin_tools()` iterates the `MCP_TOOLS` hook (each entry a `Tool` contributed by a plugin from its `__init__`), validates each tool against `MCPToolDefinition`, and registers it with the `FastMCP` instance. The server is mounted on the FastAPI app (`sparkth/main.py`) and served over HTTP at `/ai/mcp`; `register_plugin_tools()` runs once during the app's lifespan startup.

Registration stamps the contributing plugin's name into the tool's FastMCP `meta`
(`PLUGIN_NAME_META_KEY`), which is what lets `PluginToolAccessMiddleware`
(`sparkth/mcp/access.py`) resolve ownership per call — the same stamp-then-read shape
`register_router` uses for plugin endpoints. Because tools register once but `Plugin.enabled`
flips at runtime, the gate queries the flag on every `tools/call` and `tools/list` rather than
filtering the registration. The two failure modes are deliberately opposite: a database error
refuses a **call** (fail closed) but leaves a **listing** unfiltered, since the lifespan lists
tools to log its startup count and a raising filter would crash startup.

Server middleware order matters: `ToolCallAuditMiddleware` is added first and therefore runs
outermost, so calls the access gate refuses still leave an audit record.
