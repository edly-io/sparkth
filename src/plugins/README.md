# Sparkth MCP Tools Development Guide

This guide provides a walkthrough for creating custom tools and integrating them into the Sparkth MCP (Model Context Protocol) server.

## Overview

The Sparkth MCP server uses a modular tool system where each tool is:
- Defined as a method in an implementation block
- Automatically registered through the `tool_router` macro
- Integrated into the main server router 

## Creating Your First Tool

Ideally, we want to have tools for connecting our LMS endpoints with the MCP server. This requires an implementation of all the endpoints that our MCP tools can access.

The `src/plugins/` directory will have all the implementions for LMS clients. For now, we have one for `Canvas` in the `/canvas/` directory.

The directory structure is defined as:

```
src/plugins/
├── mod.rs              # Plugin exports
├── canvas/             # Canvas implementation
│   ├── mod.rs
│   ├── client.rs       # CanvasClient struct and request method
|   ├── error.rs        # CanvasError enum
│   └── types.rs        # Canvas-specific types
└── [new_lms]/          # Template for new LMS
```

### Step 1: Implementing Your LMS Client

Create your LMS implementation in `src/plugins/your_lms/`:

#### 1.1. Create modules 

Create modules for `types`, `client` and `error` for your LMS.

Then register them in `src/plugins/your_lms/mod.rs`:

```rust
pub mod client;
pub mod error
pub mod types;
```

#### 1.2. Define types
Add your LMS-specific types in `src/plugins/your_lms/types.rs`:

```rust
use serde::{Deserialize, Serialize};
use crate::plugins::traits::*;

#[derive(Debug, Deserialize)]
#[serde(untagged)]
pub enum MyLMSResponse {
   // LMS-specific response format
}

// Your LMS-specific types
#[derive(Debug, Deserialize)]
pub struct YourLMSCourse {
    pub id: u64,
    pub title: String,
    pub description: Option<String>,
    // LMS-specific fields...
}

// Define other LMS-specific types and conversions...

```

#### 1.3. Define error enum
Define your error enum In `src/plugins/your_lms/error.rs`:

```rust
use thiserror::Error;

#[derive(Error, Debug)]
pub enum MyLMSError {
    #[error("Authentication failed: {0}")]
    Authentication(String),
    #[error("My_LMS API Error ({status_code}): {message}")]
    Api { status_code: u16, message: String },

    // Add other errors as required
    
}
```

#### 1.3. Implement your client
Add your LMS client implementation in `src/plugins/your_lms/client.rs`:

```rust
pub struct MyLMSClient {
    api_token: Option<String>,          // Add other credential fields as required
    client: Client,
}
```

Create an implementation block for your client

```rust
use reqwest::Method;
use serde_json::Value;

use crate::plugins::my_lms::{error::MyLMSError, types::MyLMSResponse};

impl MyLMSClient {
    pub fn new(api_token: String) -> Self {
        Self {
            api_token: Some(api_token), // Initialize other fields if present 
            client: Client::new(),
        }
    }

    pub async fn authenticate(
        new_api_token: String,
    ) -> Result<(), MyLMSError> {
        // Add implementation for authenticating your credentials...
    }

    pub async fn request(
        &self,
        http_method: Method,        // GET, POST, PUT, DELETE, etc.
        endpoint: &str,             // endpoint to hit
        payload: Option<Value>,     // Optional payload. None for GET and DELETE requests, Some(...) for POST, PUT etc.
    ) -> Result<MyLMSResponse, MyLMSError> {
        // Add implementation for sending requests to the endpoint and returning appropriate responses...
    }

}
```

### Step 2: Set Up the Module Structure

Create a new module file in the `src/tools/` directory:

```bash
touch src/tools/my_lms_tools.rs
```

Add your module in `src/tools/mod.rs`:

```rust
pub mod my_lms_tools;
```

### Step 3: Define the Tool Router

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

### Step 4: Implement Your Tool

Add a tool method within the implementation block. Every tool must be marked with the `#[tool]` attribute:

We will prefix the tool's name with the LMS name, e.g., `canvas_get_courses`.

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
    pub fn my_lms_greet(&self) -> Result<CallToolResult, ErrorData> {
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
pub fn my_lms_greet(&self) -> Result<CallToolResult, ErrorData> {
    let greeting = String::from("Hello from Sparkth MCP!");
    Ok(CallToolResult::success(vec![Content::text(greeting)]))
}

```

You can read more about the tool attributes [here](https://docs.rs/rmcp/latest/rmcp/attr.tool.html).


### Step 5: Add Tool Parameters 

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
    pub fn my_lms_greet(
        &self,
        Parameters(ToolParams { name }): Parameters<ToolParams>,
    ) -> Result<CallToolResult, ErrorData> {
        let greeting = format!("Hello {name} from Sparkth MCP!");
        Ok(CallToolResult::success(vec![Content::text(greeting)]))
    }
}
```

#### Authentication Parameters
Tools that connect to the third-party APIs will require authentication credentials, which we can pass directly to the tool.

Define the params

```rust
#[derive(Deserialize, JsonSchema)]
struct AuthParams {
    pub token: String,      // Add other params as required
}
```

Update your `ToolParams`:

```rust
#[derive(Deserialize, JsonSchema)]
struct ToolParams {
    pub name: String,
    pub auth: AuthParams,
}

```

The tool signature will become

```rust
#[tool(description = "A simple greeting tool that returns a friendly message.")]
pub fn my_lms_greet(
    &self,
    Parameters(ToolParams { name, auth }): Parameters<ToolParams>,
) -> Result<CallToolResult, ErrorData> {

    /* Do something with the credentials, e.g., initialize an API client */

    let greeting = format!("Hello {name} from Sparkth MCP!");
    Ok(CallToolResult::success(vec![Content::text(greeting)]))
}
```

#### Example tool with LMS
We will need our tools to call the LMS endpoints. For this purpose, our tools will create an LMS Client instance.

```rust
#[tool(description = "Example tool to connect to LMS.")]
pub fn my_lms_tool(
    &self,
    Parameters(ToolParams { name, auth }): Parameters<ToolParams>,
) -> Result<CallToolResult, ErrorData> {

    let client = MyLMSClient::new(auth.api_token); 

    match client.request(Method::GET, "greet", None).await {
        Ok(...) => todo!(),
        Err(...) => todo!(),

    }
}
```


### Step 6: Test Your Tools

Create a simple test in the same module to ensure your tool works correctly:

```rust
#[cfg(test)]
mod tests {
    use crate::server::mcp_server::SparkthMCPServer;

    #[test]
    fn test_my_lms_tool_router() {
        let tools = SparkthMCPServer::my_lms_tools_router().list_all();
        // Verify the expected number of tools are registered
        assert_eq!(tools.len(), 2); // my_lms_greet, my_lms_tool 
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

### Step 7: Integrate with the Server

Navigate to `src/server/mcp_server.rs` and locate the `new()` method. Add your router to the tool router chain:

```rust
pub fn new() -> Self {
    let tool_router = ToolRouter::new()
        + SparkthMCPServer::tool_router()
        + SparkthMCPServer::my_lms_tools_router(); // Add your router here
    
    // Rest of the implementation...
}
```

Your tools are now ready to extend the Sparkth MCP server's capabilities!
