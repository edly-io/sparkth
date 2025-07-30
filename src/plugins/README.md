# Sparkth MCP Tools Development Guide

This guide provides a walkthrough for creating custom tools and integrating them into the Sparkth MCP (Model Context Protocol) server.

## Overview

The Sparkth MCP server uses a modular tool system where each tool is:
- Defined as a method in an implementation block
- Automatically registered through the `tool_router` macro
- Integrated into the main server router 

## Creating Your First Tool

### Step 1: Set Up the Module Structure

Create a new module file in the `src/tools/` directory:

```bash
touch src/tools/my_lms_tools.rs
```

Add your module in `src/tools/mod.rs`:

```rust
pub mod my_lms_tools;
```

### Step 2: Define the Tool Router

In your `my_lms_tools.rs` file, create the basic structure:

```rust
use rmcp::{tool, tool_router};
use crate::server::mcp_server::SparkthMCPServer;

#[tool_router(router = my_lms_tools_router, vis = "pub")]
impl SparkthMCPServer {}
```

**Tool Router Configuration:**

| Field  | Type       | Description                                                              |
|--------|------------|--------------------------------------------------------------------------|
| router | Ident      | Name of the generated router function (defaults to `tool_router`)       |
| vis    | Visibility | Visibility modifier for the router function (defaults to private)       |

The `vis = "pub"` parameter is important as we need to combine multiple routers in the main server.

### Step 3: Implement Your Tool

Add a tool method within the implementation block. Every tool must be marked with the `#[tool]` attribute:

```rust
use rmcp::{
    ErrorData,
    model::{CallToolResult, Content},
    tool, tool_router
};
use crate::server::mcp_server::SparkthMCPServer;

#[tool_router(router = my_lms_tools_router, vis = "pub")]
impl SparkthMCPServer {
    
    #[tool]
    pub fn greet(&self) -> Result<CallToolResult, ErrorData> {
        let greeting = String::from("Hello from Sparkth MCP!");
        Ok(CallToolResult::success(vec![Content::text(greeting)]))
    }
}
```

**Note**
- To return from the tool, return type should be `Result<CallToolResult, ErrorData>`
- Use `CallToolResult::success()` for successful operations



To add description to your tool, we can use tool attributes:

```rust

#[tool(description = "A simple greeting tool that returns a friendly message.")]
pub fn greet(&self) -> Result<CallToolResult, ErrorData> {
    let greeting = String::from("Hello from Sparkth MCP!");
    Ok(CallToolResult::success(vec![Content::text(greeting)]))
}

```

You can read more about the tool attributes [here](https://docs.rs/rmcp/latest/rmcp/attr.tool.html).


### Step 4: Add Tool Parameters

For tools that accept parameters, we must define a struct that implements `serde::Deserialize` and `schemars::JsonSchema`:


```rust
use serde::Deserialize;
use schemars::JsonSchema;

#[derive(Deserialize, JsonSchema)]
struct ToolParams {
    pub name: String,
}

```

Update your tool function arguments to use the `Parameters` extractor.

```rust
use rmcp::{
    ErrorData,
    handler::server::tool::Parameters,
    model::{CallToolResult, Content},
    tool, tool_router
};

#[tool_router(router = my_lms_tools_router, vis = "pub")]
impl SparkthMCPServer {
    
    #[tool(description = "A simple greeting tool that returns a friendly message.")]
    pub fn greet(
        &self,
        Parameters(ToolParams { name }): Parameters<ToolParams>,
    ) -> Result<CallToolResult, ErrorData> {
        let greeting = format!("Hello {name} from Sparkth MCP!");
        Ok(CallToolResult::success(vec![Content::text(greeting)]))
    }
}
```

### Step 5: Test Your Tools

Create a simple test in the same module to ensure your tool works correctly:

```rust
#[cfg(test)]
mod tests {
    use crate::server::mcp_server::SparkthMCPServer;

    #[test]
    fn test_my_lms_tool_router() {
        let tools = SparkthMCPServer::my_lms_tools_router().list_all();
        // Verify the expected number of tools are registered
        assert_eq!(tools.len(), 1); // greet 
    }
}
```

**Running Tests:**

```bash
# Run all tests
cargo test

# Run specific test
cargo test test_my_lms_tool_router

```

### Step 6: Integrate with the Server

Navigate to `src/server/mcp_server.rs` and locate the `new()` method. Add your router to the tool router chain:

```rust
pub fn new(...) -> Self {
    let tool_router = ToolRouter::new()
        + SparkthMCPServer::tool_router()
        + SparkthMCPServer::my_lms_tools_router(); // Add your router here
    
    // Rest of the implementation...
}
```

Your tools are now ready to extend the Sparkth MCP server's capabilities!
