# Type safety

Real review comments from Sparkth pull requests: type hints, optional fields, type: ignore.

## Example 1

**Issue:** About 15 type: ignore comments in the PR; asks why and requests removing them.

`app/core_plugins/chat/routes/attachments.py`

```diff
+    response_model=list[AttachedDriveFileResponse],
+)
+async def list_conversation_attachments(
+    conversation: Conversation = Depends(get_owned_conversation),
+    session: AsyncSession = Depends(get_async_session),
+    service: ChatService = Depends(get_chat_service),
+) -> list[AttachedDriveFileResponse]:
+    drive_files = await service.list_conversation_attachments(
+        session,
+        conversation_id=conversation.id,  # type: ignore
+    )
+    return [AttachedDriveFileResponse(id=f.id, name=f.name, size=f.size) for f in drive_files]  # type: ignore
```

**Review:**

> Why the `# type: ignore`? There are about ~15 in this PR. Were they backported from a previous change? Can we get
> rid of them?

## Example 2

**Issue:** Replace type: ignore with typing.cast(int, conversation.id).

`app/core_plugins/chat/routes/completions.py`

```diff
+    first_user_text = get_first_user_text(messages)
+    if first_user_text:
+        title_provider = get_provider(
+            provider_name=provider_name,
+            api_key=api_key,
+            model=model,
+            temperature=config.title_llm_temperature,
+            max_tool_executions=0,
+        )
+        background_tasks.add_task(
+            generate_conversation_title,
+            conversation_id=conversation.id,  # type: ignore[arg-type]
```

**Review:**

> we can get rid of this type-ignore by doing:
> ```
> from typing import cast
> ...
> conversation_id=cast(int, conversation.id),
> ```
>
> The `typing.cast` function does nothing in itself, it just returns the same value, it is just a helper for mypy to
> know the type of argument being passed, in our case we know that `conversation.id` here is an `int`, since it is
> being retreived from the `Conversation` DB model and the model has an `int` column for `id`

## Example 3

**Issue:** Why are all context fields optional; expected mandatory.

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

> Why are all these fields optional? I would expect them to be mandatory.

## Example 4

**Issue:** Type-hint the AUDIT_EVENTS hook consistently with other hook definitions.

`app/core/audit/events.py`

```diff
+    def require(self, event_cls: type[BaseAuditEvent]) -> None:
+        """Assert ``event_cls`` is the registered class for its event type.
+
+        Raises:
+            UnknownAuditEventTypeError: The class (or its event type) is not
+                registered; recording it is a programming error.
+        """
+        if self._types.get(event_cls.event_type) is not event_cls:
+            raise UnknownAuditEventTypeError(event_cls.event_type)
+
+
+AUDIT_EVENTS = AuditEventTypeHook()
```

**Review:**

> lets type hint this hook to stay consistent with hook definitions throughout the codebase

## Example 5

**Issue:** Do not add type: ignore comments that are already slated for removal; file an issue.

`sparkth/core/audit/models.py`

```diff
+    """One audited action, carrying the NIST AU-3 six fields plus AI provenance.
+
+    ``canonical_bytes`` holds the pinned canonical serialization of the event
+    (see :mod:`app.core.audit.canonical`) so the tamper-evidence sealer can
+    later hash exactly what was written, byte for byte.
+    """
+
+    __tablename__ = "audit_events"
+
+    # Column names starting with "model_" are intentional (AI provenance);
+    # disable pydantic's protected namespace check for them.
+    model_config = ConfigDict(protected_namespaces=())  # type: ignore[assignment]
```

**Review:**

> sure, lets create an issue about it, but still we should avoid adding thing that we already intend on removing.
> The similar comments that exist in the codebase are already on death row.
