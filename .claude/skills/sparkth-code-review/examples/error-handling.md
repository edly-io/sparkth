# Error handling

Real review comments from Sparkth pull requests: which errors to catch, raise, log or let crash.

## Example 1

**Issue:** IntegrityError check is ambiguous about cause; do an explicit existing_for_team check instead.

`app/core_plugins/slack/oauth.py`

```diff
+
+        workspace = SlackWorkspace(
+            user_id=user_id,
+            team_id=team_id,
+            team_name=team_name,
+            bot_token_encrypted=encrypt_token(bot_token),
+            bot_user_id=bot_user_id,
+        )
+        session.add(workspace)
+        try:
+            session.commit()
+        except IntegrityError as exc:
```

**Review:**

> I think the IntegrityError check is still pretty ambiguous, there's nothing that tells us that the error is related
> to an existing team workspace. Why not create the same type of check as above, with `existing_for_team`?

## Example 2

**Issue:** JsonParseError inherits status_code that doesn't fit parse errors; use json.JSONDecodeError instead.

`app/lib/exceptions.py`

```diff
+        self.status_code = status_code
+        super().__init__(self._format_message())
+
+    def _format_message(self) -> str:
+        return f"{self.message} (status_code={self.status_code})"
+
+
+class AuthenticationError(BaseError):
+    pass
+
+
+class JsonParseError(BaseError):
```

**Review:**

> this exception class inherits from `BaseError` and base error has a `status_code`. Im not sure if a json parse error
> will always have a error status code.
>
> I think the `json.JSONDecodeError` class should be used for any json parsing related exception handling

## Example 3

**Issue:** Raise a regular exception and let FastAPI convert it to 500 instead of HTTPException.

`app/core/permissions/__init__.py`

```diff
+        async def dependency(
+            request: Request,
+            current_user: User = Depends(get_current_user),
+            session: AsyncSession = Depends(get_async_session),
+        ) -> User:
+            if scope_param is not None and scope_param not in request.path_params:
+                logger.error(
+                    "Permission dependency misconfigured: scope_param %r is not among the route's path params %s",
+                    scope_param,
+                    list(request.path_params),
+                )
+                raise HTTPException(
```

**Review:**

> Instead of raising a 500 error, we should just raise a regular exception, which will then be converted to 500 by
> FastAPI.

## Example 4

**Issue:** App should crash if FRONTEND_DIR is missing when serving is enabled; remove silent skip check.

`sparkth/main.py`

```diff
 
 
+def mount_frontend(application: FastAPI) -> None:
+    """Mount the static frontend export at "/" when serving is enabled.
+
+    Serving is opt-in via SERVE_FRONTEND (the production image enables it) and
+    additionally requires FRONTEND_DIR to exist.
+    """
+    frontend_settings = get_settings()
+    if not frontend_settings.SERVE_FRONTEND:
+        return
+    if not frontend_settings.FRONTEND_DIR.exists():
```

**Review:**

> I think the app should crash if the directory does not exist. We should not attempt to serve the app without serving
> the frontend. So this check is not necessary.

## Example 5

**Issue:** Swallowed exception should log the actual exception since it is not re-raised.

`sparkth/plugins/googledrive/utils.py`

```diff
@@ -243,6 +243,16 @@ async def _process_single_file(
         await session.refresh(drive_file)
         await update_document_status(session, document_id, DocumentStatus.FAILED, "Database integrity error")
         await session.commit()
+    except Exception:
+        # Deliberate lifecycle backstop, not lazy catching: PROCESSING was committed
+        # before ingestion, and later syncs skip in-flight documents, so any unexpected
+        # error escaping here would wedge the document in PROCESSING forever. The
+        # folder-level gather only logs — it cannot fix the status. Roll back the
+        # partial work, record the failure, and swallow (fully handled here).
+        logger.exception("Unexpected error while processing '%s'", log_name)
```

**Review:**

> This should log the actual exception, since we are not re-raising it.
