# Sparkth

Sparkth is a free, open source, extensible, science-driven, AI-first learning platform. It is under active development by
[Edly](https://edly.io).

## Public Endpoints

Sparkth is hosted at [https://sparkth.edly.space](https://sparkth.edly.space) with the following endpoints:

| Endpoint | URL |
| -------- | --- |
| MCP Server | https://sparkth.edly.space/ai/mcp |
| REST API | https://sparkth.edly.space/api/ |
| Swagger UI | https://sparkth.edly.space/docs |
| ReDoc | https://sparkth.edly.space/redoc |

## Documentation

The published documentation is at **[edly-io.github.io/sparkth](https://edly-io.github.io/sparkth/)**.
It covers configuration, user management, the backend and frontend plugin guides, the
permissions model, and the Python API reference generated from the code's docstrings.

To build it locally with mkdocs:

```bash
make docs        # build the site to site/
make docs.serve  # live-preview at http://127.0.0.1:8000
```

The REST API is served interactively by the running backend at `/docs` (Swagger) and
`/redoc`.

## Development

### Prerequisites

- Python 3.14
- [uv](https://docs.astral.sh/uv/)
- [bun](https://bun.sh/)

### Setup

1. Clone the repository:
   ```bash
   git clone https://github.com/edly-io/sparkth.git
   cd sparkth
   ```

2. Install backend and frontend dependencies:
   ```bash
   make backend.install.dev
   make frontend.install.dev
   ```

3. Install git hooks:
   ```bash
   make backend.install.dev.githooks
   ```

### Running the app

Start dependent services:

    make services.up

Apply migrations:

    make migrations

Start backend service:

    make backend.up.dev

In a separate terminal, start the frontend service (with hot-reload):

    make frontend.up.dev

Access the app at http://localhost:3000.

`.env` is committed with working dev defaults and works out of the box.
For sensitive credentials (Google OAuth, Slack), create a `.env.local` file — see the comments inside `.env` for the variables to add there. `.env.local` takes precedence over `.env`.


### End-to-end tests

Playwright end-to-end tests live in `frontend/tests/`. They run against their own
ephemeral SQLite database, created fresh and deleted on every run, so they never
touch your dev Postgres data. The run starts and stops a throwaway backend (on
port 7727) and the frontend for you.

Install the browsers once:

    make test.e2e.install

Then, with the backing services up (`make services.up`, for Mailpit and Redis)
and your dev backend stopped (the run owns port 7727):

    make test.e2e            # headless
    make test.e2e.ui         # interactive UI mode

### Local MCP Endpoint

The MCP server is served over HTTP by the running backend. When running the API server
locally, it is available at:

```
http://127.0.0.1:7727/ai/mcp
```

This allows Claude and other MCP-compatible clients to connect to the MCP server via HTTP.

### API Documentation

Once the server is running, you can access the interactive API documentation locally:

* **Swagger UI:** [http://127.0.0.1:7727/docs](http://127.0.0.1:7727/docs)
    * *Best for testing endpoints interactively.*
* **ReDoc:** [http://127.0.0.1:7727/redoc](http://127.0.0.1:7727/redoc)
    * *Best for reading documentation structure.*

### Integrating with Claude Desktop

The Sparkth MCP server is served over HTTP by the running backend at `/ai/mcp`
(e.g. `http://127.0.0.1:7727/ai/mcp`). Start the backend first (`make backend.up.dev`),
then bridge Claude Desktop to it with [`mcp-remote`](https://www.npmjs.com/package/mcp-remote).

Edit the Claude configuration file:

```
# macOS
~/Library/Application\ Support/Claude/claude_desktop_config.json
# Windows
%APPDATA%\Claude\claude_desktop_config.json
# Linux
~/.config/Claude/claude_desktop_config.json
```

Add the Sparkth MCP server configuration:
```json
{
  "mcpServers": {
    "Sparkth": {
      "command": "npx",
      "args": [
        "mcp-remote",
        "http://127.0.0.1:7727/ai/mcp"
      ]
    }
  }
}
```

> Note: You may need to put the full path to the `npx` executable in the command field. You can get this by running `which npx` on macOS/Linux or `where npx` on Windows.

Restart Claude Desktop. Ensure that the "Sparkth" tools appear in the "Search and tools" menu. Then start a new chat and generate a course:

> Use Sparkth to generate a very short course (~1 hour) on the literary merits of Hamlet, by Shakespeare.

Sparkth will generate a prompt that will help Claude generate this course.

## Production

Build the Docker image:

```bash
make docker.build
```

Convert the development services from docker-compose.yml to a production setup and add the Sparkth application to the list of services:

    sparkth:
        image: ghcr.io/edly-io/sparkth:latest
        restart: unless-stopped
        env_file:
            - .env
            - .env.local
        depends_on:
            db:
                condition: service_healthy
            redis:
                condition: service_healthy

## Configuration

Runtime configuration is via environment variables in `.env` (committed dev defaults) and
`.env.local` (git-ignored overrides); restart the backend after changing them. See the
[configuration guide](docs/guides/configuration.md) for how to set and update values, the
[configuration reference](docs/reference/configuration.md) for the variables and feature
flags such as `REGISTRATION_ENABLED`, and the
[user management guide](docs/guides/user-management.md) for creating users and resetting
passwords.

## Audit Trail

Sparkth keeps an append-only audit trail of security-relevant and AI actions: who did what, when,
from where, and with what effect. The implementation lives in `sparkth/core/audit/` with its public
API in `sparkth/lib/audit/`; unlike analytics (best-effort), audit writes are fail-closed, so a
mutating or AI action whose audit record cannot be written does not proceed. Every AI tool
execution, on every surface (the MCP server, chat, RAG), is recorded as a `tool.invoked` event
committed before the handler runs plus a `tool.completed` or `tool.failed` outcome event, with
redacted arguments and the model identity that drove the call.

## Analytics Event Schemas

Analytics events are validated against **versioned schemas** before they are stored. Each
schema is a self-describing `AnalyticsEventSchema` subclass that declares its own
`event_type` string and integer `version`, and is registered on the **`ANALYTICS_EVENTS`**
hook — the single source of truth the emission gateway resolves against. This mirrors the
permission vocabulary above: declare in code at import time, no separate store and no startup
drain. Import everything from `sparkth.lib.analytics`, never from `sparkth.core.analytics.*` directly.

### Declaring an event schema

Core events are declared in `sparkth.core.analytics`; a plugin declares its own from its
`__init__` with `register_event_schema(self, MyEvent)` — the analytics analog of
`Permission.create()`.

```python
from sparkth.lib.analytics import AnalyticsEventSchema, register_event_schema

class CourseCompleted(AnalyticsEventSchema):
    event_type = "mycourseplugin.course_completed"  # namespaced under the plugin name
    version = 1

    learner_id: str
    course_id: str

# from the plugin's __init__:
register_event_schema(self, CourseCompleted)
```

`register_event_schema` enforces three guards at import time, so a misconfigured plugin fails
fast at startup instead of at first emit:

- **Namespace** — `event_type` must be prefixed with the plugin's name, else
  `EventNamespaceError`. This stops a plugin from squatting a core event name or another
  plugin's namespace.
- **Collision** — any class claiming an already-registered `(event_type, version)` raises
  `DuplicateEventTypeError`. Registration is not idempotent: re-registering the *same* class
  is fatal too.
- **Identity** — a schema missing `event_type`/`version` raises `TypeError`.

> Always declare via `register_event_schema`, not by calling `ANALYTICS_EVENTS.add_item`
> directly — the registration function is what applies the namespace guard. Core events (which
> carry no plugin prefix) are seeded directly in `sparkth.core.analytics`.

### Emitting an event

All events are emitted server-side through `ingest_event`, which resolves the schema by
`(event_type, version)`, validates the payload against it, and lands one immutable row in the
analytics database:

```python
from sparkth.lib.analytics import ingest_event

await ingest_event(
    session, "mycourseplugin.course_completed", 1,
    {"learner_id": "u1", "course_id": "c1"}, actor_id=str(user.id),
)
```

Resolve a registered schema by identity with `get_event_schema(event_type, version)` (raises
`UnknownEventTypeError` if none is registered).

## Contributing

Contributions are welcome. Open a pull request against `main` and a maintainer will take a look.

### Requesting an automated code review

This repository has an automated code review powered by Claude. To request a review on your pull request, post a comment containing `@claude-review` on the PR. The workflow runs on demand only (it does not run automatically on every push), so use the mention whenever you want a fresh pass, for example after pushing new commits.

## License

This project is licensed under the MIT License — see the [LICENSE](LICENSE) file for details.
