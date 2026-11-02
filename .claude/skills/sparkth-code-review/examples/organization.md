# Codebase organization

Real review comments from Sparkth pull requests: where code and files live, module splits, file naming, test
placement.

## Example 1

**Issue:** Move route-helper functions out of completions.py into routes/utils.py, keeping only route definitions.

`app/core_plugins/chat/routes/completions.py`

```diff
@@ -261,7 +216,156 @@ async def _persist_pre_stream_error(
         logger.exception("Failed to persist pre-stream error message for conversation %s", request.conversation_id)
 
 
-@chat_router.post("/completions", response_model=ChatCompletionResponse)
+async def _get_or_create_conversation(
```

**Review:**

> lets move all chat routes related utility functions to a separate `app/core_plugins/chat/routes/utils.py` file.
> Lets only keep route definitions in the relevant routes file. It would make it more readable and maintainable
>
> Same for the following `_attach_request_drive_files`, `_persist_incoming_messages`, `_classify_in_scope`,
> `_resolve_tools` functions

## Example 2

**Issue:** Move the LMS rules system prompt into assets/lms_rules_system_prompt.txt.

`app/core_plugins/chat/lms_credentials.py`

**Review:**

> This is a system prompt and should be moved to `app/core_plugins/chat/assets/lms_rules_system_prompt.txt`

## Example 3

**Issue:** Be careful with generic utils modules; name modules more accurately.

`app/core_plugins/chat/tools.py`

```diff
@@ -345,6 +353,15 @@ def _get_python_type(self, json_schema: dict[str, Any]) -> type:
         return type_map.get(json_type, str)
 
 
+def get_parameters_schema(args_schema: type[BaseModel] | dict[str, Any] | None) -> dict[str, Any]:
```

**Review:**

> Let's be careful with "utils" modules. Whenever possible, let's name the modules more accurately.

## Example 4

**Issue:** Move the Slack plugin's tests into the plugin directory.

**Review:**

> Lets move the plugin's tests into the plugin directory as well

## Example 5

**Issue:** Split monolithic routes.py into a routes package with oauth.py and remaining endpoints in __init__.py.

`app/core_plugins/slack/routes/__init__.py`

```diff
@@ -11,6 +11,7 @@
 from langchain_core.exceptions import LangChainException
```

**Review:**

> can we break this monolithic `routes.py` into a module.
> lets create a routes module named `routes`, inside it we can have a `oauth.py` file which houses all the `/oauth`
> routes and their helping utilities.
> The rest of the endpoints seem one-off so we can put them in the __init__.py file along with their utilities.
>
> Let me know if this approach feels better

## Example 6

**Issue:** Env-configurable values go in config.py; non-configurable constants stay in constants.py.

`app/core_plugins/slack/constants.py`

```diff
@@ -1,9 +1,11 @@
-import os
```

**Review:**

> yes, anything that is configureable via the env should be moved to `config.py` and stuff thats not configurable can
> be left here

## Example 7

**Issue:** Turn hooks.py into a hooks package with routes, models submodules, keeping the same import path.

**Review:**

> Everything looks good, just one question related to organizing the hooks, instead of having a `hooks.py` for
> everyhting can we have one hooks module and then add files in it for things like `routes`, `models` etc?
>
> So everything in `app/lib/hooks.py` would move to `app/lib/hooks/__init__.py` and will be available for import with
> the same path `app.lib.hook`
> and everything inside `app/lib/routes/hooks.py` would move to `app/lib/hooks/routes.py` and so on
>
> Let me know if you think there is a downside in organizing hooks like this

## Example 8

**Issue:** Move the remaining app/rag_mcp files into app/rag/mcp since only rag uses them.

`app/rag/agent_tools.py`

```diff
@@ -0,0 +1,78 @@
+"""Build in-process LangChain tools for the RAG search agent.
```

**Review:**

> Would it be better if we move the entire `app/rag_mcp` directory to `app/rag/mcp` and have everything live there.
>
> the `main.py` and `server.py` files are already being removed in this PR which only leaves the `schemas.py` and
> `tools.py`. These are only being used in the `app/rag` module, so maybe its better if we move these files there

## Example 9

