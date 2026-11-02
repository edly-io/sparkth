# Code smells

Real review comments from Sparkth pull requests: duplication, dead code, thin wrappers, magic literals, needless
complexity.

## Example 1

**Issue:** tests/lib/env.py is unnecessary given base conftest.py and app/testing.py.

`tests/lib/env.py`

```diff
@@ -0,0 +1,15 @@
+"""Test environment setup — import this before any app module that reads settings.
```

**Review:**

> I think this file is unnecessary now that we have a base conftest.py and app/testing.py.

## Example 2

**Issue:** Odd _workspace_repo name; call WorkspaceService directly instead of backward-compat wrapper functions.

`app/core_plugins/slack/oauth.py`

```diff
@@ -105,9 +166,7 @@ async def exchange_code_for_tokens(
     return data
 
 
-# ---------------------------------------------------------------------------
-# Workspace persistence
-# ---------------------------------------------------------------------------
+_workspace_repo = WorkspaceService()
```

**Review:**

> This variable name seems very odd, can you please explain if there is a reason behind it.
> If not then lets rename it to `_workspace_service`.
>
> Other than that, I believe this is only used inside functions that are defined for backwards compatibility. I think
> we can avoid that, instead of wrapping the new `WorkspaceService` in functions for backwards compatibility, and
> using them, lets use the new class directly.
> For example:
> every place where `save_workspace` is being called, lets call `WorkspaceService.save`. Same for `get_workspace`,
> `get_workspace_by_team` and `delete_workspace`.
>
> This would allow us to get rid of the private variable and the wrapper functions.

## Example 3

**Issue:** LMSError looks like a redundant copy of BaseError; make it specific or just use Exception.

`app/lib/exceptions.py`

```diff
+        return f"{self.message} (status_code={self.status_code})"
+
+
+class AuthenticationError(BaseError):
+    pass
+
+
+class JsonParseError(BaseError):
+    pass
+
+
+class LMSError(BaseError):
```

**Review:**

> Can you please help me in understanding the meaning of this error class.
> Where is this needed and why?
>
> This looks like a copy of the `BaseError` class which in itself is redundant. I dont think we need this, or if we
> do, we need to be specific about what it is, if its encapsulating an umbrella of exceptions, it might be better to
> just use the `Exception` class instead

## Example 4

**Issue:** Raw SQL backfill in migration looks odd; asks why bypass the ORM.

`app/migrations/versions/e65be7f91ab2_add_documents_table_and_document_id_to_.py`

```diff
+        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
+        sa.ForeignKeyConstraint(["user_id"], ["user.id"]),
+        sa.PrimaryKeyConstraint("id"),
+    )
+    op.create_index("ix_documents_user_id", "documents", ["user_id"])
+    op.create_index("ix_documents_is_deleted", "documents", ["is_deleted"])
+
+    # 2. Backfill: one Document row per DriveFile with a non-null rag_status.
+    # Cast rag_status enum to text so it stores cleanly into documents.status (varchar).
+    op.execute(
+        """
+        INSERT INTO documents (user_id, name, mime_type, status, error, is_deleted,
```

**Review:**

> I find this raw SQL statement a little strange. Do we have a good reason to bypass the ORM here?

## Example 5

**Issue:** Questions the lazy imports inside the fixture function.

`tests/rag/conftest.py`

```diff
+
+@pytest.fixture(scope="session")
+async def rag_engine() -> AsyncGenerator[AsyncEngine, None]:
+    """In-memory SQLite engine for RAG tests that need lightweight FK support."""
+    engine = create_async_engine(
+        DATABASE_URL,
+        connect_args={"check_same_thread": False},
+        poolclass=StaticPool,
+    )
+
+    from app.models.base import TimestampedModel  # noqa: F401
+    from app.models.user import User  # noqa: F401
```

**Review:**

> Why the lazy import?

## Example 6

**Issue:** Remove section-divider comments in tests, likely left by earlier AI iterations.

`app/lib/mcp/tests/test_schema_resolution.py`

```diff
@@ -1,9 +1,8 @@
 from typing import Any
 
-import pytest
 from pydantic import BaseModel
 
-from app.plugins.base import SparkthPlugin
+from app.lib.mcp.hooks import resolve_schema_refs, type_to_json_schema
 
 
 # ---------------------------------------------------------------------------
```

