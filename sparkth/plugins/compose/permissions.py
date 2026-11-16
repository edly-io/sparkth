"""Permissions the Compose plugin declares."""

from sparkth.lib.permissions import Permission
from sparkth.lib.permissions.scopes import USER, PermissionScope

# One conversation, named by its UUID, under its owner's user scope.
CONVERSATION = PermissionScope.create("conversation", parent=USER)

# Conversation access, checked at the conversation. Listing is checked at the listed owner's user scope,
# and starting a conversation at the caller's.
CONVERSATION_READ = Permission.create("compose.conversation.read")
CONVERSATION_WRITE = Permission.create("compose.conversation.write")
