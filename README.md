# Sparkth

Sparkth is a free, open source, extensible, science-driven, AI-first learning platform. It is under active development by
[Edly](https://edly.io).

## Public Endpoints

Sparkth is hosted at [https://sparkth.edly.space](https://sparkth.edly.space) with the following endpoints:

| Endpoint | URL |
| -------- | --- |
| MCP Server | https://sparkth.edly.space/ai/mcp |
| REST API | https://sparkth.edly.space/api/ |
| Swagger UI | https://sparkth.edly.space/docs |
| ReDoc | https://sparkth.edly.space/redoc |

## Guides
- [Backend Plugin Implementation](./sparkth/core/plugins/PLUGIN_GUIDE.md)
- [Frontend Plugin Implementation](./frontend/README.md)

## Development

### Prerequisites

- Python 3.14
- [uv](https://docs.astral.sh/uv/)
- [bun](https://bun.sh/)

### Setup

1. Clone the repository:
   ```bash
   git clone https://github.com/edly-io/sparkth.git
   cd sparkth
   ```

2. Install backend and frontend dependencies:
   ```bash
   make backend.install.dev
   make frontend.install.dev
   ```

3. Install git hooks:
   ```bash
   make backend.install.dev.githooks
   ```

### Running the app

Start dependent services:

    make services.up

Apply migrations:

    make migrations

Start backend service:

    make backend.up.dev

In a separate terminal, start the frontend service (with hot-reload):

    make frontend.up.dev

Access the app at http://localhost:3000.

`.env` is committed with working dev defaults and works out of the box.
For sensitive credentials (Google OAuth, Slack), create a `.env.local` file — see the comments inside `.env` for the variables to add there. `.env.local` takes precedence over `.env`.


### End-to-end tests

Playwright end-to-end tests live in `frontend/tests/`. They run against their own
ephemeral SQLite database, created fresh and deleted on every run, so they never
touch your dev Postgres data. The run starts and stops a throwaway backend (on
port 7727) and the frontend for you.

Install the browsers once:

    make test.e2e.install

Then, with the backing services up (`make services.up`, for Mailpit and Redis)
and your dev backend stopped (the run owns port 7727):

    make test.e2e            # headless
    make test.e2e.ui         # interactive UI mode

### Local MCP Endpoint

The MCP server is served over HTTP by the running backend. When running the API server
locally, it is available at:

```
http://127.0.0.1:7727/ai/mcp
```

This allows Claude and other MCP-compatible clients to connect to the MCP server via HTTP.

### API Documentation

Once the server is running, you can access the interactive API documentation locally:

* **Swagger UI:** [http://127.0.0.1:7727/docs](http://127.0.0.1:7727/docs)
    * *Best for testing endpoints interactively.*
* **ReDoc:** [http://127.0.0.1:7727/redoc](http://127.0.0.1:7727/redoc)
    * *Best for reading documentation structure.*

### Integrating with Claude Desktop

The Sparkth MCP server is served over HTTP by the running backend at `/ai/mcp`
(e.g. `http://127.0.0.1:7727/ai/mcp`). Start the backend first (`make backend.up.dev`),
then bridge Claude Desktop to it with [`mcp-remote`](https://www.npmjs.com/package/mcp-remote).

Edit the Claude configuration file:

```
# macOS
~/Library/Application\ Support/Claude/claude_desktop_config.json
# Windows
%APPDATA%\Claude\claude_desktop_config.json
# Linux
~/.config/Claude/claude_desktop_config.json
```

Add the Sparkth MCP server configuration:
```json
{
  "mcpServers": {
    "Sparkth": {
      "command": "npx",
      "args": [
        "mcp-remote",
        "http://127.0.0.1:7727/ai/mcp"
      ]
    }
  }
}
```

> Note: You may need to put the full path to the `npx` executable in the command field. You can get this by running `which npx` on macOS/Linux or `where npx` on Windows.

Restart Claude Desktop. Ensure that the "Sparkth" tools appear in the "Search and tools" menu. Then start a new chat and generate a course:

> Use Sparkth to generate a very short course (~1 hour) on the literary merits of Hamlet, by Shakespeare.

Sparkth will generate a prompt that will help Claude generate this course.

## Production

Build the Docker image:

```bash
make docker.build
```

Convert the development services from docker-compose.yml to a production setup and add the Sparkth application to the list of services:

    sparkth:
        image: ghcr.io/edly-io/sparkth:latest
        restart: unless-stopped
        env_file:
            - .env
            - .env.local
        depends_on:
            db:
                condition: service_healthy
            redis:
                condition: service_healthy

## Configuration

### Feature flags

The application is configured via environment variables that are defined in the `.env` file. This file contains values that are suitable for development. In production, create a `.env.local` file to override these values.

Make sure to restart the backend (`make backend.up.dev`) after changing the configuration to apply the new settings.

#### `REGISTRATION_ENABLED`

- Type: `boolean (true / false)`
- Default: `false`

Controls whether new user registration is enabled on the frontend.

- If `REGISTRATION_ENABLED=true`, users can sign up via the frontend.
- If `REGISTRATION_ENABLED=false`, the registration form is disabled, preventing new user creation.

Note that changing this flag does not affect existing users.

### User Management

Create a new user account:


    make create-user -- --username john --email john@example.com --name "John Doe"
    # Using short flags
    make create-user -- -u john -e john@example.com -n "John Doe"

If password is not provided via flag, you'll be prompted to enter it securely.

Create an admin user — grants the global `admin` role (run `make migrations` first so the role is seeded):

    make create-user -- --username admin --email admin@example.com --name "Admin User" --admin

Provide password directly:

    make create-user -- -u john -e john@example.com -n "John Doe" --password "SecurePass123"

Options:

- `--username, -u`: Username (required)
- `--email, -e`: Email address (required)
- `--name, -n`: Full name (optional, defaults to the username)
- `--password, -p`: Password (optional, will prompt if not provided)
- `--email-verified`: mark the user's email as already verified (optional, default: false)
- `--admin` (alias `--superuser`): also grant the user the global `admin` role (optional, default: false). The `admin` role must already be seeded (via `make migrations`), or the command exits without creating the user.

Reset a user's password (the user is given as a positional username **or** email):

    make reset-password -- john
    # Provide password directly
    make reset-password -- john --new-password "NewSecurePass123"
    make reset-password -- john -p "NewSecurePass123"

Options:

- `identifier`: Username or email of the user (required, positional)
- `--new-password, -p`: New password (optional, will prompt if not provided)

## Permission Management System

Sparkth authorizes actions with a scoped role-based access control (RBAC) model. Authorization data lives in three tables:

- **`role`** — a named role (e.g. `admin`).
- **`role_permission`** — the permissions a role grants. A permission is a free-form dotted string (e.g. `assignment.grade`); a role grants many.
- **`role_assignment`** — grants a role to a user at a single scope.

A user is authorized when they hold, through an active `role_assignment` at the relevant scope, a role whose `role_permission` rows include the permission. `can()` resolves exactly this against the three tables — it is the single authorization check.

### Permissions and scopes are declared in code

The vocabulary the system draws on — which permission strings and which scope kinds exist — is declared in application code, not kept in a catalogue table.

- **Permissions** are declared with `Permission.create("assignment.grade")`, which registers the permission on the **`PERMISSIONS`** hook. Core permissions are declared this way in `sparkth.core.permissions`; plugins declare their own from their `__init__`. The hook is the single source of truth — nothing is copied into a separate store.
- **Scope kinds** are declared with `PermissionScope.create("course", parent=...)`, which registers the scope on the **`PERMISSION_SCOPES`** hook. The root `global` scope is declared this way in `sparkth.core.permissions.scopes`; plugins declare their own from their `__init__`. As with permissions, the hook is the single source of truth — nothing is copied into a separate store.

Each hook is a `SingleNamedItemHook` keyed by name: declaring two permissions or two scope kinds with the same name **raises `ValueError`**, so a collision fails fast at import time instead of being silently ignored.

> **Always declare permissions and scope kinds via `Permission.create()` / `PermissionScope.create()`, never the bare constructors.** Only `.create()` registers the object on its hook — the source of truth — which is also what makes a duplicate name fail fast. Bind each declaration to a constant and reference that one instance wherever the permission or scope is used (e.g. `EMAIL_WHITELIST_READ`, `GLOBAL`). The bare `Permission(name)` / `PermissionScope(name)` constructors are **internal/test-only**; see [The `Permission` class](#the-permission-class) and [The `PermissionScope` class](#the-permissionscope-class) below for exactly what they skip and why it matters.

The hooks *are* the catalogue: resolve a name to its registered object with
`get_permission(name)` / `get_permission_scope(name)` (they return the
`Permission` / `PermissionScope`, raising `PermissionNotFound` / `PermissionScopeNotFound`
on a miss). There is no separate storage, no singleton, and no startup priming step — so
extending the vocabulary needs no schema change; the tables above stay the system of record
for what is actually *granted* and *assigned*.

### The `Permission` class

A `Permission` is a named unit of authorization — the right to perform one action, written as a dotted string such as `assignment.grade`. A role grants a set of permissions (one `role_permission` row each); `can()` authorizes a request when the user holds, at the relevant scope, a role whose permissions include the one being checked. Import it from `sparkth.lib.permissions` (never from `sparkth.core.permissions`):

```python
from sparkth.lib.permissions import Permission
```

**State** — a permission carries one field, `name: str` (the dotted string). It defines no custom `__eq__`, so two `Permission` objects are equal only when they are the *same* object — equality is identity, not name.

**`Permission.create(name)`** — the way to declare one. It constructs the permission, **registers it on the `PERMISSIONS` hook** (the single source of truth for the permission vocabulary), and returns it. Registration is what makes collisions fail fast: declaring two permissions with the same name **raises `ValueError`** at import time. Declare core permissions in `sparkth.core.permissions`; a plugin declares its own from its `__init__`. Bind the result to a constant and reference that instance everywhere:

```python
COURSE_GRADE = Permission.create("course.grade")
```

**`Permission(name)` vs `.create(name)`** — the bare constructor only sets `name`; it does **not** register on the hook, and is internal/test-only. The practical difference is narrow for permissions: `can()` matches the `.name` *string* against the `role_permission` table and never resolves the `Permission` object from the hook, so a bare-constructed permission with a correct name still authorizes. What you lose by skipping `.create()` is catalogue membership and duplicate detection — and, because matching is by string, a misspelled name fails silently however the object was built (it simply matches no granted permission, so the check denies). Declaring once via `.create()` and referencing that one instance is what keeps names from drifting. The shipped permissions are listed under [Shipped with the app](#shipped-with-the-app).

### The `PermissionScope` class

A `PermissionScope` is a named **kind** of boundary a role can be assigned at — `global`, `course`, `quiz`, and so on. It answers *where* a role applies; how a scope kind maps onto the `scope` / `scope_object_id` columns of `role_assignment` is covered under [Scopes](#scopes). Import the classes from `sparkth.lib.permissions.scopes`:

```python
from sparkth.lib.permissions.scopes import GLOBAL, ObjectlessPermissionScope, PermissionScope
```

`PermissionScope` is the scope for an **object-bearing** kind — the common case (e.g. `course`, `quiz` — many instances, each identified by a `scope_object_id`). The rarer singleton that names no object (`global`, `whitelist`) is **`ObjectlessPermissionScope`**, a subclass that overrides the object-id rules, the route wiring, and how the scope cascades. The kind — not a boolean flag — decides those; each is a method (`validate_object_id`, `validate_scope_param`, and the cascade contribution behind `scope_chain`).

**State** — two fields:

| Attribute | Type | Meaning |
|---|---|---|
| `name` | `str` | The scope kind's identifier (e.g. `course`); stored verbatim in `role_assignment.scope`. |
| `parent` | `PermissionScope \| None` | The enclosing scope kind, or `None` for a root. Scope kinds chain from a narrow boundary up to a broader one. |

As with `Permission`, there is no custom `__eq__` — equality is identity.

**`get_parents() -> list[PermissionScope]`** — returns this scope's ancestors nearest-first (`[parent, grandparent, …]`) by walking `parent` pointers, ending at the root (an empty list for a root scope). `can()` and `has_role()` use it (through `scope_chain`) to cascade a grant **parent → child**: a grant at an `ObjectlessPermissionScope` ancestor (`global`, `whitelist`) satisfies a check at any descendant, because such an ancestor names no object (its `scope_object_id` is always `NULL`) and needs no per-object resolution. Object-bearing multi-level cascade (e.g. a grant at one `org` applying automatically to its `course`s) still needs a materialized path to resolve which descendant objects belong to which ancestor object, and remains deferred (issue #420 Phase 2).

**`PermissionScope.create(name, parent=None)` / `ObjectlessPermissionScope.create(name, parent=None)`** — the way to declare a scope kind. It constructs the scope, **registers it on the `PERMISSION_SCOPES` hook**, and returns it; a duplicate name **raises `ValueError`**, and a `parent` must already be registered (the `global` root always is). Use `PermissionScope` for an object-bearing kind like `course` (the common case) and `ObjectlessPermissionScope` for a singleton that names no object (e.g. `global`, `whitelist`). Declare core scopes in `sparkth.core.permissions.scopes`; a plugin declares its own from its `__init__`:

```python
COURSE = PermissionScope.create("course", parent=GLOBAL)
```

**`PermissionScope(name)` / `ObjectlessPermissionScope(name)` vs `.create(name)`** — the bare constructor is internal/test-only and does not register. For scopes this difference is **not** cosmetic: a scope kind is resolved back from its name through `get_permission_scope(name)` — which the CLI uses to validate `--scope`. A bare-constructed scope is absent from the hook, so resolving it by name raises `PermissionScopeNotFound` — exactly the no-op `--scope` assignment the CLI now rejects. Always declare via `.create()` and reference the returned instance (`GLOBAL`, your `COURSE`, …). The shipped root scope is exported as `GLOBAL`; see [Shipped with the app](#shipped-with-the-app).

### Scopes

A scope answers *where* a role applies. It is the pair of two columns on `role_assignment`:

- **`scope`** — the *kind* of boundary (e.g. `global`, `course`, `quiz`), one of the kinds declared through the `PERMISSION_SCOPES` hook. It is a free-form string, not a foreign key.
- **`scope_object_id`** — *which* specific entity of that kind (e.g. the id of one course). It is polymorphic — it points at whatever domain table the scope kind maps to, so it is deliberately **not** a foreign key.

> **Scope is *where*, not *what* — it is not a power level.** Authorization is purely permission-based: `can()` authorizes a request only when the user's role actually contains the checked permission. Assigning a role at the `global` scope grants **only** the permissions that role holds, applied platform-wide — it is **not** an admin or superuser tier and confers no permission the role lacks. So a "Role Manager" role holding only `role.*` (plus `permission.read`) assigned at `global` can manage *every* role yet has no other access (e.g. none to the whitelist). The `admin` role is far-reaching because of the permissions it *bundles*, not the scope it is assigned at; there is no superuser bypass (`is_superuser` was removed).

A scope kind may name a parent (`PermissionScope.create(name, parent=…)`), so kinds form a hierarchy from a narrow boundary up to a broader one, and every scope kind is either a **`PermissionScope`** — which names one object of its kind — or an **`ObjectlessPermissionScope`**, a singleton with no object to name, so its `role_assignment` rows carry `scope_object_id = NULL`. The `global` scope is the objectless root: it applies everywhere. `whitelist` is a second `ObjectlessPermissionScope`, nested under `global`, for the singleton registration-whitelist feature. `role` is an object-bearing `PermissionScope`, also nested under `global`, that names one role by id so role management can be delegated per-role (see [Shipped with the app](#shipped-with-the-app)).

Every `ObjectlessPermissionScope` requires `scope_object_id` to be `NULL`; every `PermissionScope` (e.g. `course`) requires a non-`NULL` `scope_object_id`. This pairing is enforced in application code — `assign_role` calls the scope's `validate_object_id`, which raises `InvalidScopeObjectId` on a mismatch — **not** a database `CHECK` constraint, so the database stays ignorant of the scope vocabulary declared via `PERMISSION_SCOPES`.

`can()` and `has_role()` cascade a grant **parent → child**: a grant at an `ObjectlessPermissionScope` ancestor (`global`, `whitelist`) satisfies a check at any of its descendants, because such an ancestor names no object (its `scope_object_id` is always `NULL`) and needs no per-object resolution. A `global` grant therefore satisfies a `role`-scoped check for any role. Object-bearing (`PermissionScope`) multi-level cascade (e.g. a grant at one `org` applying automatically to its `course`s) still needs a materialized path and remains deferred (issue #420 Phase 2).

#### Shipped with the app

| Kind | Names | Notes |
|---|---|---|
| **Scopes** | `global`, `whitelist`, `role` | `global` is the root scope; applies platform-wide; objectless, so `scope_object_id` is `NULL`. `whitelist` is an objectless singleton container scope nested under `global`; a role assigned here manages the whole registration whitelist without a global grant; `scope_object_id` is also `NULL`. `role` is an **object-bearing** scope nested under `global`; a role assigned here manages one specific role (its `scope_object_id` is that role's id), so role management can be delegated per-role without a global grant. A `global` grant cascades down to both. |
| **Permissions** | `email.whitelist.read`, `email.whitelist.create`, `email.whitelist.delete`; `role.create`, `role.read`, `role.update`, `role.delete`; `permission.read` | The `email.whitelist.*` permissions gate the registration email-whitelist endpoints (at the `whitelist` scope); the `role.*` permissions gate the role-management API — the endpoints addressing one role by id gate at the `role` scope (delegable per-role), while listing all roles and creating a role stay global — and `permission.read` gates listing the assignable permission vocabulary (see [Managing roles at runtime](#managing-roles-at-runtime)). |
| **Roles** | `admin` | Grants the three `email.whitelist.*`, the four `role.*`, and the `permission.read` permissions. The seed migration also assigns it at the `global` scope to every account that was a superuser when the migration ran — a one-time backfill, not an ongoing rule. |

### Managing roles at runtime

Roles and their permission grants are managed at runtime through the role-management REST API under `/api/v1/permissions`, gated by the `role.*` and `permission.read` permissions. The endpoints that address one role by `{role_id}` authorize at the `role` scope keyed by that id, so management of a single role can be delegated; the rest (listing all roles, creating a role, and reading the permission vocabulary) stay at the `global` scope. A `global` grant satisfies the per-role checks via the scope cascade, so existing global admins keep full authority. Permissions and scope kinds themselves are **not** editable here — they are declared in code (platform defaults or plugin hooks); this API only grants already-declared permissions to roles.

| Method & path | Permission | Scope | Purpose |
|---|---|---|---|
| `GET /permissions` | `permission.read` | `global` | List the permission strings assignable to a role. |
| `GET /permissions/roles` | `role.read` | `global` | List every role with its permission grants. |
| `POST /permissions/roles` | `role.create` | `global` | Create a role (`409` if the name is taken). |
| `GET /permissions/roles/{role_id}` | `role.read` | `role` | Fetch one role (`404` if missing). |
| `PATCH /permissions/roles/{role_id}` | `role.update` | `role` | Rename or re-describe a role (`404` missing, `409` name taken). |
| `DELETE /permissions/roles/{role_id}` | `role.delete` | `role` | Delete a role (`409` while it still has an active assignment). |
| `POST /permissions/roles/{role_id}/permissions` | `role.update` | `role` | Grant a registered permission to a role (`422` if the permission is not registered). |
| `DELETE /permissions/roles/{role_id}/permissions/{permission}` | `role.update` | `role` | Revoke a permission from a role. |

Grants and revokes are idempotent. Assigning a role to a *user* is a separate concern handled by `assign_role` / the CLI (see [Assign a role to a user](#extending-the-permission-system)), not by this API.

> **Accepted limitation.** A per-role manager holding `role.update` on a role can grant that role **any** registered permission — the same capability a global `role.update` holder already has; per-role delegation narrows *who* holds it, not *what* it can grant. Restricting the grantable permission set is out of scope (a separate concern).

### Extending the permission system

**Declare a permission or scope kind** — a plugin declares its own from its `__init__`, exactly as it registers tools or config. Core declarations (not tied to any plugin) live in `sparkth.core.permissions` (permissions) and `sparkth.core.permissions.scopes` (scope kinds). Import everything you need from `sparkth.lib.permissions` (the `PermissionScope` class and the `GLOBAL` scope come from its `sparkth.lib.permissions.scopes` submodule) — never from `sparkth.core` or the hook modules directly.

```python
from sparkth.lib.permissions import Permission
from sparkth.lib.permissions.scopes import GLOBAL, PermissionScope
from sparkth.lib.plugins import SparkthPlugin

class GraderPlugin(SparkthPlugin):
    def __init__(self, name: str) -> None:
        super().__init__(name)
        Permission.create("assignment.grade")
        # a scope kind's parent must already be registered (the global root always is)
        PermissionScope.create("course", parent=GLOBAL)
```

A `role_assignment` whose `scope` names a declared kind then sets `scope_object_id` to the id of one such entity (e.g. `scope = 'course'` with `scope_object_id` a course's id).

**Add a role and its permissions** — seed them in a migration:

```sql
INSERT INTO role (name, description, created_at, updated_at)
VALUES ('grader', 'Grades submissions', now(), now());
INSERT INTO role_permission (role_id, permission, created_at, updated_at)
VALUES ((SELECT id FROM role WHERE name = 'grader'), 'assignment.grade', now(), now());
```

**Assign a role to a user** — for bootstrapping, use the CLI (it looks the user up by username or email):

```bash
# assign at the global scope
make cli -- roles assign-role john admin
# or at another objectless scope — no --scope-object-id, same as global
make cli -- roles assign-role jane "Whitelist Manager" --scope whitelist
# or scoped to one object — pass the scope kind and the object id
make cli -- roles assign-role john grader --scope course --scope-object-id 42
# delegate management of just one role — the object id is that role's id
make cli -- roles assign-role alice role-manager --scope role --scope-object-id 5
```

`--scope` must name a declared scope kind (`global`, or any added via `PermissionScope.create()` / `ObjectlessPermissionScope.create()`); an unknown kind is rejected rather than persisted as a no-op assignment. Whether `--scope-object-id` is required depends on the scope kind: an `ObjectlessPermissionScope` (`global`, `whitelist`) must be assigned *without* one; a `PermissionScope` (like `course`) must be assigned *with* one. The CLI defers this check to `assign_role`, which raises `InvalidScopeObjectId` on a mismatch and exits non-zero with a clean error rather than persisting a contradictory row.

From application code, call `assign_role`:

```python
from sparkth.lib.permissions import assign_role
from sparkth.lib.permissions.scopes import GLOBAL

# Pass a declared PermissionScope instance (GLOBAL is the shipped root; COURSE is your
# PermissionScope.create("course", …) result). The platform-wide GLOBAL scope names
# no object, so scope_object_id is None:
await assign_role(user_id, "grader", GLOBAL, None, session)
# Scoped to one course:
await assign_role(user_id, "grader", COURSE, "42", session)
```

**Gate an endpoint on a permission** — call `.require_in_global_scope()` or
`.require(scope, scope_param=None)` on the permission itself. `scope` is a declared
`PermissionScope` **object** (e.g. `GLOBAL`, `WHITELIST`, your `COURSE`), not its name — pass the
registered instance. `scope_param` names the path parameter that carries the scope object id; it is
**optional** — omit it for an objectless scope (e.g. `require(WHITELIST)`), and supply it for an
object-bearing one (e.g. `require(COURSE, "course_id")`). Supplying `scope_param` for an objectless
scope, or omitting it for an object-bearing one, is a wiring error and **raises `ValueError`** at
definition time:

```python
from fastapi import Depends

# Import your declared permission instances (don't reconstruct them) from the module that owns
# them — sparkth.lib.permissions for the platform's shipped permissions, or your plugin's module for
# ones the plugin declares. EMAIL_WHITELIST_READ, THING_READ, THING_CREATE and COURSE_EDIT are
# Permission.create(...) results.
from sparkth.lib.permissions import COURSE_EDIT, EMAIL_WHITELIST_READ, THING_CREATE, THING_READ

# Scope objects come from sparkth.lib.permissions.scopes (WHITELIST is shipped; COURSE is illustrative).
from sparkth.lib.permissions.scopes import COURSE, WHITELIST

# Global scope, as a route dependency:
@router.get("/things", dependencies=[Depends(THING_READ.require_in_global_scope())])
async def list_things(): ...

# Global scope, injected so the route can use the authorized user:
async def create_thing(user: User = Depends(THING_CREATE.require_in_global_scope())): ...

# Objectless scope check — WHITELIST is a singleton, so there is no object id to read from the
# URL and no scope_param to pass:
@router.get("/whitelist", dependencies=[Depends(EMAIL_WHITELIST_READ.require(WHITELIST))])
async def list_whitelist(): ...

# Scoped check — pass the scope's PermissionScope object and the path parameter that carries the
# object id; the id is read from the URL on each request:
@router.patch(
    "/courses/{course_id}",
    dependencies=[Depends(COURSE_EDIT.require(COURSE, "course_id"))],  # reads {course_id}
)
async def edit_course(course_id: int): ...
```

The returned dependency resolves the current user, checks the permission, and returns the
authenticated `User`. Put it in `dependencies=[...]` to gate a route; inject it as a parameter
(`user: User = Depends(...)`) only when the handler needs the authorized user — both forms enforce
the permission identically. Behavior:

| Scenario | Trigger | Result |
|---|---|---|
| Authorized | The user holds the permission at that scope | The route runs; the dependency returns the `User`. |
| Not granted | The user lacks the permission at that scope | **403** `Permission denied`. |
| Objectless/object-bearing mismatch | `require(WHITELIST, "some_param")` (a `scope_param` given for an objectless scope) or `require(COURSE)` (no `scope_param` for an object-bearing scope) | `ValueError` is raised **at definition time** (when `.require(...)` is called, i.e. when the route module is imported) — a wiring error, never a silent 403. |
| Misconfigured path param | `require(COURSE, "course_id")` on a route whose path has no `{course_id}` | The dependency raises a plain exception, which FastAPI turns into a **500** (`Permission scope is misconfigured` is logged server-side, not returned to the client) — surfaced as a server error, not a silent 403. |

`require_in_global_scope()` uses the shipped `GLOBAL` scope and names no path parameter — it
calls `_require_permission` directly rather than going through `require()`'s scope-name and
`scope_param` checks — so it can never hit the last three rows.

## Audit Trail

Sparkth keeps an append-only audit trail of security-relevant and AI actions: who did what, when,
from where, and with what effect. The implementation lives in `sparkth/core/audit/` with its public
API in `sparkth/lib/audit/`; unlike analytics (best-effort), audit writes are fail-closed, so a
mutating or AI action whose audit record cannot be written does not proceed.

## Analytics Event Schemas

Analytics events are validated against **versioned schemas** before they are stored. Each
schema is a self-describing `AnalyticsEventSchema` subclass that declares its own
`event_type` string and integer `version`, and is registered on the **`ANALYTICS_EVENTS`**
hook — the single source of truth the emission gateway resolves against. This mirrors the
permission vocabulary above: declare in code at import time, no separate store and no startup
drain. Import everything from `sparkth.lib.analytics`, never from `sparkth.core.analytics.*` directly.

### Declaring an event schema

Core events are declared in `sparkth.core.analytics`; a plugin declares its own from its
`__init__` with `register_event_schema(self, MyEvent)` — the analytics analog of
`Permission.create()`.

```python
from sparkth.lib.analytics import AnalyticsEventSchema, register_event_schema

class CourseCompleted(AnalyticsEventSchema):
    event_type = "mycourseplugin.course_completed"  # namespaced under the plugin name
    version = 1

    learner_id: str
    course_id: str

# from the plugin's __init__:
register_event_schema(self, CourseCompleted)
```

`register_event_schema` enforces three guards at import time, so a misconfigured plugin fails
fast at startup instead of at first emit:

- **Namespace** — `event_type` must be prefixed with the plugin's name, else
  `EventNamespaceError`. This stops a plugin from squatting a core event name or another
  plugin's namespace.
- **Collision** — any class claiming an already-registered `(event_type, version)` raises
  `DuplicateEventTypeError`. Registration is not idempotent: re-registering the *same* class
  is fatal too.
- **Identity** — a schema missing `event_type`/`version` raises `TypeError`.

> Always declare via `register_event_schema`, not by calling `ANALYTICS_EVENTS.add_item`
> directly — the registration function is what applies the namespace guard. Core events (which
> carry no plugin prefix) are seeded directly in `sparkth.core.analytics`.

### Emitting an event

All events are emitted server-side through `ingest_event`, which resolves the schema by
`(event_type, version)`, validates the payload against it, and lands one immutable row in the
analytics database:

```python
from sparkth.lib.analytics import ingest_event

await ingest_event(
    session, "mycourseplugin.course_completed", 1,
    {"learner_id": "u1", "course_id": "c1"}, actor_id=str(user.id),
)
```

Resolve a registered schema by identity with `get_event_schema(event_type, version)` (raises
`UnknownEventTypeError` if none is registered).

## Contributing

Contributions are welcome. Open a pull request against `main` and a maintainer will take a look.

### Requesting an automated code review

This repository has an automated code review powered by Claude. To request a review on your pull request, post a comment containing `@claude-review` on the PR. The workflow runs on demand only (it does not run automatically on every push), so use the mention whenever you want a fresh pass, for example after pushing new commits.

## License

This project is licensed under the MIT License — see the [LICENSE](LICENSE) file for details.
