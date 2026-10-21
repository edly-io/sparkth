"""Constants for the Open edX plugin."""

# The plugin's registered name, and so the key a content contributor registers its Open edX
# builder under.
OPENEDX_PLUGIN_NAME = "open-edx"

# Cache key prefix of a user's Open edX access token; the key is "<prefix>:<sparkth user id>".
OPENEDX_ACCESS_TOKEN_CACHE_PREFIX = "openedx:access-token"

# Seconds before Open edX's own expiry at which a cached access token expires.
OPENEDX_ACCESS_TOKEN_TTL_MARGIN_SECONDS = 60
