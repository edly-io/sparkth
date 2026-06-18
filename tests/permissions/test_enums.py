from app.permissions.enums import EmailWhitelistPermissions


def test_email_whitelist_permission_values() -> None:
    assert EmailWhitelistPermissions.READ.value == "email.whitelist.read"
    assert EmailWhitelistPermissions.CREATE.value == "email.whitelist.create"
    assert EmailWhitelistPermissions.DELETE.value == "email.whitelist.delete"


def test_members_are_strings() -> None:
    assert isinstance(EmailWhitelistPermissions.READ, str)
