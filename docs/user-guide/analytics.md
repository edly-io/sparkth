# Analytics

If your account has the [required permission](#required-permissions), **Analytics** in the
sidebar shows how Sparkth is used.
It has these views:

- **Overview**: the period's headline figures, such as logins, active users and signups, each
  compared with the period before, and an **Activity** chart of logins and messages sent. A
  figure that has its own view links to it.
- **Logins**: sign-ins over time and by sign-in method.
- **Course authoring**: conversations, messages, the assistant's tool use, and how many document
  searches ran and the share that found nothing. If you use an online drive, it also shows how many
  documents were processed, the share that became ready to use in chat and how long that took on
  average, and why the rest weren't usable.
- **Explore**: a chart built from any recorded event. Pick an event, filter by actor ID and by
  its fields' values, count events or distinct actors, break the count down by a field or by
  actor, and show it as a line, bars or a table. The page's address keeps the whole setup, so
  you can bookmark it or share the link. Events, fields and values show as recorded, by their
  raw identifiers. A link naming an event, field or value that no longer exists still opens, without
  that part, and says so.

Pick a period at the top, or a custom range, and how to group the charts.

- All dates and times are UTC.
- The dashed line is the period before, for comparison.
- Course authoring counts are lower bounds: now and then an event is not recorded, so read them
  as "at least".

## Saved views

In **Explore**, **Save view** names the current setup and saves it. Saved views are private to
you: nobody else sees them or can open them, even with the link. They're listed under
**Saved views** in the analytics menu. A view doesn't store a period, so opening one shows its
setup for the period you have selected.

With a saved view open:

- **Save** stores your changes to it.
- **Save as new** saves the current setup under a new name and leaves the original as it was.
- **Rename** gives it a new name. Each of your views needs a different name.
- **Delete** removes it. The chart stays on screen, no longer saved.

A saved view naming an event, field or value that no longer exists still opens, without that
part, and says so.

## Required permissions

| Permission | Lets you |
|---|---|
| `analytics.read` | See **Analytics** and its built-in views. |
| `user.read` | Also see and use **Explore** and your saved views. Explore names users when it breaks a count down by actor. |

The admin role has both.
