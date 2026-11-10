# Violations of established patterns

Real review comments from Sparkth pull requests: code that diverges from how the codebase already does it.

## Example 1

**Issue:** Move config accessor to config.py and rename to get_chat_settings for consistency with core.

`app/core_plugins/chat/routes/dependencies.py`

```diff
+from sqlmodel.ext.asyncio.session import AsyncSession
+
+from app.api.v1.auth import get_current_user
+from app.core_plugins.chat.config import ChatSystemConfig
+from app.core_plugins.chat.models import Conversation
+from app.core_plugins.chat.service import ChatService
+from app.lib.db import get_async_session
+from app.models.user import User
+
+
+@lru_cache
+def get_chat_system_config() -> ChatSystemConfig:
```

**Review:**

> lets move this to `config.py` and rename the function to `get_chat_settings` to stay consistent with the core and
> rest of the codebase

## Example 2

**Issue:** Move require_user_id dependency into routes/dependencies.py for consistency with googledrive and chat
plugins.

`app/core_plugins/slack/routes/oauth.py`

```diff
+from app.core_plugins.slack.oauth import decode_state, exchange_code_for_tokens, generate_authorization_url
+from app.core_plugins.slack.service import WorkspaceService, get_workspace_service
+from app.core_plugins.slack.types import AuthorizationUrlResponse, ConnectionStatusResponse
+from app.lib.db import get_session
+from app.lib.log import get_logger
+from app.models.user import User
+
+oauth_router: APIRouter = APIRouter()
+logger = get_logger(__name__)
+
+
+def require_user_id(current_user: User = Depends(get_current_user)) -> int:
```

**Review:**

> this is a dependency, even though its only being used in this file, can we put in in a `routes/dependencies.py` file
> so that the structure remains consistent with the googledrive and chat plugin.

## Example 3

**Issue:** raw_events uses plain SQLAlchemy table while all other models are classes; why not a class model.

**Review:**

> Everything looks good, just one last thing, why cant we have a class based SQLAlchemy model for the `raw_events`.
> Why does it need to be plain SQLAlchemy code.
> All the other models in our codebase are python classes, why not this one

## Example 4

**Issue:** Error handling duplicates PermissionScopesRegistry.get; asks why bypass the registry.

`app/core/permissions/__init__.py`

```diff
+    def require(self, permission_scope: str, scope_param: str) -> Callable[..., Awaitable[User]]:
+        """Return a FastAPI dependency enforcing this permission at a named scope.
+
+        Args:
+            permission_scope: A registered scope kind's name (e.g. ``"course"``). Looked up on
+                the PERMISSION_SCOPES hook; an unregistered name raises ``PermissionScopeNotFound``
+                here (at route-definition/import time) so misconfiguration fails fast at startup.
+            scope_param: The name of the route's path parameter carrying the scope object id;
+                resolved from ``request.path_params`` on each request.
+        """
+        scope = PERMISSION_SCOPES.get(permission_scope)
+        if scope is None:
```

**Review:**

> This error handling is already performed by `PermissionScopesRegistry.get`. Should we really bypass the registry
> here? (or anywhere really)

## Example 5

**Issue:** One OverviewTrend function builds all event trends and will bloat; split per event group with this acting
as a factory.

`frontend/app/dashboard/analytics/page.tsx`

```diff
+          ) : (
+            <div key={f.key}>{card}</div>
+          );
+        })}
+      </div>
+      <OverviewTrend {...rest} from={from} to={to} bucket={bucket} />
+    </div>
+  );
+}
+
+// Logins plus messages sent per bucket, against the previous period.
+function OverviewTrend({
```

**Review:**

> This one function generated trends for all analytics events?
> If yes then adding more events in the future would bloat this up a lot.
>
> Lets create individual functions for each event group and this function can act as a factory to bring them all
> together
