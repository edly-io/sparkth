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
- [Backend Plugin Implementation](./app/plugins/PLUGIN_GUIDE.md)
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

- **Permissions** are declared with `Permission.create("assignment.grade")`, which registers the permission on the **`PERMISSIONS`** hook. Core permissions are declared this way in `app.core.permissions`; plugins declare their own from their `__init__`. The hook is the single source of truth — nothing seeds permissions into the registry separately.
- **Scope kinds** are declared with `PermissionScope.create("course", parent=...)`, which registers the scope on the **`PERMISSION_SCOPES`** hook. The root `global` scope is declared this way in `app.core.permissions.scopes`; plugins declare their own from their `__init__`. As with permissions, the hook is the single source of truth — nothing seeds scopes into the registry separately.

Each hook is a `SingleNamedItemHook` keyed by name: declaring two permissions or two scope kinds with the same name **raises `ValueError`**, so a collision fails fast at import time instead of being silently ignored.

> **Always declare permissions and scope kinds via `Permission.create()` / `PermissionScope.create()`, never the bare constructors.** Only `.create()` registers the object on its hook — the source of truth — which is also what makes a duplicate name fail fast. Bind each declaration to a constant and reference that one instance wherever the permission or scope is used (e.g. `EMAIL_WHITELIST_READ`, `GLOBAL`). The bare `Permission(name)` / `PermissionScope(name)` constructors are **internal/test-only**; see [The `Permission` class](#the-permission-class) and [The `PermissionScope` class](#the-permissionscope-class) below for exactly what they skip and why it matters.

At startup the app reads both hooks into two singleton registries — `PermissionsRegistry` (a flat list of permission names) and `PermissionScopesRegistry` (a name-indexed tree of scope kinds, where a scope's parent must already be registered). They are the in-memory catalogue of the declared vocabulary, so extending it needs no schema change; the tables above stay the system of record for what is actually *granted* and *assigned*.

### The `Permission` class

A `Permission` is a named unit of authorization — the right to perform one action, written as a dotted string such as `assignment.grade`. A role grants a set of permissions (one `role_permission` row each); `can()` authorizes a request when the user holds, at the relevant scope, a role whose permissions include the one being checked. Import it from `app.lib.permissions` (never from `app.core.permissions`):

```python
from app.lib.permissions import Permission
```

**State** — a permission carries one field, `name: str` (the dotted string). It defines no custom `__eq__`, so two `Permission` objects are equal only when they are the *same* object — equality is identity, not name.

**`Permission.create(name)`** — the way to declare one. It constructs the permission, **registers it on the `PERMISSIONS` hook** (the single source of truth for the permission vocabulary), and returns it. Registration is what makes collisions fail fast: declaring two permissions with the same name **raises `ValueError`** at import time. Declare core permissions in `app.core.permissions`; a plugin declares its own from its `__init__`. Bind the result to a constant and reference that instance everywhere:

```python
COURSE_GRADE = Permission.create("course.grade")
```

**`Permission(name)` vs `.create(name)`** — the bare constructor only sets `name`; it does **not** register on the hook, and is internal/test-only. The practical difference is narrow for permissions: `can()` matches the `.name` *string* against the `role_permission` table and never consults `PermissionsRegistry` (nothing reads that registry today), so a bare-constructed permission with a correct name still authorizes. What you lose by skipping `.create()` is catalogue membership and duplicate detection — and, because matching is by string, a misspelled name fails silently however the object was built (it simply matches no granted permission, so the check denies). Declaring once via `.create()` and referencing that one instance is what keeps names from drifting. The shipped permissions are listed under [Shipped with the app](#shipped-with-the-app).

### The `PermissionScope` class

A `PermissionScope` is a named **kind** of boundary a role can be assigned at — `global`, `course`, `quiz`, and so on. It answers *where* a role applies; how a scope kind maps onto the `scope` / `scope_object_id` columns of `role_assignment` is covered under [Scopes](#scopes). Import it from `app.lib.permissions`:

```python
from app.lib.permissions import GLOBAL, PermissionScope
```

**State** — two fields:

| Attribute | Type | Meaning |
|---|---|---|
| `name` | `str` | The scope kind's identifier (e.g. `course`); stored verbatim in `role_assignment.scope`. |
| `parent` | `PermissionScope \| None` | The enclosing scope kind, or `None` for a root. Scope kinds chain from a narrow boundary up to a broader one. |

As with `Permission`, there is no custom `__eq__` — equality is identity.

**`get_parents() -> list[PermissionScope]`** — returns this scope's ancestors nearest-first (`[parent, grandparent, …]`) by walking `parent` pointers, ending at the root (an empty list for a root scope). It exists to support scope-hierarchy cascade — a role granted at a broad scope applying to narrower ones — planned for a later phase. It does **not** drive authorization today: `can()` matches a scope by its exact name and does not walk to parents.

**`PermissionScope.create(name, parent=None)`** — the way to declare a scope kind. It constructs the scope, **registers it on the `PERMISSION_SCOPES` hook**, and returns it; a duplicate name **raises `ValueError`**, and a `parent` must already be registered (the `global` root always is). Declare core scopes in `app.core.permissions.scopes`; a plugin declares its own from its `__init__`:

```python
COURSE = PermissionScope.create("course", parent=GLOBAL)
```

**`PermissionScope(name)` vs `.create(name)`** — the bare constructor is internal/test-only and does not register. For scopes this difference is **not** cosmetic: a scope kind is resolved back from its name through `PermissionScopesRegistry.get(name)` — which the CLI uses to validate `--scope`. A bare-constructed scope is absent from that registry, so resolving it by name raises `PermissionScopeNotFound` — exactly the no-op `--scope` assignment the CLI now rejects. Always declare via `.create()` and reference the returned instance (`GLOBAL`, your `COURSE`, …). The shipped root scope is exported as `GLOBAL`; see [Shipped with the app](#shipped-with-the-app).

### Scopes

A scope answers *where* a role applies. It is the pair of two columns on `role_assignment`:

- **`scope`** — the *kind* of boundary (e.g. `global`, `course`, `quiz`), one of the kinds declared through the `PERMISSION_SCOPES` hook. It is a free-form string, not a foreign key.
- **`scope_object_id`** — *which* specific entity of that kind (e.g. the id of one course). It is polymorphic — it points at whatever domain table the scope kind maps to, so it is deliberately **not** a foreign key.

A scope kind may name a parent (`PermissionScope.create(name, parent=…)`), so kinds form a hierarchy from a narrow boundary up to a broader one.

The `global` scope is the root: it applies everywhere and names no object, so `scope = 'global'` requires `scope_object_id` to be `NULL`, while every non-global scope requires a `scope_object_id`. A database `CHECK` constraint enforces this pairing.

#### Shipped with the app

| Kind | Names | Notes |
|---|---|---|
| **Scopes** | `global` | The root scope; applies platform-wide; `scope_object_id` is `NULL`. |
| **Permissions** | `email.whitelist.read`, `email.whitelist.create`, `email.whitelist.delete` | Gate the registration email-whitelist endpoints. |
| **Roles** | `admin` | Grants the three `email.whitelist.*` permissions. The seed migration also assigns it at the `global` scope to every account that was a superuser when the migration ran — a one-time backfill, not an ongoing rule. |

### Extending the permission system

**Declare a permission or scope kind** — a plugin declares its own from its `__init__`, exactly as it registers tools or config. Core declarations (not tied to any plugin) live in `app.core.permissions` (permissions) and `app.core.permissions.scopes` (scope kinds). Import everything you need from `app.lib.permissions` — never from `app.core` or the hook modules directly.

```python
from app.lib.permissions import GLOBAL, Permission, PermissionScope
from app.lib.plugins import SparkthPlugin

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
# or scoped to one object — pass the scope kind and the object id
make cli -- roles assign-role john grader --scope course --scope-object-id 42
```

`--scope` must name a declared scope kind (`global`, or any added via `PermissionScope.create()`); an unknown kind is rejected rather than persisted as a no-op assignment.

From application code, call `assign_role`:

```python
from app.lib.permissions import GLOBAL, assign_role

# Pass a declared PermissionScope instance (GLOBAL is the shipped root; COURSE is your
# PermissionScope.create("course", …) result). The platform-wide GLOBAL scope names
# no object, so scope_object_id is None:
await assign_role(user_id, "grader", GLOBAL, None, session)
# Scoped to one course:
await assign_role(user_id, "grader", COURSE, "42", session)
```

**Gate an endpoint on a permission** — depend on `RequirePermission`:

```python
from fastapi import Depends
from app.api.v1.auth import RequirePermission
from app.lib.permissions import GLOBAL

# Reference your declared instances — don't reconstruct them. THING_READ and COURSE_EDIT
# are Permission.create(...) results; COURSE is a PermissionScope.create(...) result.
@router.get("/things", dependencies=[Depends(RequirePermission(THING_READ, GLOBAL))])
async def list_things(): ...

# For a scoped check, name the path parameter that carries the object id:
RequirePermission(COURSE_EDIT, COURSE, "course_id")  # reads {course_id}
```

## Contributing

Contributions are welcome. Open a pull request against `main` and a maintainer will take a look.

### Requesting an automated code review

This repository has an automated code review powered by Claude. To request a review on your pull request, post a comment containing `@claude-review` on the PR. The workflow runs on demand only (it does not run automatically on every push), so use the mention whenever you want a fresh pass, for example after pushing new commits.

## License

This project is licensed under the MIT License — see the [LICENSE](LICENSE) file for details.
