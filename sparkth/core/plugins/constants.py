"""Constants for the plugin framework.

Internal to :mod:`sparkth.core.plugins`; nothing here is re-exported through
the :mod:`sparkth.lib.plugins` public surface.
"""

import re

# A plugin name is a kebab-case slug: it appears in URLs (``/api/v1/<name>``,
# ``/dashboard/<name>``) and is the key joining the backend plugin, its DB row,
# and its frontend counterpart.
PLUGIN_NAME_PATTERN = re.compile(r"[a-z0-9]+(-[a-z0-9]+)*")

# The name of the page where users manage their plugin settings, as the plugin errors name it.
PLUGIN_SETTINGS_PAGE_NAME = "Settings"

# The Authorization scheme the plugin access gate reads the caller's token from, compared
# against the header's scheme lowercased (RFC 7235 makes it case-insensitive).
BEARER_SCHEME = "bearer"
