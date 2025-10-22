pub mod client;
pub mod types;

use crate::define_plugin;

define_plugin! {
    id: "canvas_lms",
    name: "Canvas LMS",
    description: "Canvas Learning Management System integration with course management, assignments, and student tools",
    type: Lms,
    router: canvas_tools_router
}
