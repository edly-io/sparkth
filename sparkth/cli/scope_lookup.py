"""Resolve the permission scope kind a CLI command names.
Authored with LLM (Claude) assistance."""

import typer

from sparkth.lib.permissions import get_permission_scope
from sparkth.lib.permissions.exceptions import PermissionScopeNotFound
from sparkth.lib.permissions.scopes import PermissionScope
from sparkth.lib.plugins import get_plugin_loader


def resolve_scope(scope: str) -> PermissionScope:
    """Return the registered scope kind named ``scope``.

    Loads the plugins first so plugin-declared scope kinds are registered. Exits non-zero when
    the kind is unknown, so a mistyped ``--scope`` fails loudly instead of persisting or
    revoking a no-op.
    """
    get_plugin_loader()
    try:
        return get_permission_scope(scope)
    except PermissionScopeNotFound:
        typer.secho(f"Unknown scope kind: '{scope}'", fg=typer.colors.RED)
        raise typer.Exit(code=1) from None
