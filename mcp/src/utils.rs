use rmcp::model::JsonObject;
use schemars::JsonSchema;
use schemars::generate::SchemaSettings;
use schemars::transform::AddNullable;

use std::{any::TypeId, collections::HashMap, sync::Arc};

/// Generate a JSON Schema object for type `T`.
///
/// This mirrors the upstream implementation in the MCP Rust SDK:
/// https://github.com/modelcontextprotocol/rust-sdk/blob/main/crates/rmcp/src/handler/server/tool.rs#L55
///
/// # Difference from upstream
/// - Upstream uses **JSON Schema draft-07**.
/// - This version uses **draft2020-12** for broader compatibility with `mcpo`
///   and other tools that expect the newer JSON Schema specification.
///
/// # Note
/// This is a temporary workaround to keep tooling compatibility aligned.
/// Once the MCP spec and Rust SDK adopt draft2020-12 (or newer), this function
/// should be removed in favor of the upstream implementation.
pub fn schema_for_type<T: JsonSchema>() -> JsonObject {
    // TODO: Remove this custom function once the MCP spec is updated and
    // the Rust SDK adopts draft2020-12 (or newer).
    // Aside from the JSON Schema version, this function is identical
    // to the upstream version, and only exists to make schemas compatible
    // with `mcpo` and other tools relying on draft2020-12.

    let mut settings = SchemaSettings::draft2020_12();
    settings.transforms = vec![Box::new(AddNullable::default())];
    let generator = settings.into_generator();
    let schema = generator.into_root_schema_for::<T>();
    let object = serde_json::to_value(schema).expect("failed to serialize schema");
    match object {
        serde_json::Value::Object(object) => object,
        _ => panic!("unexpected schema value"),
    }
}

/// Retrieve a cached JSON Schema object for type `T`.
///
/// This mirrors the upstream [`cached_schema_for_type`] implementation in the MCP Rust SDK,
/// with **one key difference**:
///
/// # Difference from upstream
/// - Upstream calls its own `schema_for_type` (which uses JSON Schema draft-07).
/// - This version calls our **customized [`schema_for_type`]**, which generates
///   schemas in **draft2020-12** instead of draft-07.
///
/// # Behavior
/// - Caches schema generation results per `TypeId` for reuse across calls.
/// - Uses a thread-local `RwLock<HashMap>` as the schema cache.
/// - Wraps the schema in `Arc` so clones are cheap.
///
/// # Note
/// This is a temporary workaround until the MCP spec and Rust SDK adopt draft2020-12
/// (or newer). At that point, this function should also be removed and replaced with
/// the upstream version.
pub fn cached_schema_for_type<T: JsonSchema + std::any::Any>() -> Arc<JsonObject> {
    thread_local! {
        static CACHE_FOR_TYPE: std::sync::RwLock<HashMap<TypeId, Arc<JsonObject>>> = Default::default();
    };
    CACHE_FOR_TYPE.with(|cache| {
        if let Some(x) = cache
            .read()
            .expect("schema cache lock poisoned")
            .get(&TypeId::of::<T>())
        {
            x.clone()
        } else {
            let schema = schema_for_type::<T>();
            let schema = Arc::new(schema);
            cache
                .write()
                .expect("schema cache lock poisoned")
                .insert(TypeId::of::<T>(), schema.clone());
            schema
        }
    })
}
