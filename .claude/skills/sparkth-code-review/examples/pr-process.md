# PR process & scope

Real review comments from Sparkth pull requests: PR size, stacking, descriptions, what belongs in the same PR.

## Example 1

**Issue:** Googledrive env was moved to plugin config elsewhere; a rebase reintroduced it into core config.

`app/core/config.py`

```diff
@@ -19,11 +19,8 @@ class Settings(BaseSettings):
     GOOGLE_CLIENT_SECRET: str = ""
     GOOGLE_AUTH_REDIRECT_URI: str = "http://localhost:7727/api/v1/auth/google/callback"
 
-    # Slack TA Bot OAuth
-    SLACK_CLIENT_ID: str = ""
-    SLACK_CLIENT_SECRET: str = ""
-    SLACK_SIGNING_SECRET: str = ""
-    SLACK_REDIRECT_URI: str = ""
+    # Google Drive OAuth (uses same client credentials, different redirect URI)
+    GOOGLE_DRIVE_REDIRECT_URI: str = "http://localhost:7727/api/v1/googledrive/oauth/callback"
```

**Review:**

> This googledrive specific env was moved to the app/core_plugins/googledrive/config.py in an earlier change.
>
> I believe a rebase put this back here, this should not be here

## Example 2

**Issue:** File duplicates another open PR; stack the PRs and rebase so only new changes show.

`sparkth/cli/audit_context.py`

```diff
@@ -0,0 +1,13 @@
+"""The audit context CLI commands run in, so their rows are attributed to the CLI."""
```

**Review:**

> This file is the same one which appears in the PR below this one.
>
> Lets stack all these PRs and rebase them so we only see the new changes

## Example 3

**Issue:** Builder signature change on public API should be called out in PR description and changelog as breaking.

`sparkth/lib/content/hooks.py`

```diff
+    Leave it ``None`` for a contributor that builds one kind of block; a publishing
+    tool then refuses any option id.
+
+    ``list_options`` and the builders must be module-level functions. Re-registering an equal
+    contributor is a no-op only if they compare equal across constructions, and a closure or
+    bound method would not.
     """
 
     name: str
     description: str
-    builders: Mapping[str, Callable[[str], Awaitable[ContentBlock]]]
+    builders: Mapping[str, Callable[[str, str | None], Awaitable[ContentBlock]]]
```

**Review:**

> the builder signature has been changed for the public API. even though nothing breaks today, it's better to mention
> the breaking change in the PR description and changelog.

## Example 4

**Issue:** Attach the relevant issue to the PR; otherwise good to go.

**Review:**

> Please attach the relevant issue to this PR, and the rest is good to go!

## Example 5

**Issue:** Docs should ship in the same PR as the code, per CLAUDE.md, so each PR is complete.

**Review:**

> moving forward, i think the docs should be updated in the same PR as the code. CLAUDE.md already says this, and it
> would also make each PR complete on its own.

## Example 6

**Issue:** Model field removed without a migration in this PR; keep model changes and migrations together.

`sparkth/plugins/chat/models.py`

```diff
@@ -35,8 +34,6 @@ class Conversation(TimestampedModel, SQLModel, table=True):
     provider: str = Field(max_length=50, nullable=False)
     model: str = Field(max_length=100, nullable=False)
     title: str | None = Field(default=None, max_length=255)
-    # Unused: no code reads or writes it.
-    responsibility: str | None = Field(default=None, max_length=CHAT_RESPONSIBILITY_NAME_MAX_LENGTH)
     total_tokens_used: int = Field(default=0)
```

**Review:**

> the field `responsibility` is removed but there's no migration for it.
>
> moving forward, i think we should keep the model changes (if any) and the accompanying migrations in the same PR.

## Example 7

**Issue:** PR only addresses the second point of the linked issue yet says it closes it; confirm the closing claim.

**Review:**

> This only addresses the second point in the latest comment of the linked issue, according to the description this
> does not close the first point, yet in the description it says that it closes the issue, can you please confirm this
>
> Other than that, the PR looks good to go

## Example 8

**Issue:** PR is too large; break it into 4-5 stacked PRs.

**Review:**

> lets avoid creating such huge PRs
> Please break this down into 4-5 stacked PRs

## Example 9

**Issue:** PR too big; split into stacked PRs of about 10 files, frontend and backend separate.

**Review:**

> this PR is a bit big to review in one go. moving forward we split longer PRs into stacked PRs with around 10 files
> each, and keep the frontend and backend in separate PRs.

## Example 10

**Issue:** List in the PR description which environment variables are added or updated.

**Review:**

> Lets also add in the PR description which environment variables needs to be added/updated with this PR
