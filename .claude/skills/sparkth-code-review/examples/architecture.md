# Architecture

Real review comments from Sparkth pull requests: layering, dependency direction, core/lib/plugin boundaries,
data-model design.

## Example 1

**Issue:** RAG service getter duplicated in slack and chat plugins; should live in a shared library.

`app/core_plugins/chat/routes/dependencies.py`

```diff
+@lru_cache  # singleton by design — mirrors app.core.config.get_settings(); call .cache_clear() in tests that mutate env vars
+def get_chat_system_config() -> ChatSystemConfig:
+    """Dependency to get chat system configuration from environment variables."""
+    return ChatSystemConfig()
+
+
+def get_chat_service() -> ChatService:
+    """Dependency to get chat service."""
+    return ChatService()
+
+
+def get_rag_context_service() -> RAGContextService:
```

**Review:**

> There's already a `_get_rag_service()` function in the slack plugin and a `get_rag_context_service()` in the chat
> plugin `routes.py`. This tells us that this function should really be part of a shared library.

## Example 2

**Issue:** Chat plugin tests define Slack settings though Slack depends on chat, not vice versa.

`app/core_plugins/chat/tests/conftest.py`

```diff
+from typing import Any, cast
+from unittest.mock import MagicMock
+
+# Set test environment variables BEFORE importing app modules.
+os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///:memory:")
+os.environ.setdefault("SECRET_KEY", "test-secret-key")
+os.environ.setdefault("RAG_MCP_URL", "http://localhost:8000")
+os.environ.setdefault("LLM_ENCRYPTION_KEY", "QL9oJuLxl0gKCbJpQgkzrdlsZUmvIVR3Cp0gSPcVLvQ=")
+os.environ.setdefault("SLACK_CLIENT_ID", "test-slack-client-id")
+os.environ.setdefault("SLACK_CLIENT_SECRET", "test-slack-client-secret")
+os.environ.setdefault("SLACK_SIGNING_SECRET", "test-slack-signing-secret")
+os.environ.setdefault("SLACK_REDIRECT_URI", "http://localhost:7727/api/v1/slack/callback")
```

**Review:**

> Why does the chat plugin need to define Slack settings? In my understanding the Slack plugin depends on the chat
> plugin, but not vice-versa.

## Example 3

**Issue:** Slack OAuth env vars still live in core Settings, leaking plugin internals; move them to the plugin config.

`app/core_plugins/slack/config.py`

```diff
@@ -1,10 +1,45 @@
 """Configuration for the Slack TA Bot plugin."""
```

**Review:**

> In the `main` branch's `app.core.config` still has the following slack plugin related envs, this leaks the slack
> plugin's internal implementation to the core of the application. Lets move them to the plugin's config.
>
> NOTE: I am assuming that the following envs are only specific to the slack plugin, let me know otherwise
>
> ```
> # Slack TA Bot OAuth
> SLACK_CLIENT_ID: str = ""
> SLACK_CLIENT_SECRET: str = ""
> SLACK_SIGNING_SECRET: str = ""
> SLACK_REDIRECT_URI: str = ""
> ```

## Example 4

**Issue:** get_plugin_settings returns a hard-coded plugin list in core; should plugin discovery be a new function?

`app/plugins/loader.py`

```diff
+    def iter_plugin_classes(self) -> Iterator[tuple[str, Type[SparkthPlugin]]]:
+        """
+        Discover all plugins defined in get_plugin_settings().
+
+        Yields:
+            (name, class) tuples
+
+        Note:
+            All plugins are enabled by default.
+            Format: "module.path:ClassName"
+        """
+        for module_string in get_plugin_settings():
```

**Review:**

> the `app.core.config.get_plugin_settings` returns a list of hard-coded plugin paths. Any time a new plugin is
> created, this `list` inside the core of sparkth will have to be updated. I believe we are trying to fix this in our
> refactoring effort .
>
> My question is that should we be using this function here? or should we come up with a better way of discovering
> plugin module paths, since we already have a PR for this, might as well create a new function for discovering
> plugins.

## Example 5

**Issue:** Moving all of app/rag into lib exposes every function as public API; library APIs must be curated.

**Review:**

