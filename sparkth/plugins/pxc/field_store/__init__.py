"""PXC field-persistence backends. One module per storage engine."""

from sparkth.plugins.pxc.field_store.sqlite import SqliteFieldStore

__all__ = ["SqliteFieldStore"]
