# Testing

Real review comments from Sparkth pull requests: missing, weak or brittle tests and shared test setup.

## Example 1

**Issue:** Database URL duplicated across plugin conftests; share a base test environment.

`app/core_plugins/chat/tests/conftest.py`

```diff
+from sqlalchemy.pool import StaticPool
+from sqlmodel import SQLModel
+from sqlmodel.ext.asyncio.session import AsyncSession
+
+from app.api.v1.auth import get_current_user
+from app.core.db import get_async_session
+from app.core_plugins.chat.routes import chat_router
+from app.main import app  # must be imported before chat_router to avoid circular imports
+from app.models.user import User
+
+_CHAT_PREFIX = "/api/v1"
+_DATABASE_URL = "sqlite+aiosqlite:///:memory:"
```

**Review:**

> We really should not have to duplicate this database url definition across every plugin. Instead, we should have a
> base test environment that we can share across tests.

## Example 2

**Issue:** Add test that a global admin role holder is denied when the role lacks the checked permission.

`tests/permissions/test_dependency.py`

**Review:**

> let's add a test to verify that a user holding the global `admin` role is still denied when the role hasn't been
> granted the specific checked permission.

## Example 3

**Issue:** Locally built plugin may leak into other tests; make it a fixture like stub_plugin.

`tests/lib/chat/test_hooks.py`

```diff
+    CHAT_CAPABILITIES.add_item(second, STUB)
 
-    with caplog.at_level(logging.ERROR, logger="sparkth.lib.chat.hooks"):
-        jobs = await enabled_responsibilities(session)
+    assert (await enabled_capabilities(session)).count(STUB) == 1
 
-    assert jobs["stub-job"] == STUB
-    assert caplog.text == ""
 
+async def test_capabilities_follow_plugin_name_order(session: AsyncSession, stub_plugin: SparkthPlugin) -> None:
+    """The composed prompt must not depend on which plugin was imported first."""
+    early = SparkthPlugin("aaa-early")
```

**Review:**

> this plugin might leak into other tests as it never gets cleaned up the way the fixtures do. could turn it into a
> fixture like `stub_plugin`.

## Example 4

**Issue:** _mock_http and 'no tool takes a credential' test duplicated across plugins; move to sparkth.lib.testing.

`sparkth/plugins/moodle/tests/test_tools.py`

```diff
+
+
+async def test_a_tool_calls_moodle_with_the_callers_stored_settings(session: AsyncSession) -> None:
+    plugin = Plugin(name="moodle", enabled=True)
+    user = User(id=1, name="U", username="u1", email="u1@example.com", hashed_password="x")
+    session.add_all([plugin, user])
+    await session.commit()
+    stored = {"api_url": "https://stored.example.com", "api_key": "stored-key"}
+    session.add(UserPlugin(user_id=1, plugin_id=cast(int, plugin.id), config=stored))
+    await session.commit()
+    bind_current_user_id(1)
+    response = AsyncMock()
```

**Review:**

> same as `_mock_http` in `canvas/tests/test_tools.py:21`, and the "no tool takes a credential" test is duplicated
> across both files as well. we can add all these duplications to `sparkth.lib.testing`.

## Example 5

**Issue:** Test checks a hardcoded plugin list that misses additions; compare against FRONTEND_PLUGIN_NAMES.

`frontend/tests/app/plugins.test.ts`

```diff
@@ -11,4 +12,10 @@ describe("frontend plugin registry vs backend declarations", () => {
       .sort();
     expect(registered).toEqual([...FRONTEND_PLUGIN_NAMES].sort());
   });
+
+  it("sets a settings row for every plugin", () => {
+    expect([...SETTINGS_ITEMS.keys()]).toEqual(
+      expect.arrayContaining(["chat", "google-drive", "pxc", "slack"]),
```

**Review:**

> this checks a hardcoded list that won't catch any additions. maybe compare against `FRONTEND_PLUGIN_NAMES` like the
> test above does.

## Example 6

**Issue:** Drop the one-time migration test; not needed on every CI run.

`sparkth/plugins/compose/tests/test_saved_view_rename_migration.py`

```diff
@@ -0,0 +1,56 @@
+import json
```

**Review:**

> do we really need this migration test?
> This is a one time activity, we dont need to test for this on every commit/CI run
