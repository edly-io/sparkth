#[macro_export]
macro_rules! define_plugin {
    (
        id: $id:expr,
        name: $name:expr,
        description: $desc:expr,
        type: $plugin_type:ident,
        is_builtin: $is_builtin:literal,
        router: $router:ident
        $(, config: {
            $(
                $config_key:ident: {
                    type: $config_type:ident,
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
                #[allow(clippy::vec_init_then_push)]
                pub fn new() -> Self {
                    $(
                        let mut plugin_configs = vec![];

                        $(

                            plugin_configs.push(app_core::PluginConfigSchema {
                                config_key: stringify!($config_key).to_string(),
                                config_type: $config_type,
                                description: Some($config_desc.to_string()),
                                is_required: define_plugin!(@bool_required $($required)?),
                                default_value: define_plugin!(@option_default $($default)?),
                            });
                        )*
                    )?

                    Self {
                        manifest: app_core::PluginManifest {
                            id: $id.to_string(),
                            name: $name.to_string(),
                            version: env!("CARGO_PKG_VERSION").to_string(),
                            description: Some($desc.to_string()),
                            plugin_type: app_core::PluginType::$plugin_type,
                            is_builtin: $is_builtin,
                            created_by_user_id: None,
                            configs: Some(plugin_configs)
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
    (@bool_required $required:literal) => {
        $required
    };
    (@bool_required) => {
        false
    };
}
