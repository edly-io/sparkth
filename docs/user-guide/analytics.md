# Analytics

If your account has the [required permission](#required-permissions), **Analytics** in the
sidebar shows how Sparkth is used.
It has three views:

- **Overview**: the period's headline figures, such as logins, active users and signups, each
  compared with the period before, and an **Activity** chart of logins and messages sent. A
  figure that has its own view links to it.
- **Logins**: sign-ins over time and by sign-in method.
- **Course authoring**: conversations, messages, the assistant's tool use, and how many document
  searches ran and the share that found nothing. If you use an online drive, it also shows how many
  documents were processed, the share that became ready to use in chat and how long that took on
  average, and why the rest weren't usable.

Pick a period at the top, or a custom range, and how to group the charts.

- All dates and times are UTC.
- The dashed line is the period before, for comparison.
- Course authoring counts are lower bounds: now and then an event is not recorded, so read them
  as "at least".

## Required permissions

| Permission | Lets you |
|---|---|
| `analytics.read` | See **Analytics** and all its views. |

The admin role has it.
