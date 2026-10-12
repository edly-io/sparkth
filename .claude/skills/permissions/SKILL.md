---
name: permissions
description: Use when adding, changing or removing a Sparkth permission, scope kind or role grant — gating a route or plugin feature on a permission, calling Permission.create or PermissionScope.create, writing a migration that grants a permission to a role, reusing an existing permission for a new action, or touching sparkth/lib/permissions. Also when deciding whether an action needs a permission of its own.
---

# Permissions

**You propose permissions. The developer decides.** This skill is how to make a proposal worth
deciding on. Everything about the system itself (scopes and cascade, roles, groups, where to
declare, how to gate a route, the audit trail) is in
[`docs/guides/permissions.md`](../../../docs/guides/permissions.md).

**Read that guide before writing any code.** Do not work from this file alone.

## The developer owns the vocabulary

A permission name is a permanent contract. `can()` matches it literally against every
`role_permission` row that grants it, the migrations that seed those grants carry it as a
literal, and the frontend mirrors it by hand. Rename it after it has been granted and every
holder loses access at once. Rename or drop it and the old rows stay behind until a data
migration cleans them up. Which roles hold it on deploy
is a privilege decision. None of that is yours.

Never declare, rename, split, merge or drop a permission or scope kind, and never grant one to
a role, on your own judgement. Put a proposal to the developer: every permission name, what
each one gates, the scope it is checked at (for a new scope kind, its parent and whether it
names an object), which roles a migration grants it to (or none), and whether the UI checks
it. Then wait for an answer.

**An unavailable developer has not delegated the decision.** Offline, in meetings, "just get
it done": the deliverable is still the proposal. Do not build the declaration, the gate or
the grant migration "ready to merge" around a name nobody agreed to. Flagging a decision you
already built is not asking.

**A proposal already written down is not a decision.** A permission named in an issue, or a
requirement that implies one ("no manual setup", "we may want a narrower group later"), is
still a proposal until the developer says to build it. Ask once, naming anything left open,
and take the answer as the decision.

**Red flags: stop and ask:**

- You are about to write `Permission.create("...")` with a name nobody gave you
- You are choosing between one permission and several (`thing.read` vs `thing.read` + `thing.export`)
- You are gating a new action on an existing permission
- You are declaring a scope kind, or choosing its parent or whether it names an object
- You are writing a migration that grants a permission to `admin` or any other role
- You are renaming or removing a declared permission
- You are reading a requirement as the answer ("no manual setup" means "grant it to admin")
- You are about to write "considered asking, decided myself"

**All of these mean: propose, then wait.** Recommending is your job; a proposal with no
recommendation is unhelpful. Deciding is not.

| Rationalization | Reality |
|---|---|
| "The developer is offline, so I'll decide and flag it" | The proposal is the deliverable. Stop there. |
| "The permission part doesn't depend on the open question" | The name, the scope and the grant are open questions. |
| "'No manual setup' means a grant migration to admin" | That hands it to every admin on deploy. Propose the grant. |
| "Splitting now is cheap, splitting later costs a migration" | That is the trade-off to put in the proposal. The choice stays theirs. |
| "It follows the resource.action pattern, so the name is obvious" | A pattern makes a name plausible, not agreed. A rename after a grant revokes it. |
| "An earlier grant migration is the template" | It shows how to grant, not that this permission should be granted. |
| "An existing permission is close enough" | Reusing it hands the new action to everyone who already holds it. |

## What the proposal must answer

Taken from the guide's *Before adding one*; answer all of them in the proposal itself:

- **Is the action already covered?** Check the declarations in `sparkth/core/permissions/__init__.py`
  and every plugin's `plugin.py`. Recommend reuse only on an exact match.
- **What does it gate?** The routes or features that check it.
- **One permission or several?** State the trade-off both ways.
- **Where is it checked?** `global`, an existing scope kind, or a new one with its parent.
- **Who holds it after deploy?** Which roles a migration grants it to, or none.
- **Does the UI check it?**

## Four rules you must not violate while building

All are explained in the guide; none is a judgement call.

- **Declare only through `.create()`, bound to a constant, imported from `sparkth.lib.permissions`.**
  A plugin declares at module level in its `plugin.py`, never in the plugin class's `__init__`:
  the class is constructed more than once, and a second declaration raises
  `ValueError: Duplicate hook item`.
- **Gate a route with the permission's dependency, never a hand-rolled check.** Use
  `dependencies=[Depends(X.require_in_global_scope())]`, `X.require(SCOPE)` for an objectless
  scope, or `X.require(SCOPE, "<path param>")` for one that names an object. A route that calls
  `can()` and raises 403 itself skips the `permission.denied` audit record.
- **Grant in a new migration, with literal strings.** Never import permission or role symbols
  into a migration, and never edit an existing one. Generate it with the `database-migrations`
  skill.
- **Keep every mirror of the vocabulary in sync.** A new permission goes in the guide's
  *Shipped with the app* table and in the frontend `PermissionName` union, which mirrors the
  vocabulary by hand.
