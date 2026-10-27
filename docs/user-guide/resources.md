# Resources

**Resources** holds the files you import from an online drive, so the course assistant can use
them as source material. See [Supported integrations](index.md#supported-integrations) for the
drives Sparkth connects to.

Until you turn on a drive plugin in [Settings](plugins.md), the page shows
"No plugins connected".

## Connect your drive

1. Open **Resources** from the sidebar.
2. Click the connect button for your drive (for example **Connect Google Drive**) and approve
   access in the window that opens.
3. The page shows "Connected as" followed by the account you connected.

!!! note
    If connecting fails, the server may not be set up for that drive yet. Ask your
    administrator.

## Sync a folder

1. Click **Sync Folder**.
2. Choose a folder in the picker.

Its files appear in the list, each with a status.

## What the status means

| Status | Meaning |
|---|---|
| **Pending**, **Queued** | Waiting its turn. |
| **Syncing** | Being copied from your drive. |
| **Indexing** | Being prepared for the assistant. |
| **Indexed** | Ready for the assistant to use. |
| **Sync Failed**, **Failed** | Something went wrong. Try again; if it keeps failing, ask your administrator. |

## Download, delete, disconnect

Each file can be downloaded or deleted from Sparkth (deleting here does not touch the file in
your drive). **Disconnect** unlinks your drive account.
