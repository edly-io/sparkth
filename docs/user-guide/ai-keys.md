# AI keys

Compose and the Slack TA Bot call an AI provider (such as OpenAI) to write their answers.
They use an API key that you add to Sparkth and that only your account can use.

## Add a key

1. Open **AI Keys** from the sidebar.
2. Click **New Config** (or **Create Your First Config** if you have none yet).
3. Give the key a name you will recognise, choose the provider and the model, and paste your
   API key.
4. Click **Create Config**.

## Change, rotate, turn off or delete a key

Each key in the list has a toggle, a pencil and a trash icon:

- The toggle turns the key off without deleting it.
- The pencil opens **Edit Config**, where you change the key's name or model. The provider is
  fixed once the key is created. To replace the key itself, for example after you revoke the
  old one with your provider, click **Rotate Key** in the same dialog and paste the new key.
- The trash icon deletes the key, after you confirm.

## Use the key in Compose

!!! note
    Adding a key is not enough. Open [My Plugins](plugins.md), configure Compose, and select
    the key. You can also override the key's model there.

Until you do, sending a message in **Create Course** shows "Select your AI key in Compose's
configuration to start creating." with a link to the plugin settings.
