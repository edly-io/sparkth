# Sparkth

Sparkth is a free, open source, extensible, science-driven, AI-first learning platform. It is under active development by
[Edly](https://edly.io).

This repository is organized as a [Cargo workspace](https://doc.rust-lang.org/book/ch14-03-cargo-workspaces.html) with three main components:

- `mcp/`: a binary crate that runs the MCP server, responsible for creating courses from the chat UI of AI providers
- `backend/web-api/`: a binary crate that serves HTTP APIs
- `backend/app_core/`: a library crate for database access (PostgreSQL via Diesel)

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

### Building

The build guides are provided here:

1. MCP [documentation](/mcp/README.md)
2. Backend [documentation](/backend/README.md)


## Development

Build in development mode:

    cargo build

Run tests:

    cargo test

## License

This project is licensed under the MIT License — see the [LICENSE](LICENSE) file for details.
