"""Domain exceptions raised by plugin content contributors."""


class ContentBuildError(Exception):
    """Raised by a :class:`ContentContributor`'s ``build`` when it cannot produce its block.

    A publishing tool resolves the failure through its own error contract (for example,
    Open edX's ``openedx_add_plugin_content`` returns an ``{"error": {...}}`` dict) instead of
    letting the exception propagate as a raw, unhandled failure.
    """
