# Sparkth

Sparkth is a free, open source, extensible, science-driven, AI-first learning platform. It is under active development by
[Edly](https://edly.io).

With Sparkth, users can create create courses from the chat UI of AI providers such as Claude or ChatGPT. Integration with these generative AI providers is achieved by the Model Context Protocol ([MCP](https://modelcontextprotocol.io/)) standard.

Features:

- MCP endpoints that make it possible to use Sparkth as an external tool in Claude/ChatGPT/Gemini.
- Course generation prompt template that follows good instructional design principles.

Roadmap:

- Filter/Event API for extensive customisation of Sparkth.
- Native Rust API for integration of Sparkth into other applications.
- Synchronization of generated course content with 3rd-party learning management systems (LMS).
- Development of a new webassembly-based standard for the creation of next-gen learning experiences.

## Requirements

- Rust ([documentation](https://doc.rust-lang.org/book/ch01-01-installation.html)):

  curl --proto '=https' --tlsv1.2 https://sh.rustup.rs -sSf | sh

- uvx, for MCP integration ([documentation](https://docs.npmjs.com/downloading-and-installing-node-js-and-npm)):

  curl -LsSf https://astral.sh/uv/install.sh | sh

## Installation

Checkout the code:

    git clone git@github.com:edly-io/sparkth.git
    cd sparkth

Build the application:

    cargo build --release

The compiled executable will be in `target/release`. Add this executable as an external tool to Claude Desktop: File 🠂 Settings 🠂 Developer 🠂 Edit Config. This will edit the Claude configuration file:

    # macOS
    ~/Library/Application\ Support/Claude/claude_desktop_config.json
    # Windows
    %APPDATA%\Claude\claude_desktop_config.json
    # Linux
    ~/.config/Claude/claude_desktop_config.json

Add the Sparkth server, such that your configuration looks like the following:

    {
      "mcpServers": {
        "Sparkth": {
          "command": "/<PATH TO SPARKTH REPOSITORY>/target/release/sparkth"
        }
      }
    }

Restart Claude Desktop. Ensure that the Sparkth tools appear in the "Search and tools" menu. Then start a new chat and generate a course:

> Use Sparkth to generate a very short course (~1 hour) on the literary merits of Hamlet, by Shakespeare.

Sparkth will generate a prompt that will help Claude generate this course.

## Usage Modes

Sparkth can run in **two modes**, selectable via the `--mode` flag:

| Mode    | Description                                          |
| ------- | ---------------------------------------------------- |
| `stdio` | Communicates via standard input/output streams.      |
| `sse`   | Starts an HTTP server with Server-Sent Events.       |

> **Note:** The default mode is `sse` if no `--mode` flag is provided.

### Running in SSE Mode

Sparkth supports running as an SSE server via the `--mode` flag:

```sh
cargo run --release -- --mode sse --host 0.0.0.0 --port 7727
```

This starts an SSE server on the given host and port with:

* `GET /` for establishing the event stream.
* `POST /message` for sending messages.

Default values:

* Host: `0.0.0.0`
* Port: `7727`
* Mode: `sse`

## Prebuilt Binaries

Sparkth provides binaries for:

* **macOS** (x86\_64 & aarch64)
* **Linux** (x86\_64)
* **Windows** (x86\_64)

These are published automatically for every version tag (`vX.Y.Z`) on GitHub under [Releases](https://github.com/edly-io/sparkth/releases). Each archive contains:

* Platform-specific binary (`sparkth` or `sparkth.exe`)
* `.zip` and `.tar.gz` formats
* SHA-256 checksums

**To download**:

```sh
curl -LO https://github.com/edly-io/sparkth/releases/download/vX.Y.Z/sparkth-vX.Y.Z-x86_64-unknown-linux-gnu.tar.gz
```

Replace with your OS/arch and version.

## Docker Image

A prebuilt Docker image for Sparkth is published automatically to **GitHub Container Registry** on each push to the `main` branch.

* **Image**: [`ghcr.io/edly-io/sparkth:latest`](https://github.com/edly-io/sparkth/pkgs/container/sparkth)

### Pull the Image

By default, the image is **private**. You must authenticate with GitHub before pulling:

```bash
echo <YOUR_GITHUB_TOKEN> | docker login ghcr.io -u <YOUR_GITHUB_USERNAME> --password-stdin

docker pull ghcr.io/edly-io/sparkth:latest
```

> **Note:** Your GitHub token must have the `read:packages` scope. You can create a token [here](https://github.com/settings/tokens).

### Run the Container

```bash
docker run -p 7727:7727 ghcr.io/edly-io/sparkth:latest
```

This starts Sparkth in **`sse` mode** (default) and binds it to port `7727`.

### Customizing the Mode

To run in a specific mode (`sse` or `stdio`), pass the `--mode` argument:

```bash
docker run -p 7727:7727 ghcr.io/edly-io/sparkth:latest --mode stdio
```

## Development

Build in development mode:

    cargo build

Run tests:

    cargo test

⚠️ Note that in stdio mode, you will need to restart Claude Desktop every time you recompile, otherwise changes will not be automatically picked up.
