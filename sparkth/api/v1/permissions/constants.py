"""Constants of the permissions API."""

# The most checks one POST /permissions/can/batch request may ask.
MAX_PERMISSION_CHECKS = 50

# The most users one request may add to, or remove from, a group.
MAX_GROUP_MEMBER_CHANGES = 100

# The most users one request may give a role to, or the most assignments it may take away.
MAX_ROLE_ASSIGNMENT_CHANGES = 100
