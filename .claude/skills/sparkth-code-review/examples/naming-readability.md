# Naming & readability

Real review comments from Sparkth pull requests: names that say what the code does, consistent terminology.

## Example 1

**Issue:** dependencies.py is an odd module name; suggests api.py if it serves as internal API.

`app/core_plugins/chat/routes/dependencies.py`

```diff
@@ -0,0 +1,46 @@
+from functools import lru_cache
```

**Review:**

> "dependencies.py" is a weird name for a module. Do we mean that this is the module that will serve as its own
> internal API? If yes, then "api.py" is a better name.

## Example 2

**Issue:** Rename SlackSystemConfig to SlackSettings to match Settings naming in core and googledrive.

`app/core_plugins/slack/config.py`

```diff
 
-from pydantic import Field
+from functools import lru_cache
+
+from pydantic import Field, field_validator
+from pydantic_settings import BaseSettings, SettingsConfigDict
 
 from app.plugins.config_base import PluginConfig
 
-MAX_TIMESTAMP_DELTA = 60 * 5  # 5 minutes
+
+class SlackSystemConfig(BaseSettings):
```

**Review:**

> lets rename this class to `SlackSettings`, staying consistent with the `Settings` naming convention being followed
> in `app/core/config` and in the other plugin configs

## Example 3

**Issue:** Rename BaseHttpClient to something more specific like BaseHttpAuthenticationClient if only for auth.

`app/lib/http.py`

```diff
+import json
+from collections.abc import Callable
+from types import TracebackType
+from typing import Any, Self
+
+from aiohttp import ClientPayloadError, ClientResponse, ClientSession
+
+from app.lib.enums import Auth, Method
+from app.lib.exceptions import AuthenticationError, LMSRequestError
+
+
+class BaseHttpClient:
```

**Review:**

> If this class is only for providing HTTP authentication utility, then lets rename it to be more specific, something
> like `BaseHttpAuthenticationClient`

## Example 4

**Issue:** format_source_block is a vague name for a library function; suggests format_prompt or similar.

`app/rag/formatting.py`

```diff
@@ -0,0 +1,31 @@
+"""Utilities for formatting RetrievedChunk objects into human-readable context blocks."""
+
+from app.rag.types import RetrievedChunk
+
+
+def format_source_block(source_name: str, chunks: list[RetrievedChunk]) -> str:
```

**Review:**

> This is not a great name for a library function. What's a "source"? What's a "block"? These are generic terms that
> don't mean much here. Maybe "format_prompt"? or "convert_chunks_to_string"?

## Example 5

**Issue:** Rename DATABASE_URL to an app-specific name in a later PR given ANALYTICS_DATABASE_URL.

`app/core/config.py`

```diff
@@ -10,6 +10,7 @@ class Settings(BaseSettings):
     # still win over both.
     model_config = SettingsConfigDict(env_file=(".env", ".env.local"), env_file_encoding="utf-8", extra="ignore")
     DATABASE_URL: str
```

**Review:**

> Not in this PR, but in a later PR we should rename this to `SPARKTH_DATABASE_URL` or `APP_DATABASE_URL` since we
> have an `ANALYTICS_DATABASE_URL` we cant name this just `DATABASE_URL`, that would be too generic

## Example 6

**Issue:** View function names are inconsistent; rename to list_roles, list_permissions, get_role, create_role, etc.

`app/api/v1/permissions/routes.py`

```diff
+    """Build a RoleResponse for a persisted role, attaching its permission grants."""
+    assert role.id is not None
+    permissions = await get_role_permissions(role.id, session)
+    return RoleResponse(id=role.id, name=role.name, description=role.description, permissions=permissions)
+
+
+@router.get(
+    "/available",
+    response_model=list[str],
+    dependencies=[Depends(RequirePermission("role.read", "global"))],
+)
+async def list_available_permissions() -> list[str]:
```

**Review:**

> The names of the different views are a little weird and inconsistent. I suggest:
>
> ```
> list_roles                    #instead of list_available_permissions
> list_permissions       # instead of list_all_roles
> get_role                     # instead of get_one_role
> create_role                # instead of create_new_role
> update_role               # instead of update_existing_role
> delete_role_permission # instead of revoke_role_permission
> etc.
> ```

## Example 7

**Issue:** iter_items should be named iter_values since it yields only values.

`app/lib/hooks.py`

```diff
+    name is already present raises ``ValueError``.
+    """
+
+    def __init__(self) -> None:
+        self._items: dict[str, N] = {}
+
+    def add_item(self, item: N) -> None:
+        if item.name in self._items:
+            raise ValueError(f"Duplicate hook item: {item.name}")
+        self._items[item.name] = item
+
+    def iter_items(self) -> Iterator[N]:
```

**Review:**

> nit.: this should be named `iter_values`. `iter_items` would also yield the names.

## Example 8

**Issue:** UniqueCollectionHook name is misleading; rename e.g. to SingleNamedItemHook.

`app/lib/hooks.py`

