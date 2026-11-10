# Project guideline violations

Real review comments from Sparkth pull requests: code that breaks a written Sparkth rule.

## Example 1

**Issue:** Route handler still ~300 lines; extract rag-intent routing and ~55 lines of exception handling.

`app/core_plugins/chat/routes/completions.py`

```diff
+        logger.info("Auto-including all %d available tools (default)", len(tools))
+        return tools
+    if request.tools and isinstance(request.tools, list):
+        tools = await tool_registry.get_tools_by_names(request.tools)
+        if not tools:
+            logger.warning("No tools found for: %s", request.tools)
+        return tools
+    return None
+
+
+@router.post("/completions", response_model=ChatCompletionResponse)
 async def chat_completion(
```

**Review:**

> Even after being refactored this route handler spans almost 300 lines. Thats a clear indication that it should be
> broken down into more pieces.
>
> One of the suggestions is to take the rag-intent-router logic out in a utility function, second is that the
> exception handling alone is almost one-sixth of this function, from line 385-to-399 and from line 627-to-668. Thats
> 55 lines just for exception handling

## Example 2

**Issue:** Don't re-export enums from models.py; clients should import from the enums module.

`app/core_plugins/slack/models.py`

```diff
-    no_files_resolved = "no_files_resolved"
-    rag_not_ready = "rag_not_ready"
-    drive_file_not_found = "drive_file_not_found"
-    retrieval_error = "retrieval_error"
-
-
-class ConnectionEventType(str, Enum):
-    connected = "connected"
-    disconnected = "disconnected"
+__all__ = [
+    "ConnectionEventType",
+    "ResponseType",
```

**Review:**

> We should not re-export `ConnectionEventType` and `ResponseType` from this file, if any client wants to use it they
> should import it from `app.core_plugins.slack.enums`

## Example 3

**Issue:** Move the lazy pydantic import to the top to avoid misleading the agent.

`app/lib/mcp/hooks.py`

```diff
+        return schema
+
+    except (TypeError, NameError, AttributeError) as e:
+        logger.warning(f"Failed to generate input schema for {func.__name__}: {e}. Using empty schema.")
+        return {"type": "object", "properties": {}}
+
+
+def type_to_json_schema(py_type: Type[Any]) -> dict[str, Any]:
+    """Convert a Python type to a JSON Schema type definition."""
+    # Check if it's a Pydantic BaseModel
+    try:
+        from pydantic import BaseModel
```

**Review:**

> Lets move this lazy import to the top, Claude might start getting the wrong ideas because of this

## Example 4

**Issue:** Don't use keyword arguments when not needed; pass retrieve_context arguments positionally.

`app/core_plugins/slack/rag.py`

```diff
@@ -217,11 +165,11 @@ async def answer_question(
         return NO_FILES_RESOLVED_MESSAGE, ResponseType.no_files_resolved
 
     try:
-        contexts = await _run_agent_fan_out(
+        chunks = await retrieve_context(
             user_id=user_id,
             file_ids=file_ids,
-            question=question,
-            agent_llm=agent_llm,
+            query=question,
+            llm=agent_llm,
```

**Review:**

> Don't use keyword arguments when not needed. Write instead:
>
> ```
> retrieve_context(
>             user_id,
>             file_ids,
>             question,
>             agent_llm
> )
> ```

## Example 5

**Issue:** Avoid relative imports; use @/ alias everywhere in this PR.

`frontend/plugins/chat/components/messages/AssistantMessage.tsx`

```diff
@@ -7,7 +7,7 @@ import { OptionsPrompt } from "./OptionsPrompt";
 import { answeredOptions, splitOptionsBlock } from "./optionsBlock";
 import ReactMarkdown from "react-markdown";
 import remarkGfm from "remark-gfm";
-import { truncate, RAG_DISPLAY_NAME_MAX_CHARS } from "@/lib/utils";
+import { truncate, RAG_DISPLAY_NAME_MAX_CHARS } from "../../utils";
```

**Review:**

> lets avoid using relative paths for imports, this shows up in multiple places in this PR, lets fix it everywhere.

## Example 6

**Issue:** Tests import from app.core; should import from the app.lib facade instead.

`app/core_plugins/chat/tests/test_conversation_attachments.py`

```diff
@@ -8,9 +8,10 @@
 from sqlalchemy.exc import IntegrityError
 from sqlmodel.ext.asyncio.session import AsyncSession
 
+from app.core.documents.enums import DocumentStatus
+from app.core.documents.models import Document
```

**Review:**

> Do we need to import from app.core in tests or can we instead import from app.lib?
>
> Same question about tests below.

## Example 7

**Issue:** Questions the type: ignore on plugin_class() and calls the explanatory comment redundant.

`sparkth/core/plugins/loader.py`

```diff
@@ -52,36 +53,58 @@ def _load_all(self) -> None:
             Continues loading other plugins if one fails.
             Check logs for any failures.
         """
-        for plugin_name, plugin_class in self.iter_plugin_classes():
+        for plugin_class in self.iter_plugin_classes():
             try:
-                plugin_instance = plugin_class(plugin_name)
+                # Concrete plugin classes declare a no-argument __init__ that
+                # passes their name to super().__init__(); only the base class
+                # takes the name parameter, hence the call-arg ignore.
+                plugin_instance = plugin_class()  # type: ignore[call-arg]
```

**Review:**

> Any reason why we need `type: ignore`? Also the comment is redundant.

## Example 8

**Issue:** Gate with USER_READ.require() in router dependencies, not a manual can() check mid-handler; decide whether
usernames are always served.

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

> instead of checking the permission manually here via `can` this should be placed in the `dependencies` argument of
> `@router.get`.
>
> If a user doesn't have permission to read usernames, no point in coming this far down the route handler.
>
> This approach of checking permission is discouraged and permissions should be checked via `USER_READ.require()` or
> `USER_READ.require_in_global_scope()`
>
> The only reason to check for this permission half way is if we want to serve the analytics via this endpoint with
> the usernames as optional in the response. I dont think we should do this. We should either serve the usernames
> (which i think we should) or we should not. We need to make a decision about this, and depending on that decision we
> should set the appropriate permissions for this endpoint
