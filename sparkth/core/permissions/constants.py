"""Constants of the permissions package."""

# Joins the segments of a scope path, root first (org:5/course:123).
SCOPE_PATH_SEPARATOR = "/"

# Joins a scope name and an object id inside one scope path segment (course:123).
SCOPE_SEGMENT_SEPARATOR = ":"

# The role that can do everything, shipped with Sparkth.
ADMIN_ROLE = "admin"

# The role every account holds at its own user scope.
SPARKTH_USER_ROLE = "sparkth_user"

# The role every account holds at global, letting it use every plugin.
PLUGIN_USER_ROLE = "plugin_user"

# The roles every account is given when it is created.
DEFAULT_ROLES = frozenset({SPARKTH_USER_ROLE, PLUGIN_USER_ROLE})