> The goal of the app/lib modules are to be used by other modules and plugins. If you move the entire app/rag/
> directory, then it means that every function in there is an API for other modules and plugins -- which defeats the
> purpose of a library. This is why we would have to think long and hard about the library APIs that we want to expose
> for each feature.
>
> Does that make sense?

## Example 6

**Issue:** lib/rag.py imports make internal functions importable as public API; unauthorised imports undetectable;
expose only intended subset.

`app/lib/rag.py`

```diff
+    DriveFileNotFoundError,
+    RAGNotReadyError,
+    RAGRetrievalError,
+    ScannedPDFError,
+    UnsupportedFileTypeError,
+)
+from app.rag.ingestion.chunking import DocumentChunker
+from app.rag.ingestion.extraction import check_extraction_eligibility, extract_to_markdown
+from app.rag.retrieval import get_context_via_agent_with_isolated_session
+from app.rag.retrieval.utils import validate_files_ready
+from app.rag.store import ChunkStoreService, store_and_link_chunks
+from app.rag.types import IngestionResult, RetrievedChunk  # noqa: F401 — re-exported in __all__
```

**Review:**

> All these items which are imported are then going to be importable from the library module:
>
> 1. This is making the API confusing for developers
> 2. We won't be able to catch unauthorised imports, such as `from app.lib.rag import validate_files_ready`, just by
> looking at the import statement
> 3. We are exposing internal functions to end users.
>
> I wonder if we should move the exported modules outside of lib/ and then re-import them here. I'm not sure what the
> good practices are to make a subset of objects importable. Not sure if `__all__` resolves this.

## Example 7

**Issue:** Source RagStatus values from the backend to avoid drift from frontend-defined copies.

`frontend/lib/drive.ts`

```diff
   limit: number;
 }
 
-async function handleError(message: string, response: Response) {
-  const text = await response.text();
-  let detail = text;
-  try {
-    const json = JSON.parse(text);
-    if (json.detail) detail = json.detail;
-  } catch {
-    // use raw text
+export const RagStatus = {
```

**Review:**

> could there be a way where we could get these from the backend?
> Defining them here separately would put this at risk of drifting apart from the backend over time.

## Example 8

**Issue:** Gate role reads with a role-scoped permission instead of global scope.

`app/api/v1/permissions/routes.py`

```diff
+    """Create a role. Returns the created RoleResponse (id, name, description, permissions)."""
+    try:
+        role = await create_role(payload.name, payload.description, session)
+    except RoleAlreadyExists as exc:
+        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from None
+    return await _role_to_response(role, session)
+
+
+@router.get(
+    "/roles/{role_id}",
+    response_model=RoleResponse,
+    dependencies=[Depends(RequirePermission("role.read", "global"))],
```

**Review:**

> Why is the permission here not scoped to the current role? I.e:
>
> ```
> RequirePermission("role.read", "role", role_id)
> ```

## Example 9

**Issue:** Merge Permission and PERMISSIONS into one module, removing the HasName indirection layer.

`app/core/permissions/hooks.py`

```diff
@@ -0,0 +1,15 @@
+from app.lib.hooks import HasName, UniqueCollectionHook
+
+# The hooks are typed by the shared ``HasName`` bound rather than the concrete
+# ``Permission`` / ``PermissionScope`` classes, so this module stays free of any
+# app.core.permissions import.
```

**Review:**

> This construct is a little weird. If `Permission` and `PERMISSIONS` truly depend on each other, let's just put them
> both in the same module, no? This would allow us to get rid of this "HasName" layer of indirection.

## Example 10

**Issue:** Explicit registry init call signals the registry duplicates the PERMISSION_SCOPES hook; remove it.

`app/cli/roles.py`

```diff
-    if scope != _SCOPE_GLOBAL and scope_object_id is None:
+    if scope != GLOBAL.name and scope_object_id is None:
         typer.secho("--scope-object-id is required for non-global scopes", fg=typer.colors.RED)
         raise typer.Exit(code=1)
-    if scope == _SCOPE_GLOBAL and scope_object_id is not None:
+    if scope == GLOBAL.name and scope_object_id is not None:
         typer.secho("--scope-object-id is not allowed for the global scope", fg=typer.colors.RED)
         raise typer.Exit(code=1)
+    # Validate the scope kind against the registered vocabulary so a mistyped --scope
+    # fails loudly instead of persisting a no-op assignment.
+    get_plugin_loader()
+    initialize_permission_scopes_registry()
```

