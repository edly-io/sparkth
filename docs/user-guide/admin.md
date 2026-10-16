# For administrators

!!! warning "Nobody can sign up until you add an entry"
    The whitelist starts empty, and an empty whitelist blocks every sign-up, by password or
    through a sign-in provider. Add your users' emails or your organisation's domain before you invite anyone.

## Manage the whitelist

The **Admin** entry in the sidebar opens **Email Whitelist**, which decides who may create an
account.

1. Enter an email (`user@example.com`) to allow one person, or a domain (`@example.com`) to
   allow everyone with an address there.
2. Click **Add**.

![The Email Whitelist page](../img/user-guide/whitelist.png)

The table lists each entry with its value, its type (email or domain) and when it was added.
To remove one, click its trash icon and confirm. Removing an entry stops new sign-ups from it;
existing accounts keep working.

Someone who is not on the whitelist sees one of the messages in
[Signing up and signing in](account.md#common-messages).

## Accounts

There is no account screen in Sparkth. Creating accounts, granting admin rights and resetting
passwords are done on the server from the command line: see
[User management](../guides/user-management.md).

The server setting [`REGISTRATION_ENABLED`](../reference/configuration.md#registration_enabled)
turns off the sign-up form, but a sign-in provider still creates accounts for whitelisted emails.
The whitelist is what decides who can join.

## Who sees Admin and Analytics

The **Admin** entry needs whitelist access, and **Analytics** needs analytics access. The
admin role has both. See [Permissions](../guides/permissions.md) for the detail.
