# Architectural Patterns

Patterns that appear across multiple files in the Sparkth codebase.

---

## 1. Plugin System: Metaclass-Driven Tool Registration

**Files:** `app/plugins/base.py`, `app/core_plugins/*/plugin.py`

`PluginMeta` metaclass collects `@tool`-decorated methods at class definition time into `_tool_registry`. On instantiation, these are automatically registered as MCP tools — no manual wiring required.

```
SparkthPlugin (metaclass=PluginMeta)
  └── @tool(description="...", category="...")
      → auto-registered in _tool_registry at class definition
      → registered as MCP tool on plugin enable
```

Every plugin also declares a `PluginConfig` (Pydantic model) that drives per-user configuration stored in the DB. See `app/plugins/config_base.py` for the base class.

Plugin registration list lives at `app/core/config.py:PLUGINS` as `"module.path:ClassName"` strings.

---

## 2. Plugin Lifecycle Management

**Files:** `app/plugins/loader.py`, `app/main.py` (lifespan handler)

The `PluginLoader` singleton manages discovery → load → unload. The FastAPI lifespan context manager calls `get_plugin_service().get_or_create_all()` on startup and cleanup on shutdown. Each plugin can contribute:

- **Routes:** `FastAPI.include_router()`
- **Models:** SQLModel table classes
- **Middleware:** Starlette middleware
- **MCP tools:** Via `@tool` decorator
- **Dependencies:** Callable factories

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
├── PluginNotFoundError
├── PluginLoadError
├── PluginValidationError
├── PluginDependencyError
├── PluginAlreadyLoadedError
├── PluginNotLoadedError
└── PluginConfigError
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

**Files:** `app/mcp/main.py`, `app/mcp/server.py`

`register_plugin_tools()` iterates all enabled plugins, validates each tool against `MCPToolDefinition`, and registers it with the `FastMCP` instance. Transport is configurable: HTTP (default, port 7727) for network clients; stdio for local AI agent integrations.
