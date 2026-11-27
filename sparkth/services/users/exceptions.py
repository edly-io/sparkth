from sparkth.lib.i18n import _


class UserNotFound(Exception):
    """Raised when a user referenced by id does not exist or has been deleted."""

    def __init__(self, user_id: int) -> None:
        super().__init__(_("User not found: {user_id}").format(user_id=user_id))
        self.user_id = user_id
