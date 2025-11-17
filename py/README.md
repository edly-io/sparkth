# Sparkth

Sparkth is a free, open source, extensible, science-driven, AI-first learning platform. It is under active development by
[Edly](https://edly.io).

This repository is organized as a [Cargo workspace](https://doc.rust-lang.org/book/ch14-03-cargo-workspaces.html) with three main components:

- `sparkth_mcp/`
- `api/`
- `core/`
- `models/`

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



