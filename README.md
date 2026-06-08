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

## Guides
- [Backend Plugin Implementation](./app/plugins/PLUGIN_GUIDE.md)
- [Frontend Plugin Implementation](./frontend/README.md)

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


### Transport mode: http / stdio

Sparkth MCP server can run in two modes, selectable via the `--transport` flag:

| Mode     | Description                                          |
| -------- | ---------------------------------------------------- |
| `stdio`  | Communicates via standard input/output streams.      |
| `http`   | Starts an HTTP server.       |

The default is `http` on host http://0.0.0.0:7727.


### Local MCP Endpoint

When running the API server locally, the MCP server is available at:

```
http://127.0.0.1:8000/ai/mcp
```

This allows Claude and other MCP-compatible clients to connect to the MCP server via HTTP.

### API Documentation

Once the server is running, you can access the interactive API documentation locally:

* **Swagger UI:** [http://127.0.0.1:7727/docs](http://127.0.0.1:7727/docs)
    * *Best for testing endpoints interactively.*
* **ReDoc:** [http://127.0.0.1:7727/redoc](http://127.0.0.1:7727/redoc)
    * *Best for reading documentation structure.*

### Integrating with Claude Desktop

Add the Sparkth MCP server to Claude Desktop by editing the Claude configuration file:

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
    "Sparkth stdio": {
      "command": "uv",
      "args": [
        "--directory",
        "/<PATH TO SPARKTH REPOSITORY>/sparkth",
        "run",
        "-m",
        "app.mcp.main",
        "--transport=stdio"
      ]
    }
  }
}
```

> Note: You may need to put the full path to the `uv` executable in the command field. You can get this by running `which uv` on macOS/Linux or `where uv` on Windows.

Restart Claude Desktop. Ensure that the "Sparkth stdio" tools appear in the "Search and tools" menu. Then start a new chat and generate a course:

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

### Feature flags

The application is configured via environment variables that are defined in the `.env` file. This file contains values that are suitable for development. In production, create a `.env.local` file to override these values.

Make sure to restart the backend (`make backend.up.dev`) after changing the configuration to apply the new settings.

#### `REGISTRATION_ENABLED`

- Type: `boolean (true / false)`
- Default: `false`

Controls whether new user registration is enabled on the frontend.

- If `REGISTRATION_ENABLED=true`, users can sign up via the frontend.
- If `REGISTRATION_ENABLED=false`, the registration form is disabled, preventing new user creation.

Note that changing this flag does not affect existing users.

### User Management

Create a new user account:


    make create-user -- --username john --email john@example.com --name "John Doe"
    # Using short flags
    make create-user -- -u john -e john@example.com -n "John Doe"

If password is not provided via flag, you'll be prompted to enter it securely.

Create superuser:

    make create-user -- --username admin --email admin@example.com --name "Admin User" --superuser

Provide password directly:

    make create-user -- -u john -e john@example.com -n "John Doe" --password "SecurePass123"

Options:

- `--username, -u`: Username (required)
- `--email, -e`: Email address (required)
- `--name, -n`: Full name (required)
- `--password, -p`: Password (optional, will prompt if not provided)
- `--superuser, -s`: Create as superuser (optional, default: false)

Reset a user's password:

    make reset-password -- --username john
    # Using short flag
    make reset-password -- -u john
    # Provide password directly
    make reset-password -- -u john -p "NewSecurePass123"
    make reset-password -- --username john --password "NewSecurePass123"

Options:

- `--username, -u`: Username (required)
- `--password, -p`: New password (optional, will prompt if not provided)

## Contributing

Contributions are welcome. Open a pull request against `main` and a maintainer will take a look.

### Requesting an automated code review

This repository has an automated code review powered by Claude. To request a review on your pull request, post a comment containing `@claude-review` on the PR. The workflow runs on demand only (it does not run automatically on every push), so use the mention whenever you want a fresh pass, for example after pushing new commits.

## License

This project is licensed under the MIT License — see the [LICENSE](LICENSE) file for details.
