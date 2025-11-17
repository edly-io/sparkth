# Sparkth

Sparkth is a free, open source, extensible, science-driven, AI-first learning platform. It is under active development by
[Edly](https://edly.io).

This repository is organized with the following main components:

- `sparkth_mcp/`
- `api/`
- `core/`
- `models/`

**Roadmap**:

- Native Rust API for integration of Sparkth into other applications.
- Development of a new webassembly-based standard for the creation of next-gen learning experiences.

## Installation

### Pre-built binaries

We provides binaries for macOS (x86\_64 & aarch64), Linux (x86\_64) and Windows (x86\_64). They are published automatically for every version tag (`vX.Y.Z`) on GitHub under [Releases](https://github.com/edly-io/sparkth/releases). Each archive contains:

* Platform-specific binary (`sparkth` or `sparkth.exe`)
* `.zip` and `.tar.gz` formats
* SHA-256 checksums

Download from the CLI:

```sh
export sparkth_version=$(curl -s https://api.github.com/repos/edly-io/sparkth/releases/latest | sed -n 's/.*"tag_name": "\([^"]*\)".*/\1/p')

# Linux
curl -LO -o sparkth.tar.gz https://github.com/edly-io/sparkth/releases/download/$sparkth_version/sparkth-$sparkth_version-x86_64-unknown-linux-gnu.tar.gz
# macOS arm64
curl -LO -o sparkth.tar.gz https://github.com/edly-io/sparkth/releases/download/$sparkth_version/sparkth-$sparkth_version-aarch64-apple-darwin.tar.gz
# macOS x86_64
curl -LO -o sparkth.tar.gz https://github.com/edly-io/sparkth/releases/download/$sparkth_version/sparkth-$sparkth_version-x86_64-apple-darwin.tar.gz
# Windows
curl -LO -o sparkth.zip https://github.com/edly-io/sparkth/releases/download/$sparkth_version/sparkth-$sparkth_version-x86_64-pc-windows-msvc.zip

# Decompress
# For Linux/macOS:
tar -xzf sparkth.tar.gz
# For Windows:
unzip sparkth.zip

# Set execution mode (Linux/macOS only)
chmod a+x sparkth

# Smoke test
./sparkth --help
```


## Running the MCP Server

    uv run python -m sparkth_mcp.main 

Any CLI option supported by Sparkth MCP can be appended to this command.

#### Transport mode: http / stdio

Sparkth MCP server can run in two modes, selectable via the `--transport` flag:

| Mode     | Description                                          |
| -------- | ---------------------------------------------------- |
| `stdio`  | Communicates via standard input/output streams.      |
| `http`   | Starts an HTTP server.       |

The default is `http` on host http://0.0.0.0:7727.



All common tasks are wrapped in a `Makefile` for convenience.

Just run `make` to see the full list:

```bash
$ make
Usage: make <target>

Targets:
  uv           Install uv if missing
  dev          Install dev dependencies
  lock         Update lockfile
  install      Install exact versions from lockfile
  test         Run tests
  cov          Run tests with coverage
  lint         Lint with ruff
  fix          Auto-fix + format with ruff
  build        Build package

```

## Running the API Server

To develop locally, you can run the API server with hot-reloading enabled.

1.  **Ensure dependencies are installed:**
    ```bash
    make dev
    ```

2.  **Start the server:**
    ```bash
    make start
    ```
    *This runs `uvicorn` on port 8000 with reload enabled.*

### API Documentation

Once the server is running, you can access the interactive API documentation locally:

* **Swagger UI:** [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)
    * *Best for testing endpoints interactively.*
* **ReDoc:** [http://127.0.0.1:8000/redoc](http://127.0.0.1:8000/redoc)
    * *Best for reading documentation structure.*


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
