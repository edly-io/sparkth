# Design patterns

Real review comments from Sparkth pull requests: when to introduce an abstraction and which one.

## Example 1

**Issue:** Disagrees with bundling functions into a class; no state means modules work fine.

`app/core_plugins/chat/lms_credentials.py`

```diff
@@ -19,19 +19,12 @@
 
 
 def _lms_tool_prefixes() -> tuple[str, ...]:
```

**Review:**

> I disagree. There's no reason to bundle functions in a class if we don't persist state within class attributes.
> Modules work just fine.

## Example 2

**Issue:** Exposing PermissionService makes all methods public API; expose plain functions taking a session.

`app/lib/permissions.py`

```diff
@@ -0,0 +1,11 @@
+"""Public API for the permissions (scoped RBAC) framework.
+
+Application code and plugins import the permissions surface from here, never from
+``app.permissions.*`` directly.
+"""
+
+from app.permissions.constants import SCOPE_GLOBAL
+from app.permissions.exceptions import RoleNotFound
+from app.permissions.service import PermissionService
```

**Review:**

> We expose just three objects in app.lib.permissions, but in reality the entire PermissionService object becomes an
> API. So all three methods become part of the library, though this is not explicit. I don't see why we should expose
> a service, and not three functions (that would all take an extra "session" argument).

## Example 3

**Issue:** Repeated exception handling in every view; centralize via decorator or FastAPI-native mechanism.

`app/api/v1/permissions/routes/roles.py`

```diff
+
+
+@router.get(
+    "/roles/{role_id}",
+    response_model=RoleResponse,
+    dependencies=[Depends(RequirePermission("role.read", "global"))],
+)
+async def get_one_role(role_id: int, session: AsyncSession = Depends(get_async_session)) -> RoleResponse:
+    """Fetch a role by id. Returns its RoleResponse (id, name, description, permissions)."""
+    try:
+        role = await get_role(role_id, session)
+    except RoleNotFound as exc:
```

**Review:**

> Every view has to catch the same exceptions the same way. I suggest we create a decorator that catches all these
> exceptions and returns consistent HTTP 40x errors. Then wrap every view in this decorator and get rid of the
> exception handling within the views.
>
> EDIT: now that I think of it, isn't there a more fastapi-native way of handling this? For instance with
> dependencies?

## Example 4

**Issue:** New registry class is an empty singleton shell; a simple hook would work better.

`app/core/audit/registry.py`

```diff
+            raise ValueError(f"Audit event type must be 'category.action', got '{self.event_type}'")
+
+    @property
+    def category(self) -> str:
+        return self.event_type.partition(".")[0]
+
+    @property
+    def action(self) -> str:
+        return self.event_type.partition(".")[2]
+
+
+class AuditEventRegistry:
```

**Review:**

> Oh come on, you created yet another "registry" class which is nothing but an empty shell with a singleton and that
> would work better as a simple hook?

## Example 5

**Issue:** Replace boolean objectless flag with a child class; flag leaks outside PermissionScope, move behaviour into
the class.

`app/core/permissions/scopes.py`

```diff
@@ -14,18 +14,26 @@ class PermissionScope:
     The hierarchy lets a role granted at a parent scope cascade to its descendants.
     """
 
-    def __init__(self, name: str, parent: "PermissionScope | None" = None) -> None:
+    def __init__(self, name: str, parent: "PermissionScope | None" = None, *, objectless: bool = False) -> None:
```

**Review:**

> Boolean flags are a red flag for me. It's often better to replace them by a different function, or in this case, a
> different child class. The boolean flag will cause some different behaviour in class methods, which means that child
> class should override their parent.
>
> There's another issue with the `objectless` flag here, which is that it's leaking into the rest of the code base. We
> can't make this flag private because it needs to be accessed by some code outside of the PermissionScope class.
> Which means that we should probably move this code inside the class, such that the objectless attribute is not
> exposed to the outside world.

## Example 6

**Issue:** Verdict literal is defined in two places and can drift; an enum gives a single source of truth.

`sparkth/plugins/chat/analytics.py`

```diff
+
+    ``classifier_model`` is the classifier's own small model, not the conversation's chat
+    model — the two differ, and it is the classifier's that explains its verdicts.
+    """
+
+    event_type = "chat.scope_classified"
+    version = 1
+
+    conversation_id: str | None
+    provider: str
+    classifier_model: str
+    verdict: Literal["in_scope", "out_of_scope", "not_judged"]
```

**Review:**

> we have defined this literal in 2 different places, there is a real chance of drift here. Every time we change the
> literal in one place, we will also have to update in the other.
>
> Having an enum would solve this issue, since it would be a single source of truth
