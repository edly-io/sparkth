# Function & API design

Real review comments from Sparkth pull requests: signatures, arguments, return values, API contracts.

## Example 1

**Issue:** Why have a get_chat_system_config accessor if the config object must be threaded through every child call?

`app/core_plugins/chat/conversation_title.py`

```diff
@@ -43,17 +44,18 @@ async def generate_conversation_title(
     first_user_message: str,
     service: ChatService,
     provider: BaseChatProvider,
+    config: ChatSystemConfig,
```

**Review:**

> What's the point of a `get_chat_system_config` function if we need to pass the config object around in all child
> function calls?

## Example 2

**Issue:** Order arguments from most to least relevant: query, file_ids, user_id, llm.

`app/lib/rag.py`

```diff
+                new_count, reused_count = await store_and_link_chunks(session, user_id, owner_file_id, chunks, store)
+            await session.commit()
+
+    return IngestionResult(new_chunks=new_count, reused_chunks=reused_count)
+
+
+async def agentic_retrieve_context(
+    user_id: int,
+    file_ids: list[int],
+    query: str,
+    llm: BaseChatModel,
+) -> list[RetrievedChunk]:
```

**Review:**

> In both exposed functions I'm not a fan of the argument order. It's a personal thing, I don't have a fixed rule to
> order arguments. But I tend to list arguments from most to least relevant, and I try to keep the order consistent
> between different functions. In this case, I'd write:
>
> ```
> async def agentic_retrieve_context(
>     query: str,
>     file_ids: list[int],
>     user_id: int,
>     llm: BaseChatModel,
> ) -> list[RetrievedChunk]:
> ```
>
> This is a personal thing though, so I'm fine with a different approach.

## Example 3

**Issue:** Add RequireGlobalPermission so callers need not import the GLOBAL object.

`app/api/v1/whitelist.py`

```diff
@@ -14,7 +20,7 @@
 @router.get(
     "/",
     response_model=list[WhitelistedEmailResponse],
-    dependencies=[Depends(RequirePermission("email.whitelist.read", "global"))],
+    dependencies=[Depends(RequirePermission(EMAIL_WHITELIST_READ, GLOBAL))],
```

**Review:**

> I think this tells us that we need a `RequireGlobalPermission` function. That way we would not have to import the
> GLOBAL object.

## Example 4

**Issue:** get methods customarily take a default= argument.

`app/lib/hooks.py`

```diff
@@ -74,3 +74,7 @@ def iter_values(self) -> Iterator[N]:
 
     def iter_items(self) -> Iterator[tuple[str, N]]:
         yield from self._items.items()
+
+    def get(self, name: str) -> N | None:
```

**Review:**

> nit: In `get` methods it's customary to add a `default=` argument.

## Example 5

**Issue:** AuditEvent constructor with 38 arguments is too complex; move assembly into constructor with properties.

`sparkth/core/audit/recorder.py`

```diff
+        error_detail=error_detail,
+        target_type=target_type,
+        target_id=target_id,
+        old_values=redacted_old,
+        new_values=redacted_new,
+        tool_name=tool_name,
+        tool_args=redacted_args,
+        model_provider=model_provider,
+        model_name=model_name,
+        model_version=model_version,
+        purpose=purpose,
+        canonical_bytes=canonical_bytes,
```

**Review:**

> Still, the AuditEvent class constructor is way too complex. We can't have a class that takes 38 arguments. Why isn't
> this code all part of the class constructor? Some of the class attributes could then be converted to properties to
> make sure that the values are always up-to-date and consistent with the attributes.

## Example 6

**Issue:** Invalid tool arguments should be ToolFailureKind.VALIDATION, not UNKNOWN, which is misleading.

`sparkth/llm/providers.py`

```diff
@@ -297,7 +315,7 @@ async def _execute_tool(self, tool_name: str, tool_args: dict[str, Any], tools:
                             tool_args = validated.model_dump()
                         except (ValidationError, TypeError, ValueError) as e:
                             logger.warning(f"Tool '{tool_name}' argument validation failed: {e}")
-                            return f"Invalid arguments for tool '{tool_name}': {e}"
+                            return f"Invalid arguments for tool '{tool_name}': {e}", ToolFailureKind.UNKNOWN
```

**Review:**

> If we know that a tool arguments are invalid, should we not report something like a 400 `BAD_REQUEST` or 422
> `UNPROCESSABLE_CONTENT`? We already have `ToolFailureKind.VALIDATION` for this.
>
> `ToolFailureKind.UNKNOWN` seems misleading if we know that we are bad arguments