**Review:**

> lets remove all comments like these, im sure all of them have been added by Claude in previous iterations

## Example 7

**Issue:** Extract repeated /api/v1/googledrive literal into a constant at top of file.

`frontend/lib/drive.ts`

```diff
-  const response = await fetch(`${API_BASE_URL}/oauth/status`, {
-    method: "GET",
-    headers: {
-      Accept: "application/json",
-      Authorization: `Bearer ${token}`,
-    },
-  });
-
-  if (!response.ok) {
-    await handleError("Failed to get connection status", response);
+  try {
+    const { data } = await api.GET("/api/v1/googledrive/oauth/status", {
```

**Review:**

> can we extract `/api/v1/googledrive` in a constant on top of the file and reuse it everywhere below?

## Example 8

**Issue:** Registry classes are pointless; hard-code the hook and patch it in tests.

`app/lib/permissions/registry.py`

```diff
 
-from app.core.permissions import PERMISSIONS
+from app.core.permissions import PERMISSIONS, Permission
 from app.core.permissions.exceptions import PermissionNotFound, PermissionScopeNotFound
 from app.core.permissions.scopes import PERMISSION_SCOPES, PermissionScope
-from app.lib.log import get_logger
-
-logger = get_logger(__name__)
+from app.lib.hooks import SingleNamedItemHook
 
 
 class PermissionsRegistry:
```

**Review:**

> What's the point of keeping a class around? In production, this class is always going to use the PERMISSIONS hook.
> Let's simplify this class and hard-code the hook, which should alway be the same. In unit tests we can mock/patch
> the hook object.
>
> Same for the PermissionScopesRegistry.

## Example 9

**Issue:** Attribute check is unnecessary since type checking should catch it; question why performed.

`app/lib/analytics/__init__.py`

```diff
+      would otherwise raise a bare ``AttributeError``.
+    - **Namespace.** ``event_type`` must be prefixed with the contributing plugin's
+      name (e.g. plugin ``slack`` → ``"slack.*"``), else ``EventNamespaceError``.
+      This stops a plugin squatting a core or another plugin's event name.
+    - **Collision.** A *different* class claiming an already-registered
+      ``(event_type, version)`` raises ``DuplicateEventTypeError``.
+
+    Idempotent for the same class: ``ANALYTICS_EVENTS.add_item`` is a no-op when the
+    same schema is registered again, so a module re-imported in tests is safe.
+    """
+    missing = [attr for attr in ("event_type", "version") if not hasattr(schema, attr)]
+    if missing:
```

**Review:**

> I don't understand why we need to perform this check here. Type checking should help us catch errors, no?

## Example 10

**Issue:** add_item already checks duplicates; catch ValueError and raise DuplicateEventTypeError instead.

`app/lib/analytics/__init__.py`

```diff
+    if missing:
+        exc = TypeError(f"{schema.__qualname__} must declare {missing} as class attributes before it can be registered")
+        logger.error(
+            "Plugin '%s' schema %s is missing required identity ClassVars: %s",
+            plugin.name,
+            schema.__qualname__,
+            exc,
+        )
+        raise exc
+    if not schema.event_type.startswith(f"{plugin.name}."):
+        raise EventNamespaceError(plugin.name, schema.event_type)
+    existing = ANALYTICS_EVENTS.get((schema.event_type, schema.version))
```

**Review:**

> Since `add_item` performs the same check, I suggest we write instead:
>
> ```
> try:
>     ANALYTICS_EVENTS.add_item(schema)
> except ValueError as e:
>     logger.error(...)
>     raise DuplicateEventTypeError(schema.event_type, schema.version) from e
> ```

## Example 11

**Issue:** Hard-coded "/ai" mount path should be a shared variable or per-router AuditSource.

`sparkth/core/audit/middleware.py`

```diff
             user_agent=headers.get("user-agent"),
-            source=AuditSource.REST,
+            source=self._source(scope),
         )
         with audit_context(context):
             await self.app(scope, receive, send)
 
+    @staticmethod
+    def _source(scope: Scope) -> AuditSource:
+        """MCP for the FastMCP mount (mounted at ``/ai`` in main.py), REST otherwise."""
+        path: str = scope.get("path", "")
+        if path == "/ai" or path.startswith("/ai/"):
```

