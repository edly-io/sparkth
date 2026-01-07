# Sparkth

Sparkth is a free, open source, extensible, science-driven, AI-first learning platform. It is under active development by
[Edly](https://edly.io).

This repository is organized with the following main components:

- `app/mcp/` - MCP server implementation
- `app/api/` - REST API endpoints
- `app/core_plugins/` - Core plugins (OpenEdX, Canvas)
- `app/plugins/` - Plugin system
- `frontend/` - Next.js frontend application

## Public Endpoints

Sparkth is hosted at [https://sparkth.edly.space](https://sparkth.edly.space) with the following endpoints:

| Endpoint | URL |
| -------- | --- |
| MCP Server | https://sparkth.edly.space/ai/mcp |
| REST API | https://sparkth.edly.space/api/ |
| Swagger UI | https://sparkth.edly.space/docs |
| ReDoc | https://sparkth.edly.space/redoc |

## Installation

### Prerequisites

- Python 3.14
- [uv](https://docs.astral.sh/uv/) (recommended) or pip

### Setup

1. Clone the repository:
   ```bash
   git clone https://github.com/edly-io/sparkth.git
   cd sparkth
   ```

2. Install dependencies:
   ```bash
   make dev
   ```

## Running the MCP Server (Docker)

To run the MCP server in Docker:

    make dev.up

### Transport mode: http / stdio

Sparkth MCP server can run in two modes, selectable via the `--transport` flag:

| Mode     | Description                                          |
| -------- | ---------------------------------------------------- |
| `stdio`  | Communicates via standard input/output streams.      |
| `http`   | Starts an HTTP server.       |

The default is `http` on host http://0.0.0.0:7727.

## Running the API Server

To develop locally, you can run the API server with hot-reloading enabled.

1.  **Ensure dependencies are installed:**
    ```bash
    make dev
    ```

2.  **Start the server:**
    ```bash
    make dev.up
    ```
    or
    ```bash
    make up
    ```

### Local MCP Endpoint

When running the API server locally, the MCP server is available at:

```
http://127.0.0.1:8000/ai/mcp
```

This allows Claude and other MCP-compatible clients to connect to the MCP server via HTTP.

### API Documentation

Once the server is running, you can access the interactive API documentation locally:

* **Swagger UI:** [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)
    * *Best for testing endpoints interactively.*
* **ReDoc:** [http://127.0.0.1:8000/redoc](http://127.0.0.1:8000/redoc)
    * *Best for reading documentation structure.*

## Running the Frontend

The frontend is a [Next.js](https://nextjs.org) application located in the `frontend/` directory.

### Development (with hot reload)

```bash
make frontend
```

Open [http://localhost:3000](http://localhost:3000) in your browser.

### Production Build

Build the frontend as static files (exported to `frontend/out/`):

```bash
make frontend.build
```

The static files are automatically served by FastAPI when you run `make up` or `make dev.up`.

### Feature Flags
`REGISTRATION_ENABLED`

- Type: `boolean (true / false)`

- Default: `false`

- Location: `.env` file

**Description**:

Controls whether new user registration is enabled on the frontend.

- If `REGISTRATION_ENABLED=true`, users can sign up via the frontend.

- If `REGISTRATION_ENABLED=false`, the registration form is disabled, preventing new user creation.

Example `.env` entry:

```
# Enable new user registration
REGISTRATION_ENABLED=true
```

**Notes**:

Changing this flag does not affect existing users.

Make sure to run `make dev.up` after changing the `.env` variable to apply the new setting.

## Integrating with Claude Desktop

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

## Makefile

All common tasks are wrapped in a `Makefile` for convenience.

Just run `make` to see the full list:

```bash
$ make
Usage: make <target>

Targets:
  uv              Install uv if missing
  dev             Install dev dependencies
  lock            Update lockfile
  install         Install exact versions from lockfile
  test            Run tests
  cov             Run tests with coverage
  lint            Lint with ruff
  fix             Auto-fix + format with ruff
  build           Build package
  frontend        Run frontend dev server (hot reload)
  frontend.build  Build frontend (static export)

```

## User Management Commands
### Create User

Create a new user account. If password is not provided via flag, you'll be prompted to enter it securely.

    make create-user -- --username john --email john@example.com --name "John Doe"

#### Using short flags
    make create-user -- -u john -e john@example.com -n "John Doe"

#### Create superuser
    make create-user -- --username admin --email admin@example.com --name "Admin User" --superuser

#### Provide password directly
    make create-user -- -u john -e john@example.com -n "John Doe" --password "SecurePass123"

##### Options:
- `--username, -u`: Username (required)
- `--email, -e`: Email address (required)
- `--name, -n`: Full name (required)
- `--password, -p`: Password (optional, will prompt if not provided)
- `--superuser, -s`: Create as superuser (optional, default: false)


### Reset Password
Reset a user's password.

    make reset-password -- --username john

#### Using short flag
    make reset-password -- -u john

#### Provide password directly
    make reset-password -- -u john -p "NewSecurePass123"
    make reset-password -- --username john --password "NewSecurePass123"

##### Options:
- `--username, -u`: Username (required)
- `--password, -p`: New password (optional, will prompt if not provided)


## License

This project is licensed under the MIT License — see the [LICENSE](LICENSE) file for details.
