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


## License

This project is licensed under the MIT License — see the [LICENSE](LICENSE) file for details.
