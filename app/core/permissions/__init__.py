from app.core.permissions.hooks import PERMISSIONS


class Permission:
    def __init__(self, name: str) -> None:
        self.name = name

    @classmethod
    def create(cls, name: str) -> "Permission":
        permission = cls(name)
        PERMISSIONS.add_item(permission)
        return permission

    # TODO: Weigh in the pros and cons for these methods
    # defered to a later PR.
    # def require(self):
    #     ...

    # def require_in_scope(self, permisson_scope: str, scope_object_id: str):
    #     ...


# Core Permissions shipped with the application.

# The email-whitelist permissions gate the registration email whitelist.
EMAIL_WHITELIST_READ = Permission.create("email.whitelist.read")
EMAIL_WHITELIST_CREATE = Permission.create("email.whitelist.create")
EMAIL_WHITELIST_DELETE = Permission.create("email.whitelist.delete")
