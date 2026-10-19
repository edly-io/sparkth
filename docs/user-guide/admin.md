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

<!-- TODO: describe the profile page once Sparkth has one. -->
<!-- TODO: describe role management and permission assignment once they have a screen. -->

Sparkth has no screen for managing accounts yet. To create an account, give someone admin
rights or reset a password, ask whoever runs your Sparkth server.

## Required permissions

**Admin** opens **Email Whitelist**, which needs the whitelist permissions:

| Permission | Lets you |
|---|---|
| `email.whitelist.read` | See the whitelist. |
| `email.whitelist.create` | Add an entry. |
| `email.whitelist.delete` | Remove an entry. |

The admin role has all three.
