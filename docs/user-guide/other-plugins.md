# Activities and team chat

Two plugins need setup on the server before you can use them. If either does nothing after you
turn it on in [My Plugins](plugins.md), ask your administrator.

## Activities

**Activities** lists the interactive learning activities you have built in **Create Course**,
each with a preview. The assistant can place them in a course in your LMS for you.

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
2. Choose which document sources the bot may search. Choosing none lets it search all of them.
3. In [My Plugins](plugins.md), configure the bot: its name, its greeting, the message it sends
   when it finds no answer, and an [AI key](ai-keys.md). Without a key it cannot write answers.
4. Watch **Response logs** to see the questions it gets and what it answered.

Students only need to be in your workspace, not to have a Sparkth account.

!!! note
    The team-chat app must be set up on the server before you can connect it. Ask your
    administrator.
