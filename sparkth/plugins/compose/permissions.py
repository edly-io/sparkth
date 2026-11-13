"""Permissions the Compose plugin declares."""

from sparkth.lib.permissions import Permission

# Conversation access, checked at the user scope of the conversation's owner.
CONVERSATION_READ = Permission.create("compose.conversation.read")
CONVERSATION_WRITE = Permission.create("compose.conversation.write")
