# Permissions

Sparkth authorizes actions with a scoped role-based access control (RBAC) model. This guide
explains the model and how to extend it. For exact signatures and behaviour of the classes
and functions, see the generated [permissions reference](../reference/permissions.md).

## The model

Authorization data lives in six tables:

- **`role`** — a named role (e.g. `admin`).
- **`role_permission`** — the permissions a role grants. A permission is a free-form dotted
  string (e.g. `assignment.grade`); a role grants many.
- **`role_assignment`** — grants a role to a user at a single scope.
- **`user_group`** — a named, flat set of users (see [Groups](#groups)).
- **`group_membership`** — a user's membership in a group.
- **`group_role_assignment`** — grants a role to every member of a group at a single scope.

A user is authorized when they hold, at the relevant scope, a role whose `role_permission`
rows include the permission — either through an active `role_assignment` of their own or
through an active `group_role_assignment` of a group they actively belong to. `can()`
resolves exactly this — it is the single authorization check.

## Permissions and scopes are declared in code

The vocabulary the system draws on — which permission strings and which scope kinds exist —
is declared in application code, not kept in a catalogue table.

- **Permissions** are declared with `Permission.create("assignment.grade")`, which registers
  the permission on the **`PERMISSIONS`** hook. Core permissions are declared this way in
  `sparkth.core.permissions`; plugins declare their own at module level in their `plugin.py`, or in a module
  their routes import when the routes need the constant.
- **Scope kinds** are declared with `PermissionScope.create("course", parent=...)`, which
  registers the scope on the **`PERMISSION_SCOPES`** hook. The root `global` scope is declared
  this way in `sparkth.core.permissions.scopes`; plugins declare their own at module level in
  their `plugin.py`, or in a module their routes import when the routes need the constant.

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

`can()` and `has_role()` cascade a grant **parent → child**. A grant at an
`ObjectlessPermissionScope` ancestor (`global`, `whitelist`) satisfies a check at any of its
descendants. A grant at an ancestor that names an object (one `org`) also applies to the objects
beneath it (its `course`s), by way of the checked object's **`scope_path`**: the
materialized path of the object, one `<scope name>:<object id>` segment per level, joined by
`/`, root first. A quiz inside course 123 of org 5 has the path `org:5/course:123/quiz:777`,
so a check at that quiz is satisfied by a grant at any of these, nearest first:

```text
quiz:777 → course:123 → org:5 → global
```

The path rules:

- The caller supplies the path: `can(user, permission, scope, scope_path, session)` takes it, and a
  `ScopeObjectMixin` record handed to `require_for_object()` carries it. It is the only input naming the
  checked object.
- Pass `None` for an objectless scope.
- A single-segment path (`quiz:777`) names the object without ancestry, so only a grant at that object and
  the objectless ancestors count.
- The path must end at a segment named after the checked scope (`quiz:777` for a check at `quiz`). Any
  segments before it must be the ancestors of that scope that name an object, in order
  (`org:5/course:123/quiz:777`). Any other path raises `ValueError`.
- An object id may not contain `/` wherever it becomes a path: `build_scope_path`, the ids given to
  `require_for_object()`, and `scope_object_id` on `/permissions/can/batch` (answered with 422).

Role assignment and revocation never cascade: a grant is stored at exactly the scope it was
assigned at.

## Shipped with the app

| Kind | Names | Notes |
|---|---|---|
| **Scopes** | `global`, `whitelist`, `role`, `group`, `user`, `plugin`, `conversation` | `global` is the objectless root (applies platform-wide). `whitelist` is an objectless singleton nested under `global` for the registration whitelist. `role` is object-bearing (nested under `global`) so role management can be delegated per-role by that role's id. `group` is object-bearing (nested under `global`) so group management can be delegated per-group by that group's id. `user` is object-bearing (nested under `global`) and names one user by id: a user's own records live at their `user` scope, so a grant there reaches that user's records only. `plugin` is object-bearing (nested under `global`) and names one plugin by its name, so a grant there reaches that plugin only (`plugin.use` to use it, `plugin.manage` to switch it on or off for everyone, `analytics.read` to read its analytics). `conversation` is object-bearing, declared by Compose and nested under `user`, and names one conversation by its UUID: a grant at the owner's `user` scope or at `global` cascades to it. A `global` grant cascades down to all six. |
| **Permissions** | `email.whitelist.{read,create,delete}`; `role.{create,read,update,delete}`; `group.{create,read,update,delete}`; `permission.read`; `analytics.read`; `audit.read`; `user.read`; `llm.config.{create,read,update,delete}`; `plugin.use`; `plugin.manage`; `file.upload`; `compose.conversation.{read,write}`; `googledrive.{read,sync,delete}` | Gate the registration email-whitelist endpoints, the role-management API, the group-management API, listing the assignable permission vocabulary, the analytics dashboards and their read API, querying and exporting the audit trail, and reading usernames outside user management (Explore's `/analytics/query`, which names each actor, and its saved `/analytics/views`; both also need `analytics.read`) respectively. The `llm.config.*`, `compose.conversation.*` and `googledrive.*` names authorize actions on one user's records. `llm.config.*` and `googledrive.*` are checked at the `user` scope of the record's owner; `compose.conversation.*` is checked as described below the table. `compose.conversation.read` lists and reads Compose conversations and their attachments, `compose.conversation.write` sends turns and attaches and detaches documents; `llm.config.create`, `llm.config.read`, `llm.config.update` and `llm.config.delete` to create, list, change (edit, rotate the key, set active) and delete AI keys; `googledrive.read` to list and read Google Drive folders and files and download files, `googledrive.sync` to sync and refresh folders, and `googledrive.delete` to delete files. A plugin's analytics read checks `analytics.read` at that plugin's `plugin:<name>` scope (Compose at `plugin:compose`, Drive at its own `plugin:<name>` scope), so a `global` holder reads every plugin's and a holder at one plugin reads only that plugin's. A plugin-scoped `analytics.read` serves that plugin's read API only; the analytics dashboards need it at `global`. `plugin.use` authorizes using one plugin's routes, at that plugin's `plugin` scope (every Compose route except its analytics read needs it at `plugin:compose`, every Google Drive route except the OAuth callback and its analytics read needs it at its own `plugin:<name>` scope, the PXC authoring routes need it at `plugin:pxc` (the learner routes need no user login), and every Slack route except the OAuth callback and the events webhook needs it at `plugin:slack`), and the `/api/v1/plugins` routes list only the plugins the caller holds it at (an empty list, not 403, when it holds it at none), while reading, configuring, enabling or disabling one plugin needs it at that plugin; a Compose turn is given the tools and the agent of only the plugins its caller holds it at; `plugin.manage` authorizes `PATCH /api/v1/plugins/{plugin_name}/system`, which switches one plugin on or off for every user (one permission covers both directions), checked at that plugin's `plugin` scope, so a `global` holder switches any plugin and a holder at `plugin:<name>` switches only that one; it leaves each user's own preference and configuration untouched, and the change is recorded in the audit trail as `plugin.system_enabled_changed`; `file.upload` authorizes `POST /api/v1/parser/upload`, checked at the uploader's own `user` scope (a `global` holder passes too). |
| **Roles** | `admin`, `sparkth_user`, `plugin_user` (none can be changed or deleted) | `admin` grants the three `email.whitelist.*`, the four `role.*`, the four `group.*`, `permission.read`, `analytics.read`, `audit.read`, `user.read`, and `plugin.manage` (it does not hold the `llm.config.*`, `compose.conversation.*` or `googledrive.*` names). A seed migration also assigned it at `global` to every account that was a superuser when the migration ran — a one-time backfill. `sparkth_user` is the default role: every account holds it at its own `user` scope (a migration assigned it to every existing account; registration, Google sign-up and `create-user` assign it to each new one), and its default permissions, the `llm.config.*`, `compose.conversation.*`, `googledrive.*` and `file.upload` names, are granted by later migrations, one of which also assigns the role to any account that never had it. `plugin_user` holds `plugin.use`; every account holds it at `global` (registration, Google sign-up and `create-user` assign it to each new one), so every account can use every plugin. |

Roles and their permission grants are managed at runtime through the role-management REST API
under `/api/v1/permissions` (gated by `role.*` / `permission.read`). See the REST API docs
(`/docs`) for the endpoints. Permissions and scope kinds themselves are **not** editable
there — they are declared in code.

Compose checks a conversation's permissions at the conversation itself where one is named, except that attaching
documents is checked at the owner's `user` scope. Reading one conversation, its last message and its attachments,
sending a turn into it, and detaching documents are checked at that conversation's `conversation` scope; listing
conversations and starting one are checked at a `user` scope. Attaching a document is checked at the conversation
owner's `user` scope, so a role granted at one conversation cannot add the owner's documents to it, and documents
such a holder names on a turn are not attached. A conversation granted this way does not appear in the holder's
conversation list, the holder opens it by id. A role assigned at a conversation takes effect there only for the
conversation permissions it holds, so a role holding only `compose.conversation.read` shares it view-only. A holder
of `compose.conversation.write` can also learn the conversation's history, because a turn replays it to the model;
a turn also retrieves from the documents already attached to the conversation, so a write grant exposes their
content too.

```bash
# let jane open one conversation, through a role that holds compose.conversation.read
make cli -- roles assign-role jane conversation-reader --scope conversation --scope-object-id <uuid>
```

Management of one role can be delegated through the `role` scope, the way a group's can (see
[Groups](#groups)): a role assigned at `role` with that role's id covers that role only. Listing
returns the roles the caller holds `role.read` at (every role for a `global` grant). A caller who
holds `role.read` nowhere gets 403, not an empty list. Creating a role stays at `global`.

Roles shipped with the app (`admin`, `sparkth_user`, `plugin_user`) are **built-in** (`is_builtin = true`) and
cannot be changed: renaming one, editing its description, granting or revoking its permissions, and deleting it all
return `409`. Their permissions change only through a migration. An operator who needs a variant creates a
role of their own and grants it the permissions they want. Assigning a built-in role to users or groups, and
revoking it, work as for any other role. Roles created through the API are not built-in. A migration that
seeds a new shipped role sets `is_builtin = true` on it. Deleting a role also removes every user and group
assignment of it (active and revoked), recording `role.unassigned` per active user assignment and
`group.role_revoked` per active group assignment; the history stays in the audit trail. It removes
every grant scoped to the role (`role:<id>`) too, so a later role that reuses the id never inherits
them.

A user who holds `plugin_user` at `plugin:<name>` instead of at `global` can use only those plugins.
Every account holds `plugin_user` at `global`, so an assignment at a plugin changes nothing until the `global`
assignment is revoked. To limit a user to some plugins, assign `plugin_user` at each allowed plugin and revoke
the `global` assignment:

```bash
make cli -- roles assign-role jane plugin_user --scope plugin --scope-object-id compose
make cli -- roles revoke-role jane plugin_user --scope global
```

A group the user belongs to that holds `plugin_user` (or any role with `plugin.use`) at `global` still gives them
every plugin; revoke that grant with `groups revoke-role-from-group`.

Every route of the built-in plugins is gated on `plugin.use` at `plugin:<name>`, except those the table above
names; a test fails on any plugin route that is neither gated nor listed with a reason.

A Compose turn is given the tools and the agent of only the plugins its caller holds `plugin.use` at. Course
design is its own plugin, `course-design`, so a user limited to `plugin:compose` can open Compose but is offered
no agent. Assign `plugin_user` at `course-design` too, and at each plugin whose tools or agent the user should
get in Compose. A request that names a tool of a plugin left out this way records a `permission.denied` event
for that plugin; a request for every tool records none.

An LMS publishing tool lists and places the content of a plugin only for a caller who holds `plugin.use` at that
plugin. Asking by name for the content of another plugin is refused and records a `permission.denied` event;
listing records none.

When the account that connected a Slack workspace lacks `plugin.use` at `plugin:slack`, the bot replies in that
workspace that it is disabled instead of answering.

## Groups

A **group** is a flat, named set of users — the second assignee source for role grants.
Granting a role to a group at a scope is one `group_role_assignment` row, and every active
member holds that role there: "every math instructor gets the teacher role in course 42" is
one grant instead of one `role_assignment` per instructor, and membership churn (someone
joins or leaves the set) is a membership edit, not a grant edit.

- Groups are **flat by design** — no group-in-group nesting. Organizational hierarchy
  ("teachers belong to departments, which belong to universities") is a *scope*-hierarchy
  concern, answered by where in the scope tree a group's grant is placed, not by nesting
  groups.
- `can()` / `has_role()` resolve group grants through the **same scope chain** as direct
  assignments — a group grant at `global` cascades to descendant scopes exactly like a
  direct one, and `has_role` counts a role granted through a group as held, like a direct
  assignment.
- Membership and group-role assignments are **soft-deleted**: removing a member (or revoking
  a group's role) drops the inherited access immediately while keeping the history row for
  auditing.
  Deleting the group itself hard-deletes those history rows along with the group.
- Membership rows carry a **`source`** column (`"manual"` today); rule-driven membership can
  later own its `"rule"` rows without touching manually managed ones.

Group structure is managed through the REST API under `/api/v1/permissions/groups`
(CRUD, gated by the `group.*` permissions; deleting a group also deletes its memberships, its
role assignments and every grant scoped to it). Membership and group-role grants are CLI-managed,
mirroring how user-role assignment is CLI-only:

```bash
# add a user (by username or email) to a group, or remove one
make cli -- groups add-member john cs-staff
make cli -- groups remove-member john cs-staff
# grant a role to every member of a group, at the global scope — and take it back
make cli -- groups assign-role-to-group cs-staff grader
make cli -- groups revoke-role-from-group cs-staff grader
# or scoped to one object — same --scope/--scope-object-id rules as roles assign-role
make cli -- groups assign-role-to-group cs-staff grader --scope course --scope-object-id 42
```

From application code, use the façade (`sparkth.lib.permissions`): `add_group_member`,
`remove_group_member`, `assign_role_to_group`, `revoke_role_from_group`,
`get_group_by_name`.

Management of one group can be delegated, like the per-role `role` scope. The endpoints that
address one group by `{group_id}` (get, update, delete) authorize at the `group` scope, so a
role assigned at `group` with that group's id covers that group only. A `global` grant still
satisfies them through the cascade. Listing returns the groups the caller holds `group.read` at
(every group for a `global` grant). A caller who holds `group.read` nowhere gets 403, not an
empty list. Creating a group stays at `global`. The scope object id is the group's numeric id,
listed by `GET /api/v1/permissions/groups`:

```bash
# let jane manage group 7 only, through a role that holds group.read / group.update
make cli -- roles assign-role jane group-manager --scope group --scope-object-id 7
```

## Audit trail

Every change to access control is written to the audit trail, in the same transaction as
the change itself, so a change that fails or is rolled back leaves no record. The engine
functions record the events, so the REST API, the CLI, and application code are all covered;
CLI commands are attributed to the `cli` system actor.

| Event | Recorded by | Target | Snapshot |
|---|---|---|---|
| `role.created`, `role.updated`, `role.deleted` | `create_role`, `update_role`, `delete_role` | `role` | name and description (before and after for an update) |
| `role.permission_granted`, `role.permission_revoked` | `add_role_permission`, `remove_role_permission` | `role` | the permission |
| `role.assigned`, `role.unassigned` | `assign_role`, `revoke_role`, `delete_role`, `delete_group` | `user` | role, scope, and scope object id |
| `group.created`, `group.updated`, `group.deleted` | `create_group`, `update_group`, `delete_group` | `group` | name and description (before and after for an update) |
| `group.member_added`, `group.member_removed` | `add_group_member`, `remove_group_member`, `delete_group` | `group` | the member's user id |
| `group.role_assigned`, `group.role_revoked` | `assign_role_to_group`, `revoke_role_from_group`, `delete_role`, `delete_group` | `group` | role, scope, and scope object id |

The grant, assign, and add-member functions are idempotent, and so are their revoke and
remove counterparts: a call that changes nothing (the grant already exists, or there is
nothing active to revoke) records nothing. Likewise an update that leaves a role's or group's
name and description as they were records nothing. Deleting a role records `role.unassigned`
and `group.role_revoked` for each of its active assignments (users and groups) and for each
active grant scoped to it (revoked grants record nothing). Deleting a group records
`group.member_removed` and `group.role_revoked` for its active memberships and assignments, and
`role.unassigned` and `group.role_revoked` for the active grants at `group:<id>`.

A refused attempt to start a conversation is recorded against a conversation id that was never stored.

## Before adding one

A permission name is stored as a literal string in every `role_permission` row that grants
it, and `can()` matches it literally. Once a permission has been granted, renaming it revokes
it from every holder at once, and a rename or a removal leaves the old rows behind until a data
migration rewrites or deletes them. A scope kind is stored the same way, in the `scope` column of every assignment made at
it. Settle these before declaring one:

- **Is the action already covered?** If a declared permission already means exactly this
  action, gate on it. Reuse only on an exact match: gating a new action on an existing
  permission hands that action to everyone who already holds it.
- **What does it gate?** Name the routes or features that check it, and declare the
  permission in the same change as the code that checks it.
- **One permission or several?** A permission is the smallest thing an operator can grant.
  Actions behind one permission cannot later be granted apart without a data migration that
  rewrites every role holding it. Permissions that are always granted together add vocabulary
  with nothing to show for it.
- **Where is it checked?** At `global`, at an existing scope kind, or at a new one. A new
  scope kind needs a parent and is either objectless or object-bearing, and a grant at an
  objectless ancestor satisfies the check at every descendant (see
  [Scopes](#scopes-where-not-what)).
- **Who holds it after deploy?** Nobody, unless a data migration grants it to a seeded role
  (see *Add a role and its permissions* below). Granting it to `admin` that way gives it to
  every current admin as soon as the release is migrated. Left ungranted, an operator grants
  it at runtime through the role-management API, to a role they created: a built-in role's
  permissions change only by migration.
- **Does the UI check it?** The frontend checks a permission with `checkPermission`, which
  accepts only names in the `PermissionName` union in `frontend/lib/permissions/names.ts`. That
  union mirrors the whole vocabulary by hand: a core permission is added to it directly, and a
  plugin's permissions are declared in the plugin's own `permissions.d.ts`
  (see [Frontend plugins](frontend-plugins.md)).

## Extending the permission system

**Declare a permission or scope kind** — a plugin declares its own at module level in
`plugin.py`, or in a module of the plugin that its routes import when they need
the constant (routes cannot import from `plugin.py`, which imports them),
bound to a constant, never in the plugin class's `__init__`: the loader and the
plugin's own tests each construct the class, and a second declaration of a name raises
`ValueError`. Core declarations live in `sparkth.core.permissions` (permissions) and
`sparkth.core.permissions.scopes` (scope kinds). Import everything from
`sparkth.lib.permissions` — never from `sparkth.core` or the hook modules directly.

```python
# sparkth/plugins/grader/plugin.py
from sparkth.lib.permissions import Permission
from sparkth.lib.permissions.scopes import GLOBAL, PermissionScope

ASSIGNMENT_GRADE = Permission.create("assignment.grade")
# a scope kind's parent must already be registered (the global root always is)
COURSE = PermissionScope.create("course", parent=GLOBAL)
```

**Add a role and its permissions** — seed them in a migration:

```sql
INSERT INTO role (name, description, is_builtin, created_at, updated_at)
VALUES ('grader', 'Grades submissions', true, now(), now());
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
The CLI defers this to `assign_role`, which raises `InvalidScopeObjectId` on a mismatch. For the `plugin` scope
the CLI also checks that `--scope-object-id` names a loaded plugin, so a mistyped plugin name is rejected rather
than stored as a grant that reaches no plugin.

**Revoke a role from a user** with `roles revoke-role`, which takes the same arguments and `--scope` /
`--scope-object-id` options and removes only the assignment at that exact scope:

```bash
make cli -- roles revoke-role john admin
make cli -- roles revoke-role john grader --scope course --scope-object-id 42
```

An unknown scope kind or user, or a `--scope-object-id` that contradicts the scope kind, exits non-zero. A user
who holds no assignment of that role at that exact scope (a mistyped role name included) gets a "nothing revoked"
notice and exit zero, so a re-run is harmless. Built-in roles can be revoked from a user. `revoke-role` does not
check that a plugin is loaded, so a grant left on a plugin that was removed can still be revoked.

From application code, call `assign_role`:

```python
from sparkth.lib.permissions import assign_role
from sparkth.lib.permissions.scopes import GLOBAL

# GLOBAL names no object, so scope_object_id is None:
await assign_role(user_id, "grader", GLOBAL, None, session)
# Scoped to one course (COURSE is your PermissionScope.create("course", …) result):
await assign_role(user_id, "grader", COURSE, "42", session)
```

**Gate an endpoint on a permission** — call `.require_in_global_scope()`, `.require(scope, scope_param=None)` or
`.require_for_object(scope, scope_object_id)` on the permission itself. `scope` is a
declared `PermissionScope` **object** (e.g. `GLOBAL`, `WHITELIST`, your `COURSE`), not its
name. An objectless scope takes no `scope_param` and cannot use `require_for_object`; an object-bearing
scope needs a `scope_param` or `require_for_object`. A wrong combination raises `ValueError` at import
time (a wiring error, never a silent 403).

- `require(scope, scope_param)`: `scope_param` names the path parameter carrying the object id.
- `require_for_object(scope, scope_object_id)`: `scope_object_id` is a fixed id string, or an async
  FastAPI dependency returning the id as a `str` or the loaded `ScopeObjectMixin` record. An id becomes the path of that object at the checked scope;
  a record's own `scope_path` is checked, so a role granted at an ancestor object
  authorizes it. A record is checked at its own scope, so to
  authorize at an owner's scope the dependency returns the owner's record or id, not the
  child record. The dependency returns `None` for a missing record. `None` is checked at the scope
  itself, so a caller who holds the permission only at objects gets 403 (and a denial audit row)
  and cannot tell a missing object from one they may not access. A caller who passes the check
  reaches the route, which raises its own not-found. The dependency runs after authentication, so
  an anonymous caller gets 401 first.

  To gate a record owned by a user, the dependency loads the record and raises the record's not-found
  error when it is missing (a 404 for everyone, with no denial audit row). A record that is itself a
  scope object is gated by returning the record, so grants at the record, at its owner and at `global`
  all authorize. A record that is not one is gated by returning the owner's id as the object id of the
  `user` scope. A caller who lacks the permission on an existing record gets 403.

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

**Gate a route that names no object** — a list or create route has no object to put in the path, so
`require()` cannot check it at an object-bearing scope. Gate each kind of route as follows:

- **Create** checks at the scope the new object will live in. A root object (a group, a role) lives
  under `global`, so `require_in_global_scope()` is right. A record the caller will own is created at
  the caller's own `user` scope: gate the route with `require_for_object(USER, get_current_user_id)`,
  where `get_current_user_id` returns the caller's id.
- **List** uses `.require_for_any_object(scope)`. The dependency returns the ids of the objects of that
  scope at which the caller holds the permission, as strings, or `None` when a grant at an objectless
  ancestor (`global`) covers every object. A caller who holds the permission at no object is refused
  with 403 and a `permission.denied` audit event. The route filters its query by the ids, so a role
  granted at one object lists that object only. A scope whose objects have integer keys passes the ids
  through `object_id_str_to_int`, which skips any id that is not a plain integer and keeps `None` as `None`.
  - Grants at an object-bearing ancestor are not considered; only grants at the scope itself and at
    objectless ancestors are.
  - An objectless scope names no objects to list, so `require_for_any_object` raises `ValueError` for one.
  - A list route that must answer a caller who holds the permission nowhere with an empty list, not 403,
    reads the ids with `get_accessible_scope_object_ids(user, permission, scope, session)` in its own
    dependency. `None` means every object, an empty set means none, and no audit row is written.
  - A list of one user's records takes an optional `owner_id` query parameter and gates with
    `require_for_object(USER, get_listed_owner_id)`. It returns `owner_id`, or the caller's id when
    absent, so listing another user's records needs the permission at that user's scope or at `global`.
    An `owner_id` that names no user is not looked up: a holder gets an empty list, a non-holder 403.

```python
from sparkth.lib.permissions import GROUP_READ, object_id_str_to_int
from sparkth.lib.permissions.scopes import GROUP


@router.get("/groups")
async def list_groups(
    accessible_ids: set[str] | None = Depends(GROUP_READ.require_for_any_object(GROUP)),
    session: AsyncSession = Depends(get_async_session),
) -> list[GroupResponse]:
    # None: every group. Otherwise only the groups whose id is in the set.
    return await load_groups(object_id_str_to_int(accessible_ids), session)  # your own query
```

**Make an object cascade** — a table model that is an object of a scope inherits `ScopeObjectMixin`,
sets its `scope`, and stores the path of its parent as `parent_scope_path` when it is created:

```python
from sqlmodel import Field
from sparkth.lib.permissions.scopes import ScopeObjectMixin


class Course(ScopeObjectMixin, table=True):
    scope = COURSE  # the PermissionScope this model is an object of

    id: int | None = Field(default=None, primary_key=True)


async def create_course(org: Org, session: AsyncSession) -> Course:
    course = Course(parent_scope_path=org.scope_path)
    session.add(course)
    await session.flush()
    return course  # course.scope_path is now "org:5/course:<id>"
```

`scope_path` is the parent's path plus the object's own `<scope name>:<scope_id>` segment, derived
when read, so the stored column never needs the object's own id (which an autoincrement key only
gets on insert). `scope_id` is the record's `id` as a string; a model keyed otherwise overrides it.
An id may not contain `/`, since it would add path segments; building the path raises
`InvalidScopeObjectId`. A root-level object, whose parent scope is objectless, leaves
`parent_scope_path` as `None`. **Moving an object means rewriting the `parent_scope_path`** of it
and of everything beneath it: nothing derives it later.

Then gate routes with `require_for_object`, with a fixed string or a dependency returning the record:

```python
# Fixed id: a plugin's routes check the grant held at plugin:grader.
@router.get("/status", dependencies=[Depends(PLUGIN_USE.require_for_object(PLUGIN, "grader"))])
async def status(): ...


async def load_course(course_id: int, session: AsyncSession = Depends(get_async_session)) -> Course | None:
    return await session.get(Course, course_id)  # None for a missing course: the check denies, not 404


# The record's scope_path includes its org, so a grant at the org authorizes the edit.
@router.patch("/courses/{course_id}", dependencies=[Depends(COURSE_EDIT.require_for_object(COURSE, load_course))])
async def edit_course(course_id: int): ...
```

The returned dependency resolves the current user, checks the permission, and returns the
authenticated `User`. Put it in `dependencies=[...]` to gate a route, or inject it as a
parameter (`user: User = Depends(...)`) when the handler needs the authorized user — both
enforce the permission identically. A missing permission yields **403**.

Every 403 from these dependencies is recorded in the audit trail as a `permission.denied`
event: the caller is the actor, the target is the permission checked, and `error_detail`
names the scope (e.g. `scope=role:7`). The row is committed in its own transaction before
the 403 is raised, so it survives the request's rollback; if the write fails, the request
fails rather than returning 403. Calling `can()` or `batched_can()` directly, or the
`/permissions/can/batch` probe below, records nothing.

Code that turns down one thing a caller asked for by name, without refusing the whole request, records
the same event with `await PERMISSION.record_denial(SCOPE, scope_path)`. It writes the row the same way
and does not refuse the request; a failed write still fails the caller. A list that only leaves out what
the caller may not use records nothing.

**Check the current user's permissions** — a client (e.g. the web UI) can ask whether the
authenticated user holds permissions via `POST /api/v1/permissions/can/batch`. The body is a list of
checks, at most `MAX_PERMISSION_CHECKS` (50), each with `permission`, `scope` (required, e.g.
`global`) and an optional `scope_object_id`. The response has one result per check, in request
order. Each result repeats its check and adds `allowed` (`true` or `false`), so the same permission
can be checked at two scopes. A single check is a list of one, and `batched_can()` answers them all
from one read of the user's grants.

With `scope_object_id`, a check covers that one object. Without it, an object-bearing scope answers
whether the user holds the permission at any of its objects, the same check
`require_for_any_object()` makes for a list route:
`{"permission": "group.read", "scope": "group"}` is `true` for a grant at `global` or at any
`group:<id>`. An objectless scope answers for the scope itself. A check without a scope, an unknown
permission or scope name, or a `scope_object_id` containing `/` rejects the whole request with 422,
and no check is answered.

The probe is a convenience for gating UI, not a security boundary, since every endpoint still
enforces its own permission and returns 403.
