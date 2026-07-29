# API layer

Applies to everything under `sparkth/api/`. The project-wide exception rules in the root
`CLAUDE.md` (never bare `except Exception`, always log with context) apply here too — this file
covers only what is specific to REST routes.

## Domain exceptions → HTTP responses (REST routes)

REST routes must not repeat `try/except → raise HTTPException(...)` for every domain error.
HTTP status decisions live in one API-layer mapping, not scattered through business-logic
routes.

1. **Raise HTTP-agnostic domain exceptions.** Services, engines, and plugins raise plain
   `Exception` subclasses (e.g. `RoleNotFound`); a domain exception never carries an HTTP
   status. HTTP is strictly an API-layer concern.

2. **Register the type → status mapping once**, with
   `register_exception_handler(ExcClass, status_code)` from
   [`sparkth.lib.exceptions.handlers`](../lib/exceptions/handlers.py) — core registers at
   import, a plugin from its `__init__`. `assemble_app` wires the registry onto the app at
   startup, and Starlette dispatches by walking the raised exception's `__mro__`, so a mapping
   on a base class also covers its subclasses. The route just raises the exception; the
   framework renders it as `{"detail": str(exc)}` with the mapped status.

3. **Design exceptions so the mapping is 1-to-1.** Each exception class must mean exactly one
   thing, so it maps unambiguously to a single status (`RoleNotFound` → 404,
   `RoleAlreadyExists` → 409, `RoleInUse` → 409). If one failure would need different statuses
   in different places, split it into distinct per-cause classes — do not overload one class.

4. **`try/except` in a route is the exception, not the rule.** Reach for it only when the
   status is genuinely context-dependent — the *same* domain exception must become a
   *different* HTTP status depending on the calling route. Then catch the specific type
   locally and translate to the appropriate `HTTPException` (catch-and-translate at the route
   boundary), still following the project-wide rules (log with context). A type that always maps
   to the same status must go through the registry, never an inline `try/except`.

5. **Let boundary validation reject malformed input.** Typed path/query params and request
   models turn bad input into a `422` before it reaches domain logic — do not hand-validate it
   in the route.

## Permission gating on routes

For routes that only need gatekeeping from a permission, use the `dependencies=[]` argument on the
router decorator. Do not add unused arguments to the route handler just to check permissions.