**Review:**

> The fact that we need to explicitly call this function really tells us that we need to get rid of it. The registry
> only duplicates the data that is container in the PERMISSION_SCOPES hook.

## Example 11

**Issue:** Avoid TYPE_CHECKING; it hides a circular dependency that must be resolved.

`app/core/permissions/utils.py`

```diff
 from sqlalchemy import ColumnElement
 from sqlalchemy.exc import IntegrityError
 from sqlmodel import col, select
 from sqlmodel.ext.asyncio.session import AsyncSession
 
-from app.core.permissions import Permission
 from app.core.permissions.exceptions import RoleNotFound
 from app.core.permissions.models import Role, RoleAssignment, RolePermission
 from app.core.permissions.scopes import PermissionScope
 from app.models.user import User
 
+if TYPE_CHECKING:
```

**Review:**

> Ouch... I'd really like to avoid `TYPE_CHECKING` if possible at all. This points to a circular dependency issue,
> which must be resolved.

## Example 12

**Issue:** Anonymous actor with username is contradictory; attribute audit to immutable user ID, not mutable username.

`app/api/v1/auth.py`

```diff
@@ -173,22 +174,44 @@ async def login_for_access_token(
     result = await session.exec(select(User).where(User.username == form_data.username))
     user = result.one_or_none()
 
+    # Audit writes are fail-closed and committed independently of this request
+    # (record_event_now), so a failed attempt stays on record despite the 401.
+    attempted_actor = AuditActor(type="anonymous", label=form_data.username)
```

**Review:**

> How's this an anonymous actor but with a username? And do we really want to tie audit actor to a username, which is
> a mutable field? Instead we should use the user ID, no?

## Example 13

**Issue:** Create a hook so app and plugins can add middlewares, applied in assemble_app.

`sparkth/main.py`

```diff
@@ -109,6 +111,9 @@ def assemble_app(lifespan: Lifespan[FastAPI] | None = None) -> FastAPI:
             "/api/v1/auth",
         ],
     )
+    # Added after PluginAccessMiddleware so it wraps it (outermost): the audit
+    # context must exist before any other middleware or handler runs.
+    application.add_middleware(AuditContextMiddleware)
```

**Review:**

> What this tells us is that we need to create a new hook to which the app and plugins can add their own middlewares,
> which will then be added at runtime in `assemble_app`.

## Example 14

**Issue:** Request fields should exist only on request contexts; build the audit context after authentication.

`app/core/audit/context.py`

```diff
+    label: str | None = None
+
+
+@dataclass(slots=True)
+class AuditContext:
+    """Request-scoped origin metadata merged into every recorded event."""
+
+    request_id: str | None = None
+    request_ip: str | None = None
+    user_agent: str | None = None
+    source: AuditSource = AuditSource.SYSTEM
+    actor: AuditActor | None = None
```

**Review:**

> `request_*` and user_agent fields should be available (and not None) only on AuditRequestContext objects. If `actor`
> is available only after authentication, then we should build the audit context after authentication, no?

## Example 15

**Issue:** Recording calls to nonexistent tools adds complexity; middleware and audited_tool_handler decorator
duplicate each other.

`sparkth/mcp/audit.py`

```diff
@@ -0,0 +1,52 @@
+"""Protocol-level audit backstop for the FastMCP server.
+
+Successful tool calls (and handler-raised failures) are recorded by the
+audited handler wrapper (:func:`sparkth.lib.audit.audited_tool_handler`); this
+middleware covers the calls that never reach a handler (unknown tool names
+and input-validation rejections), so every ``tools/call`` on ``/ai/mcp``
+leaves a record either way (ADR-0002 seam table row three).
```

**Review:**

> I don't understand the point of tracking calls to tools that do not exist. This adds extra complexity without any
> visible gain. The way I see it, this is causing us to record things that did not happen. But I might be missing some
> context?
>
> And if we do want to keep track of non-existing tool calls, then we should keep this middleware but get rid of the
> audited_tool_handler decorator. The decorator forces developers to wrap all tools, while the middleware
> automatically captures all calls. Isn't that a duplicated feature?

## Example 16

**Issue:** Enforce unique tool names in the MCP hook instead of adding a handler module column.

`sparkth/core/audit/execution.py`