**Issue:** Rename models.py holding pydantic models to schemas.py for consistency.

`app/core_plugins/canvas/schemas.py`

```diff
@@ -1,8 +1,17 @@
 from datetime import datetime
```

**Review:**

> In other plugins/modules, we are using `schemas.py` for pydantic models and `models.py` for SQLAlchemy models, so
> `schemas.py` would be a better name for this file.

## Example 10

**Issue:** Avoid adding to app/models/__init__.py; import the model from its full path instead.

`app/models/__init__.py`

```diff
@@ -1,3 +1,4 @@
+import app.core.documents.models  # noqa: F401 — loads Document table into SQLModel metadata
```

**Review:**

> Can we avoid adding stuff to this `__init__.py` file by importing from the full model path? Unless I'm mistaken the
> declarations in this file are not useful so we should avoid adding new stuff there.
>
> A bigger cleanup of `__init__.py` files is out of the scope for this PR, I'm only trying to limit the amount of
> stuff that we add here.

## Example 11

**Issue:** Move private constant to constants.py, imported but not re-exported.

`app/core/audit/recorder.py`

```diff
+
+from sqlmodel.ext.asyncio.session import AsyncSession
+
+from app.core.audit.canonical import canonicalize
+from app.core.audit.context import AnonymousActor, current_audit_context
+from app.core.audit.events import AUDIT_EVENTS, BaseAuditEvent
+from app.core.audit.redaction import redact
+from app.lib.db import session_scope
+from app.models.audit import AuditEvent
+from app.models.base import utc_now
+
+_ANONYMOUS = AnonymousActor()
```

**Review:**

> lets put this in a file named `constants.py`, it would make things much easier to navigate.
>
> If this is a private constant to this module, we can put it in `constants.py` import it here just not re-export it
> via the public library so its never imported outside of this module.

## Example 12

**Issue:** Put NavItem and gatedNav.ts in a components/NavItem directory; move tests to a separate tests directory.

`frontend/components/NavItem/NavItem.tsx`

**Review:**

> Lets create a new directory for better codebase management. Lets put `NavItem` component in a `components/NavItem`
> directory and also move the related logic (`gatedNav.ts`) inside the directory.
> Furthermore, lets move the tests files into a separate tests directory just like we have for the backend

## Example 13

**Issue:** plugins.md documents generic plugin behaviour; chat-specific attachment info doesn't belong there.

`docs/guides/plugins.md`

```diff
@@ -532,6 +532,41 @@ If a builder cannot produce its block, it reports that by raising
 letting some other exception escape. A publishing tool catches it and reports the failure
 through its own error contract instead of letting it propagate unguarded.
 
+## Reacting to a deleted document
```

**Review:**

> The `plugins.md` documents the generic behaviour of plugins, since attachments are a feature related to a specific
> (`chat`) plugin, this might not be the best place to put this information.

## Example 14

**Issue:** Import intl-test-utils via the @/tests alias instead of a relative path.

`frontend/tests/app/dashboard/analytics/PeriodView.test.tsx`

```diff
@@ -0,0 +1,131 @@
+import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
+import { act, screen } from "@testing-library/react";
+import userEvent from "@testing-library/user-event";
+import { NextIntlClientProvider } from "next-intl";
+
+import en from "@/messages/en.json";
+import { renderWithIntl } from "../../../intl-test-utils";
```

**Review:**

> lets update this import to use `@/tests/intl-test-utils` instead of `../../../intl-test-utils`

## Example 15

**Issue:** Drive-specific analytics helpers shouldn't live in shared lib/analytics; plugin-specific code belongs with
its plugin.

`frontend/lib/analytics/drive.ts`

```diff
@@ -0,0 +1,33 @@
+import type { DriveDocumentsPoint } from "@/lib/analytics/types";
```

**Review:**

> Im not sure if lib/analytics is the right place for this file.
>
> In the backend all the plugins manage their analytics related functionality on their own.
> core related analytics can maybe go here (not even sure about that).
>
> Lets keep it here for now, this might get addressed in the new frontend epic I have opened
>
> let me kow about your thoughts on the matter, how should this code be managed.
>
> In my opinion lib/analytics should only have utils that are needed in other places, not something specific like
> google drive related functions

