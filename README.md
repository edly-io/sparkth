# Sparkth

Sparkth is a free, open source, extensible, science-driven, AI-first learning platform. It is under active development by 
[Arbisoft](https://arbisoft.com). 


## Usage
In Sparkth v1.0, we will enable users to create courses from the chat UI of AI providers such as Claude or ChatGPT.

Integration with AI providers will be done via [MCP](https://modelcontextprotocol.io/).

In this first iteration, Sparkth users are course authors, who might not necessarily be instructional design experts. Users will leverage the combined strengths of LLMs and Sparkth to create courses.

### Use case #1: AI guidelines Course Creation
1. Enable Sparkth MCP server in the Claude settings. MCP should be available for users of Claude Desktop even in the free version. Follow these steps to enable MCP.

2. Launch a new chat for course creation: 
> **User**: generate an intro-level course on the ethical use of AI.
>
> **Claude**: \<queries the Sparkth MCP to fetch a good prompt for course creation. This prompt includes good principles of instructional design to optimize student learning>
>
> **Claude**: \<generate a course outline and content, formatted as markdown>
>
> **User**: split chapter 2 into multiple sections, to have smaller units of learning. Conclude chapter 3 with a project that makes use of Replit.
>
> **Claude**: \<updates the course content according to spec>
>
> **User**: this looks good to me. Publish this course on my Open edX instance. The LMS url is http://sandbox.openedx.edly.io. My credentials are: username=admin password=admin

## How to Set Up

### Clone the Repository
Navigate to your desired directory and clone the repository:

```bash

# Clone using HTTPS
git clone https://github.com/edly-io/sparkth.git

# Or clone using SSH (if you have SSH keys set up)
git clone git@github.com:edly-io/sparkth.git

# Navigate into the project directory
cd sparkth

```

In the project directory, you should see:

* `Cargo.toml` - Sparkth manifest file (dependencies, metadata)
* `Cargo.lock` - Dependency lock file (don't modify manually)
* `src/` - Source code directory
* `README.md` - Sparkth documentation

### Install Dependencies
Cargo will automatically download and compile dependencies:

```bash
cargo build
```

For a release build (optimized):

```bash 
cargo build --release
```

Run tests to verify everything works

```bash
cargo test
```

If you have compiled in release mode, it builds a standard input/output Sparkth MCP server binary at `target/release`.

We can test the server from an existing MCP host, Claude for Desktop.

## Test the Server with Claude for Desktop

### Install Claude for Desktop
First, make sure you have Claude for Desktop installed. [Install the latest version from here](https://claude.ai/download). If you already have Claude for Desktop, make sure it’s updated to the latest version.

### Configuration
We’ll need to configure Claude for Desktop for whichever MCP servers you want to use. To do this, we will update the Claude for Desktop App configuration. Open your `claude_desktop_configuration.json` file in a text editor, making sure to create the file if it doesn’t exist.

For example, if you have [VS Code](https://code.visualstudio.com/) installed:

#### MacOS/Linux

```bash
code ~/Library/Application\ Support/Claude/claude_desktop_config.json
```

#### Windows

```powershell
code $env:AppData\Claude\claude_desktop_config.json
```

We will then add our server in the mcpServers key. In this case, we’ll add our Sparkth MCP server like so:

#### MacOS/Linux
```
{
  "mcpServers": {
    "sparkth": {
      "command": "/ABSOLUTE/PATH/TO/PARENT/FOLDER/target/release/sparkth",
      "args": []
    }
  }
}
```

#### Windows
```
{
  "mcpServers": {
    "sparkth": {
      "command": "/ABSOLUTE/PATH/TO/PARENT/FOLDER/target/release/sparkth.exe",
      "args": []
    }
  }
}
```

> **NOTE:** Make sure you pass in the absolute path to your server.

This tells Claude for Desktop:

1. There's an MCP server named `sparkth`
2. To launch it by running `./ABSOLUTE/PATH/TO/PARENT/FOLDER/target/release/sparkth` on MacOS/Linux and `./ABSOLUTE/PATH/TO/PARENT/FOLDER/target/release/sparkth.exe` on Windows.

**Ensure that the MCP UI elements appear in Claude Desktop.** The MCP UI elements will only show up in Claude for Desktop if at least one server is properly configured. 

It may require to restart Claude for Desktop.

## Test with commands

**Once Claude Desktop is running,** try chatting:

```
Create a 3-hour course on "Rust Programming for Beginners".
```