**Review:**

> This "/ai" is a hard-coded string that should be replaced by a variable. Unless each router configures its own
> AuditSource?

## Example 12

**Issue:** Single-use permission_obj/scope_obj variables can be inlined into the can() call.

`sparkth/api/v1/permissions/routes/__init__.py`

```diff
+    session: AsyncSession = Depends(get_async_session),
+) -> PermissionCheckResponse:
+    """Return whether the current user holds ``permission`` at the given scope.
+
+    A self-check any authenticated user may call about their own grants. It is not a security
+    boundary (endpoints enforce their own permissions and return 403); it lets a client gate UI
+    precisely. The permission and scope names are resolved against the registered vocabulary
+    (unknown → 422) and the decision is delegated to the engine's ``can()``.
+    """
+    permission_obj = get_permission(permission)
+    scope_obj = get_permission_scope(scope)
+    allowed = await can(current_user, permission_obj, scope_obj, scope_object_id, session)
```

**Review:**

> `permission_obj` and `scope_obj` are only used once, we can call the functions inline, no need to store them in
> variables

## Example 13

**Issue:** Repeated lazy-init pattern in ToolRegistry; use lazy accessor, move stateless methods to module functions,
drop unused reset.

`sparkth/plugins/chat/tools.py`

```diff
@@ -56,6 +61,17 @@ async def get_tool_schemas(self) -> list[dict[str, Any]]:
             for tool in self._tools.values()
         ]
 
+    def category_for(self, tool_name: str) -> str:
+        """Return the MCP category a tool was contributed under.
+
+        LangChain tools carry no category — ``_convert_mcp_to_langchain_tool`` drops
+        it — so the mapping is recorded during discovery. Unknown names resolve to
+        :data:`UNKNOWN_TOOL_CATEGORY` rather than raising.
+        """
+        if not self._initialized:
```

**Review:**

> This pattern is being repeated multiple times across the ToolRegistry class. I would recommend writing instead:
>
> ```
> class ToolRegistry:
>     """Registry for managing LangChain tools."""
>
>     def __init__(self) -> None:
>         self._tools: dict[str, BaseTool] | None = None
>
>     def tools_dict(self) -> dict[str, BaseTool]:
>         if self._tools is None:
>             self._tools = self._discover_plugin_tools()
>         return self._tools
> ```
>
> Interestingly, while writing this, I realised that we could replace many instance methods by static methods:
> _convert_mcp_to_langchain_tool, _get_handler_type_hints, _build_args_schema_from_handler, _json_schema_to_pydantic,
> _resolve_ref, _get_python_type etc. could all be moved out of the ToolRegistry class and made normal functions.
>
> Also, `refresh_tools` is unused anywhere, and we should thus gete rid of the `reset` method.
>
> Maybe this might be worth having a look if you take on this PR?

## Example 14

**Issue:** Hand-written status mapping duplicates existing DocumentStatus enum; use that enum instead.

`sparkth/plugins/chat/routes/completions.py`

```diff
@@ -50,6 +52,23 @@
 
 router = APIRouter()
 
+# Why a soft-deleted document reports "deleted" whatever its ingestion status: from the
+# instructor's side the file is gone, which is the thing worth counting, not how far it had
+# got through ingestion before it went.
+_INGESTION_STATUS: dict[DocumentStatus, Literal["queued", "processing", "failed", "deleted"]] = {
```

**Review:**

> we have an enum for ingestion status at `core.documents.enums.DocumentStatus`, lets use that instead

## Example 15

**Issue:** todayUtc is a one-line wrapper around toIsoDate(now); call that directly.

`frontend/lib/analytics/dates.ts`

```diff
+export function toIsoDate(d: Date): IsoDate {
+  return d.toISOString().slice(0, 10);
+}
+
+export function parseIsoDate(s: string): Date | null {
+  if (!/^\d{4}-\d{2}-\d{2}$/.test(s)) return null;
+  const d = new Date(`${s}T00:00:00Z`);
+  // Date rolls 2026-02-30 over to March; a round-trip mismatch means the day doesn't exist.
+  return Number.isNaN(d.getTime()) || toIsoDate(d) !== s ? null : d;
+}
+
+export function todayUtc(now: Date = new Date()): IsoDate {
```

