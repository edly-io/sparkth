from enum import StrEnum


class EmailWhitelistPermissions(StrEnum):
    READ = "email.whitelist.read"
    CREATE = "email.whitelist.create"
    DELETE = "email.whitelist.delete"