```diff
@@ -44,3 +52,22 @@ def iter_items(self) -> Iterator[tuple[SparkthPlugin, T]]:
         for plugin, plugin_items in self._iter_plugin_items():
             for plugin_item in plugin_items:
                 yield plugin, plugin_item
+
+
+class UniqueCollectionHook(Generic[N]):
```

**Review:**

> In "PluginCollectionHook" the "Collection" part was meant to represent the fact that each plugin was collecting a
> list of objects. This is not the case here, as each name is associated with a single item. So I suggest to rename
> "UniqueCollectionHook". For instance, to "SingleNamedItemHook".

## Example 9

**Issue:** Import alias grant_role suggests the function was misnamed; non-blocking.

`app/cli/roles.py`

```diff
@@ -4,14 +4,12 @@
 from sqlmodel import select
 
 from app.lib.db import session_scope
-from app.lib.permissions import RoleNotFound
+from app.lib.permissions import GLOBAL, PermissionScope, RoleNotFound
 from app.lib.permissions import assign_role as grant_role
```

**Review:**

> Just noticed this:
>
> ```
> from app.lib.permissions import assign_role as grant_role
> ```
>
> Doesn't this say that we named the function wrong in the first place?
>
> I realize this is not part of this PR, so feel free to ignore.

## Example 10

**Issue:** GLOBAL rename from SCOPE_GLOBAL hides that it is a scope object; keep scope in the name.

`app/core/permissions/scopes.py`

```diff
@@ -30,3 +39,10 @@ def get_parents(self) -> list["PermissionScope"]:
             return []
         grand_parents = self.parent.get_parents()
         return [self.parent, *grand_parents]
+
+
+# Core Permisson Scopes shipped with the application, ordered root-first so each is registered after its parent.
+
+# The root scope: it applies platform-wide and names no object. This is the canonical
+# instance plugins should reference as a parent so the whole tree shares one root.
+GLOBAL = PermissionScope.create("global")
```

**Review:**

> Why the rename from SCOPE_GLOBAL to GLOBAL? When we import this object (as in
> `from app.lib.permissions import GLOBAL`) neither the name nor the import path tell us that this is a scope object.

## Example 11

**Issue:** Use 'core' terminology rather than 'defaults' for things shipped with the application.

`app/core/analytics/registry.py`

```diff
@@ -36,40 +36,47 @@ def __init__(self) -> None:
         # __init__ runs on every EventRegistry() call, even when __new__ returns
         # the existing singleton — guard so re-construction never wipes registrations.
         if not hasattr(self, "_schemas"):
-            self._schemas: dict[tuple[str, int], type[BaseModel]] = {}
+            self._schemas: dict[tuple[str, int], type[AnalyticsEventSchema]] = {}
             self._server_only: dict[tuple[str, int], bool] = {}
             self._register_defaults()
 
     def _register_defaults(self) -> None:
```

**Review:**

> lets use `core` terminology rather than `defaults`, we are making the same change for the permission system as well.
>
> Anything shipped with the application should be called `core`

## Example 12

**Issue:** Drop the _or_raise suffix from get_permission_or_raise and scope variant.

`app/core/permissions/utils.py`

```diff
@@ -171,3 +171,19 @@ async def revoke_role(
         # them dirty — no session.add needed.
         assignment.soft_delete()
     await session.flush()
+
+
+def get_permission_or_raise(name: str) -> Permission:
```

**Review:**

> Can we get rid of the "_or_raise" suffix, which is a little awkward? Same for `get_permission_scope_or_raise`.
> Otherwise Claude is going to create only `*_or_raise` lib functions, as pretty much all our functions can raise
> exceptions.

## Example 13

**Issue:** Rename record_event_now to record_event_and_commit.

`sparkth/core/audit/recorder.py`

```diff
+        model_provider=model.provider if model is not None else None,
+        model_name=model.name if model is not None else None,
+        model_version=model.version if model is not None else None,
+        purpose=event.purpose,
+        canonical_bytes=canonical_bytes,
+    )
+    session.add(row)
+    await session.flush()
+    return row
+
+
+async def record_event_now(event: BaseAuditEvent) -> AuditEvent:
```

**Review:**

> this function could be named better, if the only difference between this function and `record_event` is committing,
> then a better name would be `record_event_and_commit`.

## Example 14

**Issue:** Rename audited_tool_handler to audited_tool; handler/manager suffixes add no meaning.

`sparkth/core/audit/execution.py`

```diff
+    ``tool.invoked`` event inside the block. Protocol-layer backstops (the
+    FastMCP middleware) use it to record exactly the failures the handler
+    wrapper could not see.
+    """
+    token = _execution_recorded.set(False)
+    try:
+        yield _execution_recorded.get
+    finally:
+        _execution_recorded.reset(token)
+
+
+def audited_tool_handler(handler: AsyncToolHandler) -> AsyncToolHandler:
```

**Review:**

