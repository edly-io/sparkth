# Sparkth MCP

With Sparkth, users can create create courses from the chat UI of AI providers such as Claude or ChatGPT. Integration with these generative AI providers is achieved by the Model Context Protocol ([MCP](https://modelcontextprotocol.io/)) standard.

**Features**:

- Filter/Event API for extensive customisation of Sparkth.
- MCP endpoints that make it possible to use Sparkth as an external tool in Claude/ChatGPT/Gemini.
- Course generation prompt template that follows good instructional design principles.
- Synchronization of generated course content with 3rd-party learning management systems (LMS), such as [Canvas](https://canvas.instructure.com/).

**Tool Development Guide**:

The tool development guide can be found [here](src/plugins/README.md).

### Building

Make sure that you have the following requirements:

- Rust ([documentation](https://doc.rust-lang.org/book/ch01-01-installation.html)):

      curl --proto '=https' --tlsv1.2 https://sh.rustup.rs -sSf | sh

- uvx, for MCP integration ([documentation](https://docs.npmjs.com/downloading-and-installing-node-js-and-npm)):

      curl -LsSf https://astral.sh/uv/install.sh | sh

Checkout the code:

    git clone git@github.com:edly-io/sparkth.git
    cd sparkth/mcp

Build the application:

    cargo build --release

The compiled executable will be in `target/release`. Run Sparkth with:

    cargo run --release --

Any CLI option supported by Sparkth MCP can be appended to this command.

## Docker

A pre-built Docker image for Sparkth MCP is published automatically to the GitHub Container Registry on each push to the `main` branch.

Pull the [`ghcr.io/edly-io/sparkth:latest`](https://github.com/edly-io/sparkth/pkgs/container/sparkth) image with:

    docker pull ghcr.io/edly-io/sparkth:latest

Alternatively, build the image manually with:

    docker build -t ghcr.io/edly-io/sparkth:latest .

Then, run the Sparkth MCP server with:

    # Expose MCP server to http://localhost:7727
    docker run \
      --publish 127.0.0.1:7727:7727 \
      ghcr.io/edly-io/sparkth:latest

Any CLI option supported by Sparkth can be appended to this command.

## Usage

### Local usage

Add the `sparkth` (or `sparkth.exe`) executable as an external tool to Claude Desktop by editing the Claude configuration file:

    # macOS
    ~/Library/Application\ Support/Claude/claude_desktop_config.json
    # Windows
    %APPDATA%\Claude\claude_desktop_config.json
    # Linux
    ~/.config/Claude/claude_desktop_config.json

Add the Sparkth MCP server, such that your configuration looks like the following:

    {
      "mcpServers": {
        "Sparkth stdio": {
          "command": "/<PATH TO SPARKTH REPOSITORY>/mcp/target/release/sparkth",
          "args": ["--mode=stdio"],
        }
      }
    }

Restart Claude Desktop. Ensure that the "Sparkth stdio" tools appear in the "Search and tools" menu. Then start a new chat and generate a course:

> Use Sparkth to generate a very short course (~1 hour) on the literary merits of Hamlet, by Shakespeare.

Sparkth will generate a prompt that will help Claude generate this course.

### Production deployment

Deploying Sparkth MCP in production involves the following steps:

1. Run Sparkth MCP in SSE mode, either with Docker or a pre-built image.
2. Run an HTTPS proxy, for instance [Caddy](https://caddyserver.com/) with self-generated SSL certificates.
3. Add the Sparkth MCP server in Claude: Settings 🠂 Connectors 🠂 Add custom connector:

      Name=Sparkth SSE
      Remote MCP server URL=https://<yourdomainname.com>/

### Options

#### Transport mode: server-sent events (SSE) / stdio

Sparkth MCP server can run in two modes, selectable via the `--mode` flag:

| Mode    | Description                                          |
| ------- | ---------------------------------------------------- |
| `stdio` | Communicates via standard input/output streams.      |
| `sse`   | Starts an HTTP server with Server-Sent Events.       |

The default is `sse` on host http://0.0.0.0:7727.

This starts an SSE server on the given host and port with:

* `GET /` for establishing the event stream.
* `POST /message` for sending messages.

The `stdio` transport mode is appropriate for running with Claude locally:

    ./sparkth --mode=stdio

⚠️ Note that in stdio mode, you will need to restart Claude Desktop every time you recompile, otherwise changes will not be automatically picked up.