## Example 16

**Issue:** Don't import AuditEvent from core; expose it in sparkth/lib and import from there.

`sparkth/services/audit_log/service.py`

```diff
@@ -0,0 +1,51 @@
+"""Read access to the audit trail: filtered, paginated listing.
+
+Reads never touch the append-only guard, and listing is not itself recorded.
+"""
+
+from sqlmodel import col, select
+from sqlmodel.ext.asyncio.session import AsyncSession
+from sqlmodel.sql.expression import SelectOfScalar
+
+from sparkth.core.audit.models import AuditEvent
```

**Review:**

> lets avoid making imports directly from the core and use the `lib` for it.
> lets expose this model in `sparkth/lib` and import it from there

## Example 17

**Issue:** Split the growing reads file into schemas.py, enums.py and types.py, and drop the redundant 'reads' name.

`sparkth/core/analytics/schemas/reads.py`

```diff
@@ -70,3 +70,48 @@ class EventCatalogEntry(BaseModel):
 
     event_type: str
     fields: list[EventField]
+
+
+class Measure(StrEnum):
```

**Review:**

> alright this file is now growing a lot, we need to break this into `schemas.py` for pydantic models, `enums.py` for
> enums and `types.py` for python dataclasses.
>
> The name `reads` was already specific to the `analytics` module, so we can stop using it, the suggested names are
> already being used throughout the codebase

## Example 18

**Issue:** Imports private helpers from another module; move them here or make them public and documented.

`sparkth/core/analytics/explore.py`

```diff
+from sqlalchemy import ColumnClause, ColumnElement, func, literal_column, or_, select
+from sqlalchemy.ext.asyncio import AsyncSession
+
+from sparkth.core.analytics.catalog import catalog_entry
+from sparkth.core.analytics.exceptions import (
+    ExploreQueryError,
+    InvalidFilterValue,
+    UnknownExploreEvent,
+    UnknownExploreField,
+)
+from sparkth.core.analytics.models import raw_events
+from sparkth.core.analytics.reads import _PG_RAW_BUCKET, _SQLITE_BUCKET, _in_days
```

**Review:**

> these are private helpers being imported. Which means they are not private. Either move them to this file or make
> them public and document this properly

## Example 19

**Issue:** Convert api/v1/analytics.py into a module with routes/ and schemas.py, following v1/permissions, instead of
a separate analytics_views.py.

`sparkth/api/v1/analytics_views.py`

```diff
@@ -0,0 +1,128 @@
+"""Saved Explore views: each user's own, gated by ``analytics.read``. Another user's view is a 404."""
```

**Review:**

> Again here, this file is doing a lot of things.
>
> First, we already have a `analytics.py` in `api/v1`, if we need to add more analytics API endpoints, its better to
> convert the existing file into a module and add everything there.
>
> from the PR i understand that the API endpoint from the existing `analytics.py` file are added under `/analytics`
> endpoint, and the ones from this new file are to be added under `analytics/views` endpoint.
>
> The solution for that is simple, and is already being implemented in the `v1/permissions/` module.
>
> There should be an analytics module in `api/v1` at `api/v1/analytics`, the content of `v1/analytics.py` should be
> moved to `api/v1/analytics/routes/__init__.py` and the contents of this `analytics_views.py` should be moved to
> `api/v1/analytics/routes/views.py`. Both files can define their routers with the required endpoint prefixes.
>
> The pydantic model schemas should be moved to `api/v1/analytics/schemas.py`
>
> please look into the `v1/permissions/` module, this structure is already being followed there

## Example 20

**Issue:** Analytics nav is page structure; place it in analytics core components/layout and render it from app/.

`frontend/core/analytics/components/layout/AnalyticsNav.tsx`

```diff
@@ -1,10 +1,12 @@
 "use client";
```

**Review:**

> This file should really be in `frontend/core/analytics/components/layout/AnalyticsNav.tsx`, imported in the `app/`
> here and rendered.
>
> For content anything related to the structure of the page (core or plugin) should be added to `components/layout`,
> and the atomic components should be added in `components/ui`
>
> Since this is the navbar of the analytics page, it should be analytic's `components/layout`
