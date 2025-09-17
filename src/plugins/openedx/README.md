# Sparkth Plugin: Open edX Integration (Studio/LMS)

This Sparkth plugin adds first-class Open edX support to your MCP server, letting Claude (or any MCP client wired to Sparkth) authenticate against your LMS, work with Studio content (XBlocks, ContentStore), and query course structure—all via clean, typed tools behind the scenes.

## Prerequisites

### Older than Teak? Enable the Studio Content API

In **Django Admin → Waffle → Switches**, create/enable:
```
contentstore.enable_studio_content_api
```
(Required only for pre-Teak Open edX releases.)

### Endpoints & credentials you'll need

- **LMS URL** (e.g. `https://lms.example.com`)
- **Studio URL** (e.g. `https://studio.example.com`)
- **Username & Password** for an account with `staff` access


## What this plugin can do

- **Authenticate to Open edX** with username/password and **refresh tokens**
- **Validate the current user** via `/api/user/v1/me`
- **List course runs** from Studio (with pagination)
- **Create course runs** in Studio
- **Create & update XBlocks** (Problem/HTML):
    - Create in a target unit, then immediately update with OLX/HTML
    - Optional metadata (e.g., `display_name`, `weight`, `max_attempts`)
    - Optional **MCQ boilerplate** for quick single-answer problems
- **Update existing components** (Problem/HTML) with new content/metadata
- **Read a specific block** from **ContentStore** (requires locator; returns data + metadata; uses `Accept: application/json`)
- **Fetch the full course tree** via the LMS Course Blocks API (`depth=all` with helpful fields)
- **Handles auth headers** (JWT/Bearer) and returns consistent JSON payloads (including raw server responses for debugging)
