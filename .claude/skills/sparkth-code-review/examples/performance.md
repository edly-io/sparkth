# Performance

Real review comments from Sparkth pull requests: redundant queries, unbounded growth, per-request cost.

## Example 1

**Issue:** Pre-check SELECT is a redundant round trip now that unique constraint and IntegrityError translation exist.

`sparkth/services/whitelist/service.py`

```diff
-                raise ValueError(f"Invalid domain format: {value}")
+                raise InvalidWhitelistValue(f"Invalid domain format: {value}")
             entry_type = "domain"
         else:
             try:
                 _EmailValidator(email=normalized)
             except ValidationError as exc:
-                raise ValueError(f"Invalid email format: {value}") from exc
+                raise InvalidWhitelistValue(f"Invalid email format: {value}") from exc
             entry_type = "email"
 
         result = await session.exec(select(WhitelistedEmail).where(WhitelistedEmail.value == normalized))
```

**Review:**

> Now that `value` has `unique=True` and the commit below translates `IntegrityError` into
> `WhitelistEntryAlreadyExists`, this pre-check SELECT is a redundant round trip.

## Example 2

**Issue:** Old revisions never removed so each edit grows PXC_DATA_DIR; prune older revisions, e.g. keep the last two.

`sparkth/plugins/pxc/revisions.py`

```diff
+    return get_pxc_settings().data_dir / "revisions" / activity_id
+
+
+def publish_revision(staged: Path, activity_id: str) -> Path:
+    """Move a staged activity into a new revision, make that revision live, and return it.
+
+    ``staged`` must sit on the data directory's filesystem, so moving it is a rename. The link's
+    target is relative, so the data directory can be mounted anywhere. If the link cannot be made
+    live, the new revision and the temporary link are removed, the live revision is untouched, and
+    the error is raised.
+    """
+    revision = revisions_dir(activity_id) / str(uuid7())
```

**Review:**

> old revisions are never removed, once updates exist, each edit grows `PXC_DATA_DIR` by a full build, and that never
> shrinks.
>
> in the update PR, delete revisions older than the previous one once nobody can still be using them. A simple version
> is "keep the last two".

## Example 3

**Issue:** Every turn sends every section and tool, so plain turns pay for the whole pxc prompt; keep in mind.

`sparkth/plugins/chat/routes/completions.py`

```diff
-                content=gettext(turn_end),
-                message_type="text",
-            )
-            return _refusal_response(turn_end, request.stream, conversation.uuid, model, provider_name)
+                return _refusal_response(REFUSAL_MESSAGE, request.stream, conversation.uuid, model, provider_name)
 
         provider = get_provider(
             provider_name=provider_name,
             api_key=api_key,
             model=model,
-            system_prompt=render_system_prompt([responsibility]),
+            system_prompt=render_system_prompt(list(jobs.values())),
```

**Review:**

> every turn now sends every section and every tool, so a plain course design turn also pays for the whole pxc prompt
> and its tool schemas. probably fine, just something to keep in mind as more plugins come in.

## Example 4

**Issue:** Questions whether so many attributes per row are needed in the list response.

`sparkth/services/audit/schemas.py`

```diff
+            raise ValueError("'from' must not be after 'to'")
+        return self
+
+
+class AuditEventPageQuery(AuditEventQuery):
+    """The filters plus a keyset cursor: up to ``limit`` events older than ``before_id``."""
+
+    limit: int = Field(default=DEFAULT_PAGE_SIZE, ge=1, le=MAX_PAGE_SIZE)
+    before_id: int | None = Field(default=None, ge=1)
+
+
+class AuditEventRecord(BaseModel):
```

**Review:**

> do we actually need this many attributes being sent to the frontend per row?
