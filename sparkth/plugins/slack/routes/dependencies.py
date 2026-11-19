"""FastAPI dependencies for Slack route handlers.

Dependencies here are injected via ``Depends()`` by route handlers.
"""

from sparkth.lib.permissions import PLUGIN_USE
from sparkth.lib.permissions.scopes import PLUGIN
from sparkth.plugins.slack.constants import SLACK_PLUGIN_NAME

# Gates every Slack route a signed-in user calls, bar the OAuth callback and the events webhook, on the caller
# being allowed to use Slack.
require_slack_use = PLUGIN_USE.require_for_object(PLUGIN, SLACK_PLUGIN_NAME)
