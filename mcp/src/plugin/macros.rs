#[macro_export]
macro_rules! define_plugin {
    (
        id: $id:expr,
        name: $name:expr,
        description: $desc:expr,
        type: $plugin_type:ident,
        router: $router:ident
        $(, config: {
            $(
                $config_key:ident: {
                    type: $config_type:literal,
                    description: $config_desc:literal
                    $(, required: $required:literal)?
                    $(, default: $default:expr)?
                }
            ),* $(,)?
        })?
    ) => {
        paste::paste! {
            pub struct [<$router:camel Plugin>] {
                manifest: app_core::PluginManifest,
            }

            impl [<$router:camel Plugin>] {
                pub fn new() -> Self {
                    $(
                        let mut properties = Vec::new();
                        let mut required = Vec::new();

                        $(
                            properties.push((
                                stringify!($config_key).to_string(),
                                app_core::ConfigProperty {
                                    property_type: $config_type.to_string(),
                                    description: $config_desc.to_string(),
                                    default: define_plugin!(@option_default $($default)?),
                                }
                            ));

                            $(
                                if $required {
                                    required.push(stringify!($config_key).to_string());
                                }
                            )?
                        )*

                        let config_schema = Some(app_core::ConfigSchema {
                            schema_type: "object".to_string(),
                            properties,
                            required,
                        });
                    )?

                    Self {
                        manifest: app_core::PluginManifest {
                            id: $id.to_string(),
                            name: $name.to_string(),
                            version: env!("CARGO_PKG_VERSION").to_string(),
                            description: Some($desc.to_string()),
                            authors: vec![env!("CARGO_PKG_AUTHORS").to_string()],
                            plugin_type: app_core::PluginType::$plugin_type,
                            config_schema
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
    (@option_default $val:expr) => { Some($val) };
    (@option_default) => { None };
}