```diff
+    returned unchanged, so seams can wrap defensively.
+
+    Raises (from the returned wrapper):
+        sqlalchemy.exc.SQLAlchemyError: The ``tool.invoked`` write failed; the
+            handler was **not** executed (fail-closed refusal).
+    """
+    if getattr(handler, "__audit_wrapped__", False):
+        return handler
+
+    @functools.wraps(handler)
+    async def audited(*args: Any, **kwargs: Any) -> Any:
+        call = AuditToolCall(name=handler.__name__, args=_named_jsonable_args(handler, args, kwargs))
```

**Review:**

> Instead of adding `handler.__module__` as a column could we enforce unique tool names in the MCP hook? WDYS

## Example 17

**Issue:** Nit: typer.Exit raised in non-CLI helper functions is a refactoring footgun.

`sparkth/cli/groups.py`

```diff
+    database layer is async; this is the awaited implementation. Exits non-zero if the
+    group or role is missing, the scope kind is unknown, or the scope and object id
+    contradict each other (enforced by the engine's assign_role_to_group).
+    """
+    # Load plugins first so plugin-declared scope kinds are registered before validation,
+    # and a mistyped --scope fails loudly instead of persisting a no-op assignment.
+    get_plugin_loader()
+    try:
+        permission_scope = get_permission_scope(scope)
+    except PermissionScopeNotFound:
+        typer.secho(f"Unknown scope kind: '{scope}'", fg=typer.colors.RED)
+        raise typer.Exit(code=1) from None
```

**Review:**

> nit: I'm not too confortable running typer.Exit in non-CLI functions. I understand this specific function is only
> called in CLI, but it might be a future footgun during a refactoring. Feel free to ignore this comment.

## Example 18

**Issue:** Generated frontend plugin list leaks plugins into core; generate one file per plugin directory instead.

`frontend/lib/plugins/generated.ts`

```diff
@@ -0,0 +1,7 @@
+// Generated by scripts/dump_frontend_plugins.py. Do not edit.
+// Backend plugins that declare a frontend page (FRONTEND_APPS hook).
+// Regenerate with `make frontend.build.plugins`; tests fail on drift.
+
+export const FRONTEND_PLUGIN_NAMES = ["chat", "google-drive", "slack"] as const;
```

**Review:**

> This is effectively a leak of plugins into the core. This means that when a user wants to enable some custom
> plugins, they will need to re-generate this file, which is not really appropriate. I don't have a great solution
> though. Could we instead generate one file per plugin, in their own plugin directory?

## Example 19

**Issue:** Adding a field isn't a v2; newer versions must be backwards compatible, so update the v1 event schema
instead.

`sparkth/core/analytics/schemas/v1/user_logged_in.py`

```diff
+
+v1 carried the username, a string the user chose, so it is retired and nothing may emit
+it. Analytics migration ``6ccbebfb6a25`` removed the username from stored v1 rows, which
+are still counted as logins.
+"""
+
+from enum import StrEnum
+
+from sparkth.core.analytics.schemas.base import AnalyticsEventSchema
+
+
+class LoginMethod(StrEnum):
```

**Review:**

> This is not a v2 of an existing event, newer versions should be backwards compatible.
> Lets update the v1 of this event, instead of creating a v2

## Example 20

**Issue:** Routes should not hit the DB directly; create a user service under core/services/user.

`sparkth/api/v1/analytics.py`

```diff
     session: AsyncSession = Depends(get_analytics_session),
+    app_session: AppSession = Depends(get_async_session),
 ) -> ExploreResult:
     """Measure one event type's raw events per bucket, filtered and grouped by payload fields.
 
     Sparse. Grouped results keep the top 20 groups by range total and set `truncated` when more
     existed. An unknown event type or field, or a value that does not fit its field, is a 422.
+    Grouped by actor, `actor_names` maps user ids to usernames for holders of `user.read`.
     """
-    return await explore(session, query)
+    result = await explore(session, query)
+    if query.group_by == "actor" and await can(user, USER_READ, GLOBAL, None, app_session):
```

**Review:**

> Lets not perform direct DB operations from a route hander. In the rest of the codebase we have service classes to
> which routes delegate this responsibility to.
>
> Lets create a user service, it can be in `core/services/user` and then this route can call the service to get
> usernames
