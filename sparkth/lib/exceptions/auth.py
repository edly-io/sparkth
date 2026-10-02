"""Domain exceptions raised when code asks who the authenticated caller is."""


class NoAuthenticatedUser(Exception):
    """Raised when no authenticated user is bound to the running request.

    The REST routes bind one through ``get_current_user``. The ``/ai/mcp`` surface
    authenticates no one, so a tool that needs its caller raises this there, and the MCP
    client sees it as a tool error.
    """
