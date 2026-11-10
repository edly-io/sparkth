# Documentation & comments

Real review comments from Sparkth pull requests: docstrings, comments and guides that stay accurate.

## Example 1

**Issue:** Remove lazy import from the docstring example so the agent doesn't copy the pattern.

`app/plugins/base.py`

```diff
-                        from starlette.middleware.cors import CORSMiddleware
-
-                        self.add_middleware(
-                            Middleware(
-                                CORSMiddleware,
-                                allow_origins=["*"],
-                                allow_methods=["*"]
-                            )
-                        )
+        def __init__(self, name: str):
+            super().__init__(name)
+            from starlette.middleware.cors import CORSMiddleware
```

**Review:**

> do we need to have this lazy import in this code example? because claude might start making this lazy middleware
> import looking at this.

## Example 2

**Issue:** Don't mention PR numbers in the codebase.

`app/core_plugins/slack/rag.py`

```diff
     RAGNotReadyError,
     RAGRetrievalError,
+    RagStatus,
+    RetrievedChunk,
+    agentic_retrieve_context,
 )
-from app.rag.store import SimilarityResult
-from app.rag.types import RAGContext, RagStatus
-from app.rag.utils import resolve_source_name
+from app.llm.providers import BaseChatProvider
+from app.models.drive import DriveFile
+from app.rag.utils import resolve_source_name  # internal helper for source-name resolution (residual; see #398)
```

**Review:**

> Let's not mention PR numbers in the code base...

## Example 3

**Issue:** Don't refer to past implementations in docstrings.

`app/core_plugins/slack/rag.py`

```diff
-      3. Aggregate. If no chunks are returned across any file, reply with the
-         configured fallback_message.
+      2. Retrieve relevant chunks via agentic_retrieve_context (validates all files READY,
+         fans out internally across all file_ids).
+      3. If no chunks are returned, reply with the configured fallback_message.
       4. Optionally synthesize via LLM; otherwise return formatted raw chunks.
 
     Each operational failure mode maps to its own distinct user-facing message and
     ResponseType. config.fallback_message is reserved ONLY for the case where the
     agent ran successfully but found no relevant chunks.
 
+    Note: unlike the previous fan-out implementation, a single per-file agent failure
```

**Review:**

> Let's not refer to past implementations.

## Example 4

**Issue:** Docstrings should not refer to other classes since they can drift.

`app/core/audit/events.py`

```diff
+    @property
+    def action(self) -> str:
+        return self.event_type.partition(".")[2]
+
+
+E = TypeVar("E", bound=BaseAuditEvent)
+
+
+class AuditEventTypeHook:
+    """Flat hook mapping event types to their event classes.
+
+    Like :class:`app.lib.hooks.SingleNamedItemHook` but keyed by
```

**Review:**

> Lets not refer to other classes in any doc-strings.
> If those classes change, this information will get outdated and we are at risk of a drift in the codebase

## Example 5

**Issue:** Jargon like object-bearing cascade/scope is unclear; use more human-friendly terms.

`docs/guides/permissions.md`

```diff
+
+A **group** is a flat, named set of users — the second assignee source for role grants.
+Granting a role to a group at a scope is one `group_role_assignment` row, and every active
+member holds that role there: "every math instructor gets the teacher role in course 42" is
+one grant instead of one `role_assignment` per instructor, and membership churn (someone
+joins or leaves the set) is a membership edit, not a grant edit.
+
+- Groups are **flat by design** — no group-in-group nesting. Organizational hierarchy
+  ("teachers belong to departments, which belong to universities") is a *scope*-hierarchy
+  concern, answered by where in the scope tree a group's grant is placed, not by nesting
+  groups (see [#420](https://github.com/edly-io/sparkth/issues/420) Phase 2 for
+  object-bearing cascade).
```

**Review:**

> I have no idea what "object-bearing cascade" means. Is it some sort of whitewater sport? Further down there is the
> term "object-bearing scope". Is that some sort of telescope?
>
> In all seriousness, we should use a more human-friendly term here ;)

## Example 6

**Issue:** Reference information belongs in docstrings rendered into generated docs, not the guide.

`docs/guides/plugins.md`

~~~diff
+)
+
+
+class MyAppPlugin(SparkthPlugin):
+    def __init__(self) -> None:
+        super().__init__("my-app")
+        DISPLAY_INFO.add_item(self, DisplayInfo("My App", "What the plugin does, in one line", icon="sparkles"))
+        SIDEBAR_ENTRIES.add_item(self, SidebarEntry("My App", icon="sparkles", order=5))
+        FRONTEND_APPS.add_item(self, FrontendApp())
+```
+
+- **`DISPLAY_INFO`**: the human-facing identity (display name, description, optional icon) shown in settings and catalogs. Every plugin should register one; without it the plugin appears with only its slug name.
~~~

**Review:**

> This sort of reference information would be more appropriate as docstring to be included in the generated docs.

## Example 7

**Issue:** Make event docstrings concise; a few words per attribute, no unnecessary detail.

`sparkth/plugins/chat/analytics.py`

```diff
@@ -189,6 +190,107 @@ class ChatAttachmentUnusable(AnalyticsEventSchema):
     status: Literal["queued", "processing", "failed", "deleted"]
 
 
+class ChatScopeClassified(AnalyticsEventSchema):
```

**Review:**

> lets make the doc-strings concise. A few words about an attribute should do the job, lets also avoid adding
> unnecessary details in doc-strings

## Example 8

**Issue:** Use a doc-string instead of a comment and add that instruction to CLAUDE.md; this keeps recurring.

`frontend/lib/analytics/client.ts`

```diff
@@ -26,3 +26,16 @@ export async function fetchChatActivity(
     }),
   );
 }
+
+// Every Overview figure, counted for the period and the one before it, in one request.
```

**Review:**

> lets make this s doc-string instead of a comment, also add this instruction to the CLAUDE.md file.
> This has been happening alot

## Example 9

**Issue:** Comment still describes only the cards though the component now also draws the trend.

`frontend/app/dashboard/analytics/page.tsx`

```diff
@@ -25,7 +56,7 @@ export default function OverviewPage() {
 }
 
 // The server declares the figures; this draws one card each and links it to its view.
```

**Review:**

> This comment still only describes the cards, but the component now draws the trend too.

## Example 10

**Issue:** Keep docs drive-agnostic; don't name Google Drive, list supported drives in a later section.

`docs/user-guide/index.md`

```diff
+
+This guide is for instructors and administrators using Sparkth in the browser. If you run the
+server yourself, see the developer docs instead.
+
+## Find your way around
+
+After you sign in, the sidebar on the left takes you everywhere:
+
+| Sidebar entry | What it opens |
+|---|---|
+| **Create Course** | The AI assistant that writes your course. Shown once Compose is turned on in **My Plugins**. |
+| **Resources** | Files you have imported from Google Drive for the assistant to use. |
```

**Review:**

> lets not specifically mention GoogleDrive here, we should keep this documentation name agnostic. We should only
> mention that you can connect to an online drive in the resources section, in a later section we can list what drives
> are supported as of the latest release.
