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

Each key in the list has its own actions:

- **Edit Config** changes its name, provider or model. **Rotate API Key** replaces the key
  itself, for example after you revoke the old one with your provider.
- The toggle turns the key off without deleting it.
- **Delete Config** removes it.

## Use the key in Compose

!!! note
    Adding a key is not enough. Open [My Plugins](plugins.md), configure Compose, and select
    the key. You can also override the key's model there.

Until you do, **Create Course** shows "Select your AI key in Compose's configuration to start
creating."
