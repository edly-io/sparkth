pub mod client;
pub mod types;

use app_core::ConfigType::{String, Number};

use crate::define_plugin;

define_plugin! {
    id: "canvas_lms",
    name: "Canvas LMS",
    description: "Canvas Learning Management System integration with course management, assignments, and student tools",
    type: Lms,
    router: canvas_tools_router,
    config: {
        api_url: {
            type: String,
            description: "Canvas API base URL",
            required: true,
            default: "https://canvas.instructure.com".to_string()
        },
        api_token: {
            type: String,
            description: "Canvas API access token",
            required: true
        },
        timeout: {
            type: Number,
            description: "Request timeout in seconds"
        }
    }
}
