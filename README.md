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

## Development

Build in development mode:

    cargo build

Run tests:

    cargo test

⚠️ Note that in stdio mode, you will need to restart Claude Desktop every time you recompile, otherwise changes will not be automatically picked up.
