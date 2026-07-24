# Permissions

Sparkth authorizes actions with a scoped role-based access control (RBAC) model. This guide
explains the model and how to extend it. For exact signatures and behaviour of the classes
and functions, see the generated [permissions reference](../reference/permissions.md).

## The model

Authorization data lives in three tables:

- **`role`** — a named role (e.g. `admin`).
- **`role_permission`** — the permissions a role grants. A permission is a free-form dotted
  string (e.g. `assignment.grade`); a role grants many.
- **`role_assignment`** — grants a role to a user at a single scope.

A user is authorized when they hold, through an active `role_assignment` at the relevant
scope, a role whose `role_permission` rows include the permission. `can()` resolves exactly
this against the three tables — it is the single authorization check.

## Permissions and scopes are declared in code

The vocabulary the system draws on — which permission strings and which scope kinds exist —
is declared in application code, not kept in a catalogue table.

- **Permissions** are declared with `Permission.create("assignment.grade")`, which registers
  the permission on the **`PERMISSIONS`** hook. Core permissions are declared this way in
  `sparkth.core.permissions`; plugins declare their own from their `__init__`.
- **Scope kinds** are declared with `PermissionScope.create("course", parent=...)`, which
  registers the scope on the **`PERMISSION_SCOPES`** hook. The root `global` scope is declared
  this way in `sparkth.core.permissions.scopes`; plugins declare their own from `__init__`.

Each hook is a `SingleNamedItemHook` keyed by name: declaring two permissions or two scope
kinds with the same name **raises `ValueError`**, so a collision fails fast at import time.
Resolve a name back to its registered object with `get_permission(name)` /
`get_permission_scope(name)`.

!!! warning "Always declare via `.create()`, never the bare constructor"
    Only `.create()` registers the object on its hook (the source of truth) and makes a
    duplicate name fail fast. Bind each declaration to a constant and reference that one
    instance wherever the permission or scope is used (e.g. `EMAIL_WHITELIST_READ`, `GLOBAL`).
    The bare `Permission(name)` / `PermissionScope(name)` constructors are internal/test-only.
    A bare-constructed **scope** is absent from the hook, so resolving it by name raises
    `PermissionScopeNotFound` — exactly the no-op `--scope` assignment the CLI rejects.

## Scopes: *where*, not *what*

A scope answers *where* a role applies. It is the pair of columns on `role_assignment`:

- **`scope`** — the *kind* of boundary (e.g. `global`, `course`), one of the kinds declared
  through `PERMISSION_SCOPES`. A free-form string, not a foreign key.
- **`scope_object_id`** — *which* specific entity of that kind. Polymorphic, so deliberately
  **not** a foreign key.

Scope is **not a power level.** Authorization is purely permission-based: `can()` authorizes
only when the user's role actually contains the checked permission. Assigning a role at
`global` grants only that role's permissions, applied platform-wide — it is not an admin or
superuser tier (there is no superuser bypass; `is_superuser` was removed). The `admin` role
is far-reaching because of the permissions it *bundles*, not the scope it is assigned at.

