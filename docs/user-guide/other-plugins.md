# Activities and team chat

Two plugins need setup on the server before you can use them. If either does nothing after you
turn it on in [Settings](plugins.md), ask your administrator.

## Activities

**Activities** lists the interactive learning activities you have built in **Compose**,
each with a preview. The assistant can place them in a course in your LMS for you.

An activity shows **Placed** once it has been put in a course, and the mark stays even if the
course later drops it. **Delete** asks you to confirm first. Deleting a placed activity breaks it
in any course that still holds it, and learners lose their answers. A delete cannot be undone.

!!! note
    Activities need setup on the Sparkth server and in your LMS, and not every LMS supports
    them. If the page is empty, or learners see nothing in the course, ask your administrator.

## Team-chat bot

The team-chat bot answers student questions in your team-chat workspace, using the documents
you have synced into [Resources](resources.md). See
[Supported integrations](index.md#supported-integrations) for the team-chat tools Sparkth
connects to.

1. Open the bot's page from the sidebar (for example **Slack TA Bot**) and click its connect
   button (for example **Connect Slack**) to connect your workspace.
2. In [Settings](plugins.md), configure the bot: its name, its greeting, the message it sends
   when it finds no answer, the documents it may search, and an [AI key](ai-keys.md). Without a
   key it cannot write answers.
3. Watch **Response logs** to see the questions it gets and what it answered.

The bot reads at most five documents for each question, unless your administrator changes the
limit. It takes the ones you synced earliest: from the documents you picked, or from all of them
if you picked none. So pick the documents that matter most.

Students only need to be in your workspace, not to have a Sparkth account.

!!! note
    The team-chat app must be set up on the server before you can connect it. Ask your
    administrator.
