# Sparkth MCP Plugin Development Guide

Welcome to the **Sparkth MCP Plugin System!**

This guide explains:

- How to create your own **tools**  
- How to register tools into the MCP server  
- How to build a full **plugin** (e.g. an LMS integration)  
- How to wire plugins into the MCP server

---

# MCP Tool 

All tools implement the `Tool` trait:

```rust
pub trait Tool: Send + Sync {
    fn name(&self) -> &str;
    fn call(&self, args: Option<Value>) -> Result<CallToolResult, ToolError>;
}
```

## How to Build a Tool
Let’s walk through creating a simple tool.

#### 1. Define the argument Struct

Suppose you want a tool to greet someone. Define its arguments:

```rust
use serde::Deserialize;

#[derive(Debug, Deserialize)]
pub struct SayHelloRequest {
    pub name: String,
}
```

#### 2. Implement the Tool Trait
```rust
pub struct SayHelloTool;

impl Tool for SayHelloTool {
    fn name(&self) -> &str {
        "say_hello"
    }

    fn call(&self, args: Option<Value>) -> Result<CallToolResult, ToolError> {
        let parsed = parse_args(
            self.name(),
            args,
            "name: String",
        )?;

        let req: SayHelloRequest =
            from_value(parsed).map_err(|_| ToolError::InvalidArgs {
                name: self.name().into(),
                args: "name: String".into(),
            })?;

        let message = format!("Hello, {}!", req.name);

        Ok(CallToolResult::success(vec![
            Content::text(message)
        ]))
    }
}

```

#### 3. Register Your Tool
Register your tool with the MCP’s tool registry:
```rust
tools.register(SayHelloTool);
```

# How to Build a Plugin
A plugin:

- Defines one or more tools
- Registers them into the MCP
- Optionally connects to external systems (like Canvas)

## Example Plugin — “My LMS”
Suppose you want to build a plugin for your custom LMS.

#### 1. Define Your Tool
`my_lms/tools.rs:`

```rust
#[derive(Debug, Deserialize)]
pub struct CreateCourseRequest {
    pub name: String,
}

pub struct CreateCourseTool;

impl Tool for CreateCourseTool {
    fn name(&self) -> &str {
        "my_lms.create_course"
    }

    fn call(&self, args: Option<Value>) -> Result<CallToolResult, ToolError> {
        let parsed = parse_args(
            self.name(),
            args,
            "name: String",
        )?;

        let req: SayHelloRequest =
            from_value(parsed).map_err(|_| ToolError::InvalidArgs {
                name: self.name().into(),
                args: "name: String".into(),
            })?;

        println!("Creating course: {}", req.name);

        Ok(CallToolResult::success(vec![
            Content::text(format!("Course '{}' created!", req.name))
        ]))
    }
}

```

#### 2. Create Plugin Setup
In `my_lms/plugin.rs` file:

```rust
pub fn my_lms_plugin_setup(tools: &mut ToolRegistry) {
    tools.register_tool(CreateCourseTool);
    println!("My LMS plugin tools registered!");
}
```

## Connect Plugins to MCP Server
In `main.rs`:

```rust
fn main() {
    let mut server = SparkthMCPServer::new();

    // setup your plugin
    my_lms_plugin_setup(&mut server.tool_registry);

    // Now your tools are available!
}
```

# Calling Your Tool
When a client sends:

```
Create a course on Programming Fundamentals
```

The server parses the request in the required format:
```json
{
  "tool_name": "create_course",
  "args": {
    "name": "Programming Fundamentals"
  }
}
```

and the calls the `dispatch` tool. The `dispatch` tool looks for the requested tool in the registry and, if found, calls it by passing the `args`.
