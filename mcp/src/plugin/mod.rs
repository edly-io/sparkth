pub mod api;
pub mod error;
pub mod macros;
pub mod registry;

pub use api::{MCPPlugin, PluginManifest};
pub use registry::PluginRegistry;
