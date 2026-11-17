"""Resolve and check the permission scope a CLI command names.
Authored with LLM (Claude) assistance."""

import typer

from sparkth.lib.permissions import get_permission_scope
from sparkth.lib.permissions.exceptions import PermissionScopeNotFound
from sparkth.lib.permissions.scopes import PLUGIN, PermissionScope
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


def validate_scope_object(permission_scope: PermissionScope, scope_object_id: str | None) -> None:
    """Exit non-zero when a ``plugin`` scope names a plugin that is not loaded.

    A mistyped plugin name would store a grant that reaches no plugin. Only the ``plugin`` scope is
    checked; any other scope kind passes with the object id as given.
    """
    if permission_scope is not PLUGIN or scope_object_id is None:
        return
    loaded = [name for name, _ in get_plugin_loader().get_loaded_plugins()]
    if scope_object_id not in loaded:
        typer.secho(
            f"Unknown plugin: '{scope_object_id}'. Loaded plugins: {', '.join(loaded)}",
            fg=typer.colors.RED,
        )
        raise typer.Exit(code=1)
