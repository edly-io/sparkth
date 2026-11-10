# Configuration, dependencies & CI

Real review comments from Sparkth pull requests: settings, env vars, Makefile, Docker, CI.

## Example 1

**Issue:** Read OAuth bot scopes from an env variable so production can change them without a code push.

`app/core_plugins/slack/constants.py`

```diff
@@ -1,9 +1,20 @@
-import os
 import re
 
+# Slack OAuth endpoints
 SLACK_AUTHORIZE_URL = "https://slack.com/oauth/v2/authorize"
+SLACK_TOKEN_URL = "https://slack.com/api/oauth.v2.access"
+
+# Required OAuth scopes for the bot
+BOT_SCOPES = [
```

**Review:**

> Lets read the scopes from an env variable.
> If we ever want to update scope in production envieonment, we would not be able to do so without code push, reading
> from the env mitigates that.

## Example 2

**Issue:** Slack settings were required so missing values crash deployment; defaults to empty make failures lazy.

`app/core/config.py`

```diff
@@ -23,10 +23,10 @@ class Settings(BaseSettings):
     GOOGLE_DRIVE_REDIRECT_URI: str = "http://localhost:7727/api/v1/googledrive/oauth/callback"
 
     # Slack TA Bot OAuth
-    SLACK_CLIENT_ID: str
-    SLACK_CLIENT_SECRET: str
-    SLACK_SIGNING_SECRET: str
-    SLACK_REDIRECT_URI: str
+    SLACK_CLIENT_ID: str = ""
+    SLACK_CLIENT_SECRET: str = ""
+    SLACK_SIGNING_SECRET: str = ""
+    SLACK_REDIRECT_URI: str = ""
```

**Review:**

> I believe that we had these as required so that incase any of these is missed in a deployment (dev or prod), the
> deployment would crash instead of initially going up and then failing in a couple of usecases.
>
> Let me know if you have a better approach

## Example 3

**Issue:** Rename Makefile target, move gen:api into Makefile, add test.frontend.api, drop git diff CI job.

`Makefile`

```diff
@@ -79,6 +79,11 @@ frontend.install.dev: ## Install exact frontend dependencies from lockfile
 frontend.up.dev: ## Run frontend dev server (hot reload)
 	cd frontend && bun run dev
 
+.PHONY: gen.api
+gen.api: ## Regenerate frontend API types from the backend OpenAPI schema
+	uv run python scripts/dump_openapi.py > openapi.json
+	cd frontend && bun run gen:api
```

**Review:**

> I propose the following changes:
>
> 1. Rename the `gen.api` make target to `frontend.build.api`.
> 2. Move gen:api command to Makefile: `make frontend.build.api` with the `frontend.build` target depending on
> `frontend.build.api`. After all, we don't need package.json scripts if we have a Makefile, and make handles
> dependencies better than package.json.
> 3. Introduce a `make test.frontend.api`: which will run `openapi-typescript --check`. Have `test.frontend` depend on
> `test.frontend.api`.
> 4. Remove the awkward `git diff` test from CI: instead, API checks will be performed as part of `test.backend`. That
> way we don't have to introduce a new CI job.

## Example 4

**Issue:** Add scripts/ to directories checked by make mypy in this PR.

`scripts/e2e_init_db.py`

```diff
@@ -16,7 +16,7 @@
 from sqlalchemy.ext.asyncio import AsyncEngine
 from sqlmodel import SQLModel
 
-from app.core.db import async_engine
+from app.core.db import dispose_engine, get_engine
```

**Review:**

> What this tells us is that we should really run mypy on the scripts/ directory. Can you use this PR to add scripts/
> to the list of directories processed by `make mypy`?

## Example 5

**Issue:** CI did not run because PR targets a non-main base; suggests running CI on all PRs.

**Review:**

> How come CI did not run on this PR? We shouldn't merge until we have a greenlight from mypy, unit tests, etc.
>
> EDIT: that's because this PR is not running on top of "main". Should we run CI for all PRs instead of just those
> that target the "main" branch?

## Example 6

**Issue:** Run the pg tests on every CI run; path-filter change list is fragile and tests are cheap.

`.github/workflows/ci.yml`

```diff
+      changed: ${{ steps.filter.outputs.changed }}
+    steps:
+      - uses: actions/checkout@v6
+        with:
+          persist-credentials: false
+      - uses: dorny/paths-filter@v3
+        id: filter
+        with:
+          # Run when the analytics read/maintenance code, the analytics migrations, or the
+          # pg lane itself change — NOT merely when a pg test is added — so a migration that
+          # breaks the continuous aggregate is caught even in a migration-only PR.
+          filters: |
```

**Review:**

> I think we should just run tests all the time: they don't cost much in terms of time spent and the `changed` list is
> fragile.

## Example 7

**Issue:** Do not auto-run migrations on start; document in README and simplify the three migration commands.

`docker-compose.prod.yml`

```diff
+    stop_grace_period: 30s
+    depends_on:
+      migrations:
+        condition: service_completed_successfully
+      db:
+        condition: service_healthy
+      redis:
+        condition: service_healthy
+
+  # Applies both Alembic lineages, then backfills TimescaleDB continuous
+  # aggregates (idempotent). The app starts only after this succeeds.
+  migrations:
```

**Review:**

> Let's not run migrations automatically on every application start. Instead, add instructions in the README that
> explain how to run migrations. The fact that we need to run 3 different commands should tell us that we need to
> simplify the way we run migrations...

## Example 8

**Issue:** Do not set an alias for the old key name; update env vars on deploy so the app fails loudly.

`sparkth/core/config.py`

```diff
@@ -106,7 +106,9 @@ class Settings(BaseSettings):
 
     MEMORY_PROFILING_ENABLED: bool = False
 
-    LLM_ENCRYPTION_KEY: str
+    # Encrypts stored AI keys. Read from LLM_ENCRYPTION_KEY when ENCRYPTION_KEY is unset, the name it had before.
+    # The pydantic mypy plugin rejects any required field with alias choices; settings resolve them at runtime.
+    ENCRYPTION_KEY: str = Field(validation_alias=AliasChoices("ENCRYPTION_KEY", "LLM_ENCRYPTION_KEY"))  # type: ignore[pydantic-alias]
```

**Review:**

> lets not set an alias here, this would cause confusions later on.
> Its better to update the environment variables when this PR is deployed.
>
> By not keeping the alias, the app would crash which is better than someone being confused by the name difference
> later on
