#[macro_export]
macro_rules! define_plugin {
    (
        id: $id:expr,
        name: $name:expr,
        description: $desc:expr,
        type: $plugin_type:ident,
        router: $router:ident
    ) => {
        paste::paste! {
            pub struct [<$router:camel Plugin>] {
                manifest: app_core::PluginManifest,
            }

            impl [<$router:camel Plugin>] {
                pub fn new() -> Self {
                    Self {
                        manifest: app_core::PluginManifest {
                            id: $id.to_string(),
                            name: $name.to_string(),
                            version: env!("CARGO_PKG_VERSION").to_string(),
                            description: Some($desc.to_string()),
                            authors: vec![env!("CARGO_PKG_AUTHORS").to_string()],
                            plugin_type: app_core::PluginType::$plugin_type,
                        },
                    }
                }
            }

            #[async_trait::async_trait]
            impl $crate::plugin::MCPPlugin for [<$router:camel Plugin>] {
                fn manifest(&self) -> &app_core::PluginManifest {
                    &self.manifest
                }
            }
        }
    };

    (@default $val:expr, $default:expr) => {
        $val
    };
    (@default , $default:expr) => {
        $default
    };
}