> I have a problem with the name of this decorator. If we decide to keep it, and not the middleware, then we should
> probably rename to something like "audited_tool".
>
> In general "handler"/"manager"/etc. suffixes don't add meaningful to a name and should be either removed or replaced
> by something more specific. (There are exceptions though)

## Example 15

**Issue:** GroupAlreadyExists uses name while GroupNotFound uses group; use the same attribute name.

`sparkth/core/permissions/exceptions.py`

```diff
+class GroupNotFound(Exception):
+    """Raised when a group referenced by id or name does not exist."""
+
+    def __init__(self, group: str) -> None:
+        super().__init__(f"Group not found: {group}")
+        self.group = group
+
+
+class GroupAlreadyExists(Exception):
+    """Raised when creating or renaming a group to a name that is already taken."""
+
+    def __init__(self, name: str) -> None:
```

**Review:**

> There's an inconsistency between this "name" attribute and the "group" attribute of the GroupNotFound class.
> Shouldn't we use the same attribute name?

## Example 16

**Issue:** Rename Drive audit events to GoogleDrive-prefixed names so a future OneDrive support isn't confusing.

`sparkth/plugins/googledrive/audit.py`

```diff
+from dataclasses import dataclass
+from typing import ClassVar
+
+from sparkth.lib.audit.events import MutationAuditEvent
+from sparkth.lib.audit.hooks import AUDIT_EVENTS
+
+DRIVE_CONNECTION_TARGET = "googledrive_connection"
+
+
+@AUDIT_EVENTS.register
+@dataclass(frozen=True, slots=True, kw_only=True)
+class DriveConnectedAuditEvent(MutationAuditEvent):
```

**Review:**

> Lets rename these events to `GoogleDriveConnectedAuditEvent` and `GoogleDriveDisconnectedAuditEvent`
>
> If we ever implement support for, lets say, OneDrive, this naming convention would get confusing

## Example 17

**Issue:** Rename to _create_audit_snapshot; use this name for all snapshot-generating functions for consistency.

`sparkth/core/permissions/groups.py`

```diff
+    GroupRoleRevokedAuditEvent,
+    GroupUpdatedAuditEvent,
+)
 
 
-async def create_group(name: str, description: str | None, session: AsyncSession) -> Group:
-    """Create and return a group. Raises GroupAlreadyExists if the name is already taken.
+def _target(group_id: int | None) -> AuditTarget:
+    return AuditTarget(type="group", id=str(group_id))
+
+
+def _snapshot(group: Group) -> dict[str, str | None]:
```

**Review:**

> lets rename this function to `_create_audit_snapshot`
> Lets use this name for all snapshot generating functions to keep the codebase consistent

## Example 18

**Issue:** usePermission name is misleading since it performs a check; rename to something meaningful.

`frontend/lib/permissions/usePermission.ts`

```diff
+import type { PermissionName } from "@/lib/permissions/types";
+
+/** Where a permission check stands: still in flight, granted, or refused (including on error). */
+export type Access = "checking" | "allowed" | "denied";
+
+/**
+ * Whether the signed-in user holds `permission`, for gating a page or panel.
+ *
+ * Goes back to `"checking"` whenever the token or permission changes, so a re-login never
+ * briefly shows the previous user's answer, and fails closed to `"denied"` when the check errors.
+ */
+export function usePermission(
```

**Review:**

> this function stills checks the permissions, `usePermission` doesn't seem like a good name for this function.
> Lets rename this function to be more meaningful

## Example 19

**Issue:** Avoid single-letter variable names such as t and f.

`sparkth/core/analytics/catalog.py`

```diff
+
+def event_catalog() -> list[EventCatalogEntry]:
+    """Every event type with its fields merged across versions (the highest version wins), sorted."""
+    merged: dict[str, dict[str, EventField]] = {}
+    for schema in sorted(ANALYTICS_EVENTS.iter_values(), key=lambda s: s.version):
+        fields = merged.setdefault(schema.event_type, {})
+        for name, info in schema.model_fields.items():
+            if (field := _field(name, info)) is not None:
+                fields[name] = field
+    return [
+        EventCatalogEntry(event_type=t, fields=sorted(f.values(), key=lambda f: f.name))
+        for t, f in sorted(merged.items())
```

**Review:**

> lets avoid using variable names such as `t` and `f`

## Example 20

**Issue:** Standalone function name `explore` is too vague; name must convey full meaning on its own.

`sparkth/core/analytics/explore.py`

```diff
+
+
+def _group_value(value: Any, kind: FieldKind | None) -> str | None:
+    """A group's label: booleans as ``true``/``false`` on every dialect, the rest as text."""
+    if value is None:
+        return None
+    if kind == FieldKind.boolean:
+        return "true" if value else "false"
+    return str(value)
+
+
+async def explore(session: AsyncSession, query: ExploreQuery) -> ExploreResult:
```

**Review:**

> lets make the function name more descriptive. If this was a class method then `explore` would've been fine since the
> overall name would then be `Classname.explore`, but since this is a standalone function, its name needs to convey
> the entire meaning by itself
