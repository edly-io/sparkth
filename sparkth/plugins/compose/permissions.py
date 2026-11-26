"""Permissions the Compose plugin declares."""

from sparkth.lib.i18n import gettext_noop
from sparkth.lib.permissions import Permission
from sparkth.lib.permissions.scopes import USER, PermissionScope

# One conversation, named by its UUID, under its owner's user scope.
CONVERSATION = PermissionScope.create("conversation", parent=USER)

# The category this plugin's permissions are listed under.
_CATEGORY = gettext_noop("Compose")

# Conversation access
CONVERSATION_READ = Permission.create(
    "compose.conversation.read",
    gettext_noop("Read conversations"),
    gettext_noop("Open Compose conversations and their files."),
    _CATEGORY,
)
CONVERSATION_WRITE = Permission.create(
    "compose.conversation.write",
    gettext_noop("Write in conversations"),
    gettext_noop("Send messages and attach files."),
    _CATEGORY,
)