**Review:**

> this is a one-line wrapper around `toIsoDate(now)`, lets use that directly where needed

## Example 16

**Issue:** Raw TimescaleDB SQL duplicated per plugin; add a core analytics helper that builds the query from
arguments.

`sparkth/plugins/chat/analytics/reads.py`

```diff
+    """Count of one chat event type in one bucket. ``bucket`` is the UTC start, ``YYYY-MM-DD``."""
+
+    bucket: str
+    event_type: str
+    dimension: str | None = None
+    """Tool name for ``chat.tool_invoked``, failure cause for ``chat.turn_failed``."""
+    outcome: str | None = None
+    """``succeeded`` / ``failed`` for tool calls recorded with an outcome."""
+    event_count: int
+
+
+_PG_SQL = {
```

**Review:**

> I assume that we would be building more timescaleDB queries like this. Instead of having these in every plugin,
> could we make a helper function in the analytics core which would take some arguments and build the query?
> This way, each plugin can just call that helper function and wont have to write this much raw SQL.
>
> Lets try to find a way where we can avoid writing this much raw SQL in each plugin

## Example 17

**Issue:** Result of getattr still wrapped despite being a bool; avoid unnecessary wrappers.

`sparkth/core/routes/__init__.py`

```diff
+    """Mark a plugin endpoint as serving platform-wide data, such as an analytics read.
+
+    The plugin access gate lets a marked endpoint through whatever the plugin switches say;
+    its own dependencies (e.g. a permission) still apply. Apply it below the route decorator.
+    """
+    setattr(endpoint, PLATFORM_WIDE_ATTRIBUTE, True)
+    return endpoint
+
+
+def is_platform_wide_route(route: BaseRoute) -> bool:
+    """Whether the route's endpoint is marked :func:`platform_wide`."""
+    return getattr(getattr(route, "endpoint", None), PLATFORM_WIDE_ATTRIBUTE, False) is True
```

**Review:**

> Why are we still wrapping the result of `getattr` in `bool`, form what I see `PLATFORM_WIDE_ATTRIBUTE ` cant be
> anything else other than a bool.
> We dont need to add unnecessary wrappers

## Example 18

**Issue:** Wrapper dependency around require_in_global_scope is unnecessary; put the Depends straight on endpoints.

`sparkth/api/v1/analytics_views.py`

```diff
+
+router = APIRouter()
+
+
+def _owner_id(user: Annotated[User, Depends(ANALYTICS_READ.require_in_global_scope())]) -> int:
+    """The caller's id; a signed-in user always has one."""
+    if user.id is None:
+        raise RuntimeError(f"Signed-in user has no id: {user!r}")
+    return user.id
+
+
+Owner = Annotated[int, Depends(_owner_id)]
```

**Review:**

> why not just add this `Depends(ANALYTICS_READ.require_in_global_scope())` dependency straight to the endpoints? why
> have this wrapper

## Example 19

**Issue:** chat, drive and pxc settings files are identical defaults; fall back to default row and drop them.

`frontend/plugins/chat/settings.ts`

```diff
@@ -0,0 +1,10 @@
+import { SettingsListItem } from "@/lib/components/settings/SettingsListItem";
+import { SETTINGS_ITEMS } from "@/lib/settings/slots";
+
+// Chat's row on the settings page, with the config modal built from its backend config.
+SETTINGS_ITEMS.set("chat", [
+  {
+    listItem: SettingsListItem,
+    loadConfigModal: () => import("@/lib/components/settings/ConfigModal"),
+  },
+]);
```

**Review:**

> this is pretty identical to google drive and pxc settings (other than the plugin name), and all of these are setting
> the default row and modal just to show up on the settings page. if we fall back to the default row for plugins that
> set nothing, these three files can be removed. only slack would need a `settings.ts`.

## Example 20

**Issue:** Approved; stack another PR removing the backend endpoints that have no callers.

**Review:**

> The PR looks good to go.
> In the **Notes** section, there is a mention of some backend endpoints that have no callers in the repository. Lets
> stack another PR on top of this and remove those unused backend endpoints as well.
