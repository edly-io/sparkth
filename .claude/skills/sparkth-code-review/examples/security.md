# Security

Real review comments from Sparkth pull requests: authorization, input limits, secrets.

## Example 1

**Issue:** f-string interpolation into SQL constraint resembles injection pattern; question keeping it.

`app/core/permissions/models.py`

```diff
@@ -44,9 +44,9 @@ class RoleAssignment(TimestampedModel, SoftDeleteModel, table=True):
         # object, every other scope must. Enforced in the database so no code path
         # can persist a contradictory pair.
         CheckConstraint(
-            f"(scope = '{SCOPE_GLOBAL}' AND scope_object_id IS NULL) "
+            f"(scope = '{GLOBAL.name}' AND scope_object_id IS NULL) "
```

**Review:**

> I just noticed this piece of code, though it was not introduced in this PR. This pattern is generally avoided,
> because it's typical of SQL injection. In this particular case we don't run the risk of SQL injection, because
> GLOBAL.name is a hardcoded variable. But I'm afraid that this pattern could be replicated elsewhere. Are we OK with
> keeping this here? I'm not familiar with this pattern so I can't suggest alternatives.

## Example 2

**Issue:** No limit on how many builds one author can start; add a per-user limit in build_activity or the tool.

`sparkth/plugins/pxc/tools.py`

```diff
+    If the build fails, the error explains why (an invalid manifest, a rejected import, compiler
+    output, or the sandbox failing to start). Fix the files and call this again.
+    """
+    source = ActivitySource(
+        title=title,
+        description=description,
+        manifest=_manifest_object(manifest),
+        ui_js=ui_js,
+        sandbox_js=sandbox_js,
+    )
+    activity = await build_activity(source, current_user_id())
+    return {"activity_id": str(activity.id), "preview_url": preview_url(activity.id)}
```

**Review:**

> the server doesn't limit how many builds one author can start. maybe add a per-user limit in `build_activity` or the
> tool.

## Example 3

**Issue:** Input is validated before the caller identity is checked; resolve current_user_id() first and pass owner to
build_activity.

`sparkth/plugins/pxc/tools.py`

```diff
+
+    If the build fails, the error explains why (an invalid manifest, a rejected import, compiler
+    output, or the sandbox failing to start). Fix the files and call this again.
+    """
+    source = ActivitySource(
+        title=title,
+        description=description,
+        manifest=_manifest_object(manifest),
+        ui_js=ui_js,
+        sandbox_js=sandbox_js,
+    )
+    activity = await build_activity(source, current_user_id())
```

**Review:**

> this method validates the input before checking who the caller is. setting `owner = current_user_id()` as the first
> line and passing `owner` to `build_activity` would be better.

## Example 4

**Issue:** Documented behaviour lets disabled plugins' tools be called when requested; they should be left out.

`docs/guides/plugins.md`

```diff
+order. Chat contributes its own, course design. A plugin that is switched off contributes no
+section and no scope.
+
+- **Scope gate.** Each message is judged against every enabled scope. A message that fits none
+  is refused with a fixed sentence before the model runs. A refused first message writes nothing; a refused later message is stored in the
+  conversation, with the refusal as the assistant's reply. If the classification fails, the
+  message is admitted.
+- **System prompt.** The prompt is chat's skeleton with each enabled capability's section under
+  its title. The skeleton owns the date, the assistant's identity, the output language, the
+  refusal, injection and offering-choices rules, so a section must not repeat them. A section
+  holds the capability's workflow, plus any language or guardrail rules specific to it.
+- **Tools.** Every turn gets all the tools the request asks for.
```

**Review:**

> ideally this shouldn't be the case. disabled plugins tools should be left out, even if requested.

## Example 5

**Issue:** Access token cached in Redis as plain text; probably fine as short-lived but state it explicitly.

`sparkth/plugins/openedx/client.py`

```diff
 
-        if not token_response.access_token.strip():
-            raise AuthenticationError(401, "empty access_token")
-
-        self.access_token = token_response.access_token
-        self.refresh_token = token_response.refresh_token or refresh_token
-        return token_response.model_dump()
+        granted = await self.get_token()
+        ttl = None
+        if granted.expires_in is not None:
+            ttl = max(granted.expires_in - OPENEDX_ACCESS_TOKEN_TTL_MARGIN_SECONDS, 1)
+        await cache.set(key, granted.access_token, ttl)
```

**Review:**

> the token goes into redis as plain text. as it's short lived, it's probably fine, but we should say that explicitly.
