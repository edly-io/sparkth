pub mod client;
pub mod types;

use crate::define_plugin;

define_plugin! {
    id: "openedx_lms",
    name: "Open edX",
    description: "Open edX Learning Management System integration with course creation and content management",
    type: Lms,
    router: openedx_tools_router,
    config: {
        lms_url: {
            type: "string",
            description: "Open edX LMS URL",
            required: true
        },
        studio_url: {
            type: "string",
            description: "Open edX Studio URL",
            required: true
        },
        username: {
            type: "string",
            description: "Open edX username",
            required: true
        },
        password: {
            type: "string",
            description: "Open edX password",
            required: true
        }
    }
}
