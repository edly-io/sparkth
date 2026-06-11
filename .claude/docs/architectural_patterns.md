# Architectural Patterns

Patterns that appear across multiple files in the Sparkth codebase.

---

## 1. Plugin System: Hook-Based Contribution

**Files:** `app/lib/hooks.py`, `app/lib/mcp/hooks.py`, `app/lib/routes.py`, `app/lib/config/hooks.py`, `app/core_plugins/*/plugin.py`

A plugin contributes its capabilities from its `__init__` — one consistent pattern
across all contribution types (a `PluginCollectionHook` holds many items per plugin,
a `PluginHook` holds one):

```
SparkthPlugin.__init__
  ├── register_router(self, router)                                   # app/lib/routes.py
  ├── MCP_TOOLS.add_item(self, Tool(self.my_tool, category="..."))   # app/lib/mcp/hooks.py
  └── CONFIG_SCHEMAS.add_item(self, MyPluginConfig)                  # app/lib/config/hooks.py
```

`register_router` (`app/lib/routes.py`) mounts the router at `/api/v1/<plugin-name>`,
deriving both the prefix and OpenAPI tags from the plugin instance automatically.

A `Tool` (`app/lib/mcp/hooks.py`) derives its name from the handler method, its
description from the handler docstring, and its input schema from the signature.
Consumers iterate the hooks: `app/mcp/main.py` registers `MCP_TOOLS` with the FastMCP
server, the chat tool registry converts them to LangChain tools, and `app/main.py`
mounts plugin routes.

Every plugin also declares a `PluginConfig` (Pydantic model) that drives per-user configuration stored in the DB. See `app/plugins/config_base.py` for the base class.

Plugin registration list lives at `app/core/config.py:PLUGINS` as `"module.path:ClassName"` strings.

---

## 2. Plugin Lifecycle Management

**Files:** `app/plugins/loader.py`, `app/main.py` (`assemble_app()` + lifespan handler)

The `PluginLoader` singleton manages discovery → load → unload. Route registration is DB-free and happens in `assemble_app()` at import time, so the full route map (and OpenAPI schema) exists without a running server. The FastAPI lifespan context manager owns the stateful side: it calls `get_plugin_service().get_or_create_all()` on startup and unloads plugins on shutdown. Each plugin can contribute:

- **Routes:** via `register_router` (`app/lib/routes.py`), mounted with `FastAPI.include_router()`
- **Middleware:** Starlette middleware
- **MCP tools:** via the `MCP_TOOLS` hook (see §1)

`PluginAccessMiddleware` (`app/plugins/middleware.py`) gates tool access based on per-user plugin config at request time.

---

## 3. FastAPI Layered Architecture

**Files:** `app/main.py`, `app/api/v1/`, `app/services/`, `app/core/db.py`

```
Request → Middleware → APIRouter → Endpoint function → Service layer → AsyncSession
```

- Endpoint functions stay thin; business logic lives in `app/services/`
- All DB access is async: `AsyncSession` injected via `Depends(get_async_session)`
- Plugin routes are mounted dynamically by the plugin loader at startup

---

## 4. Dependency Injection via FastAPI `Depends`

**Files:** `app/api/v1/auth.py`, `app/api/v1/user.py`, `app/core/db.py`

Auth and DB session are injected uniformly:

```python
async def endpoint(
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_async_session),
):
```

`get_current_user` validates the Bearer JWT and returns the `User` ORM object. This pattern is used in every protected endpoint.

---

## 5. Database: Async-First SQLModel + Dual Engines

**Files:** `app/core/db.py`, `app/models/base.py`, `app/models/*.py`

- Two engines: `async_engine` (asyncpg, used by FastAPI) and `sync_engine` (used by CLI/migrations)
- URL conversion handled in `db.py`: `postgresql://` → `postgresql+asyncpg://`
- SQLite used for tests; PostgreSQL for production
- All models inherit from `TimestampedModel` (adds `created_at`, `updated_at`) or `SoftDeleteModel` (adds `deleted_at`)

---

## 6. Settings: `pydantic-settings` Singleton

**File:** `app/core/config.py`

`Settings` class loads from `.env` via pydantic-settings. `get_settings()` is wrapped with `@lru_cache` so configuration is loaded once per process. All modules import `get_settings()` rather than accessing env vars directly.

---

## 7. JWT + OAuth2 Authentication

**Files:** `app/core/security.py`, `app/api/v1/auth.py`, `app/core/google_auth.py`

- Tokens: HS512, 8-day expiry, signed with `SECRET_KEY`
- Passwords: Argon2 via pwdlib
- Google OAuth2: Authlib OIDC flow; callback at `/api/v1/auth/google/callback`
- `HTTPBearer` security scheme used on all protected routes

---

## 8. Custom Exception Hierarchy

**File:** `app/plugins/exceptions.py`

```
PluginError (base)
├── PluginLoadError
├── PluginValidationError
```

Plugin code raises typed exceptions; FastAPI translates them to `HTTPException` at the endpoint layer. MCP tools raise `AuthenticationError` for credential issues.

---

## 9. Chat Plugin: Service + LLM Layer + Encryption

**Files:** `app/core_plugins/chat/service.py`, `app/core_plugins/chat/intent_router.py`, `app/core_plugins/chat/middleware.py`, `app/llm/providers.py`, `app/llm/service.py`, `app/core/encryption.py`, `app/core/cache.py`

- `ChatService` owns conversation logic and history management
- LLM backends (OpenAI, Anthropic, Google) are abstracted in the shared `app/llm/` layer — `providers.py` (provider registry + valid models) and `service.py` — not inside the chat plugin
- `RAGIntentRouter` (`intent_router.py`) decides how to route a user turn
- Stored LLM API keys are encrypted at rest with Fernet via `EncryptionService` (`app/core/encryption.py`); key from `LLM_ENCRYPTION_KEY`. Conversation contents themselves are not encrypted
- Redis (`app/core/cache.py`) backs the rate limiting enforced in `chat/middleware.py` — per-minute request/chat limits and a concurrent-stream cap, configured in `chat/config.py`

---

## 10. Frontend: Lazy-Loaded Plugin Routes

**Files:** `frontend/lib/plugins/`, `frontend/app/dashboard/[pluginName]/page.tsx`, `frontend/plugins/index.ts`

Each frontend plugin exports a `PluginDefinition` with `loadComponent: () => import("./Plugin")`. The dashboard's dynamic route `[pluginName]` resolves the plugin from the registry and renders it via `next/dynamic`. `generateStaticParams()` returns the known plugin names so Next.js can pre-generate routes at build time.

---

## 11. MCP Tool Registration Pipeline

**Files:** `app/mcp/server.py`, `app/lib/mcp/hooks.py`

`register_plugin_tools()` iterates the `MCP_TOOLS` hook (each entry a `Tool` contributed by a plugin from its `__init__`), validates each tool against `MCPToolDefinition`, and registers it with the `FastMCP` instance. The server is mounted on the FastAPI app (`app/main.py`) and served over HTTP at `/ai/mcp`; `register_plugin_tools()` runs once during the app's lifespan startup.