Every scope kind is either a **`PermissionScope`** — which names one object of its kind (a
non-`NULL` `scope_object_id`) — or an **`ObjectlessPermissionScope`**, a singleton naming no
object (`scope_object_id = NULL`). This pairing is enforced in application code (`assign_role`
calls the scope's `validate_object_id`, raising `InvalidScopeObjectId` on a mismatch), not a
database `CHECK` constraint.

`can()` and `has_role()` cascade a grant **parent → child**: a grant at an
`ObjectlessPermissionScope` ancestor (`global`, `whitelist`) satisfies a check at any of its
descendants. Object-bearing multi-level cascade (e.g. a grant at one `org` applying to its
`course`s) needs a materialized path and remains deferred
([#420](https://github.com/edly-io/sparkth/issues/420) Phase 2).

## Shipped with the app

| Kind | Names | Notes |
|---|---|---|
| **Scopes** | `global`, `whitelist`, `role` | `global` is the objectless root (applies platform-wide). `whitelist` is an objectless singleton nested under `global` for the registration whitelist. `role` is object-bearing (nested under `global`) so role management can be delegated per-role by that role's id. A `global` grant cascades down to both. |
| **Permissions** | `email.whitelist.{read,create,delete}`; `role.{create,read,update,delete}`; `permission.read` | Gate the registration email-whitelist endpoints, the role-management API, and listing the assignable permission vocabulary respectively. |
| **Roles** | `admin` | Grants the three `email.whitelist.*`, the four `role.*`, and `permission.read`. A seed migration also assigned it at `global` to every account that was a superuser when the migration ran — a one-time backfill. |

Roles and their permission grants are managed at runtime through the role-management REST API
under `/api/v1/permissions` (gated by `role.*` / `permission.read`). See the REST API docs
(`/docs`) for the endpoints. Permissions and scope kinds themselves are **not** editable
there — they are declared in code.

## Extending the permission system

**Declare a permission or scope kind** — a plugin declares its own from its `__init__`,
exactly as it registers tools or config. Core declarations live in `sparkth.core.permissions`
(permissions) and `sparkth.core.permissions.scopes` (scope kinds). Import everything from
`sparkth.lib.permissions` — never from `sparkth.core` or the hook modules directly.

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

**Add a role and its permissions** — seed them in a migration:

```sql
INSERT INTO role (name, description, created_at, updated_at)
VALUES ('grader', 'Grades submissions', now(), now());
INSERT INTO role_permission (role_id, permission, created_at, updated_at)
VALUES ((SELECT id FROM role WHERE name = 'grader'), 'assignment.grade', now(), now());
```

**Assign a role to a user** — for bootstrapping, use the CLI (it looks the user up by
username or email):

```bash
# assign at the global scope
make cli -- roles assign-role john admin
# or at another objectless scope — no --scope-object-id, same as global
make cli -- roles assign-role jane "Whitelist Manager" --scope whitelist
# or scoped to one object — pass the scope kind and the object id
make cli -- roles assign-role john grader --scope course --scope-object-id 42
```

`--scope` must name a declared scope kind; an unknown kind is rejected rather than persisted
as a no-op. Whether `--scope-object-id` is required depends on the kind: an
`ObjectlessPermissionScope` must be assigned *without* one, a `PermissionScope` *with* one.
The CLI defers this to `assign_role`, which raises `InvalidScopeObjectId` on a mismatch.

From application code, call `assign_role`:

```python
from sparkth.lib.permissions import assign_role
from sparkth.lib.permissions.scopes import GLOBAL

# GLOBAL names no object, so scope_object_id is None:
await assign_role(user_id, "grader", GLOBAL, None, session)
# Scoped to one course (COURSE is your PermissionScope.create("course", …) result):
await assign_role(user_id, "grader", COURSE, "42", session)
```

**Gate an endpoint on a permission** — call `.require_in_global_scope()` or
`.require(scope, scope_param=None)` on the permission itself. `scope` is a declared
`PermissionScope` **object** (e.g. `GLOBAL`, `WHITELIST`, your `COURSE`), not its name.
`scope_param` names the path parameter carrying the scope object id — omit it for an
objectless scope, supply it for an object-bearing one. Getting this wrong raises `ValueError`
at import time (a wiring error, never a silent 403).

```python
from fastapi import Depends
from sparkth.lib.permissions import COURSE_EDIT, EMAIL_WHITELIST_READ, THING_READ
from sparkth.lib.permissions.scopes import COURSE, WHITELIST

# Global scope, as a route dependency:
@router.get("/things", dependencies=[Depends(THING_READ.require_in_global_scope())])
async def list_things(): ...

# Objectless scope — WHITELIST is a singleton, so no scope_param:
@router.get("/whitelist", dependencies=[Depends(EMAIL_WHITELIST_READ.require(WHITELIST))])
async def list_whitelist(): ...

# Object-bearing scope — pass the PermissionScope object and the path parameter carrying
# the object id (read from the URL on each request):
@router.patch(
    "/courses/{course_id}",
    dependencies=[Depends(COURSE_EDIT.require(COURSE, "course_id"))],
)
async def edit_course(course_id: int): ...
```

The returned dependency resolves the current user, checks the permission, and returns the
authenticated `User`. Put it in `dependencies=[...]` to gate a route, or inject it as a
parameter (`user: User = Depends(...)`) when the handler needs the authorized user — both
enforce the permission identically. A missing permission yields **403**.

**Check the current user's permission** — a client (e.g. the web UI) can ask whether the
authenticated user holds a permission via `GET /api/v1/permissions/can?permission=<name>`
(optionally `&scope=<kind>&scope_object_id=<id>`), which returns `{"allowed": true|false}`.
It is backed by `can()` and is a convenience for gating UI — not a security boundary, since
every endpoint still enforces its own permission and returns 403.
