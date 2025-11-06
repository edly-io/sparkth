pub mod client;
pub mod types;

use crate::define_plugin;

use app_core::ConfigType::String;

define_plugin! {
    id: "openedx_lms",
    name: "Open edX",
    description: "Open edX Learning Management System integration with course creation and content management",
    type: Lms,
    is_builtin: true,
    router: openedx_tools_router,
    config: {
        lms_url: {
            type: String,
            description: "Open edX LMS URL",
            required: true
        },
        studio_url: {
            type: String,
            description: "Open edX Studio URL",
            required: true
        },
        username: {
            type: String,
            description: "Open edX username",
            required: true
        },
        password: {
            type: String,
            description: "Open edX password",
            required: true
        }
    }
}
